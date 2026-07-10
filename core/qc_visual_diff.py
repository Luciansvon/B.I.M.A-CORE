"""Pixel-level visual diff untuk QC revisi gambar kerja (REV_A vs REV_B).

Pipeline per pasangan halaman (murni lokal — nol token API):
    PNG/JPG bytes → grayscale → ORB feature alignment (homography RANSAC)
    → absdiff + threshold + morphology → change mask
    → anaglyph overlay (magenta = hilang dari REV_A, hijau = baru di REV_B)
    → bbox region perubahan (normalized) buat hint prompt VLM.

Kalau alignment gagal (halaman beda total / minim fitur), pasangan halaman
ditandai `aligned=False` — caller lanjut VLM-only, gak pernah lebih buruk
dari perilaku lama.
"""
import base64
import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger("bima_core.qc_visual_diff")

# Ambang ink: gambar kerja = garis gelap di atas kertas putih
_INK_THRESHOLD = 160
# Ambang absdiff (setelah blur) supaya noise anti-aliasing gak ke-flag
_DIFF_THRESHOLD = 30
# Minimal area region perubahan sebagai fraksi luas halaman (~34×34px di 2048px)
_MIN_REGION_AREA_FRAC = 0.0004
# Maksimal region per halaman yang dilaporkan ke VLM (ambil terbesar)
_MAX_REGIONS = 8
# Minimal inlier ORB match supaya homography dianggap valid
_MIN_INLIERS = 15

# Warna anaglyph (RGB) — gaya diff-dwg: magenta = removed, hijau = added
_COLOR_REMOVED = (200, 30, 140)
_COLOR_ADDED = (30, 160, 60)
_COLOR_COMMON = (90, 90, 90)


@dataclass(frozen=True)
class PageDiff:
    """Hasil diff 1 pasangan halaman (REV_A p_i vs REV_B p_i)."""

    page: int  # 1-indexed
    aligned: bool
    changed_ratio: float  # fraksi piksel berubah (0.0-1.0); -1.0 kalau unaligned
    regions: tuple[tuple[float, float, float, float], ...]  # bbox normalized
    anaglyph_png: bytes | None  # None kalau alignment gagal


def _decode_gray(img_bytes: bytes) -> np.ndarray | None:
    """Decode PNG/JPG/WEBP bytes → grayscale ndarray. None kalau gagal."""
    arr = np.frombuffer(img_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    return img


def _align(
    gray_a: np.ndarray, gray_b: np.ndarray
) -> tuple[np.ndarray, np.ndarray] | None:
    """Align gray_b ke frame gray_a via ORB + homography RANSAC.

    Return (gray_b_warped, valid_mask) — valid_mask 255 di area yang beneran
    ke-cover warp; pinggiran hasil border-fill dikecualiin biar gak jadi
    "perubahan" palsu. None kalau fitur kurang / homography degenerate.
    """
    h_a, w_a = gray_a.shape[:2]
    if gray_b.shape[:2] != (h_a, w_a):
        gray_b = cv2.resize(gray_b, (w_a, h_a), interpolation=cv2.INTER_AREA)

    orb = cv2.ORB_create(nfeatures=4000)
    kp_a, des_a = orb.detectAndCompute(gray_a, None)
    kp_b, des_b = orb.detectAndCompute(gray_b, None)
    if des_a is None or des_b is None or len(kp_a) < _MIN_INLIERS or len(kp_b) < _MIN_INLIERS:
        return None

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    knn = matcher.knnMatch(des_b, des_a, k=2)
    good = [m for m, n in (p for p in knn if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < _MIN_INLIERS:
        return None

    src = np.float32([kp_b[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst = np.float32([kp_a[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
    H, inlier_mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
    if H is None or inlier_mask is None or int(inlier_mask.sum()) < _MIN_INLIERS:
        return None

    # Sanity: homography gambar kerja mestinya near-rigid (skala ~1, gak kebalik)
    det = H[0, 0] * H[1, 1] - H[0, 1] * H[1, 0]
    if not (0.4 < abs(det) < 2.5):
        return None

    warped = cv2.warpPerspective(
        gray_b, H, (w_a, h_a),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=255,  # isi pinggiran dengan putih (kertas)
    )
    # Validity mask: warp bidang penuh — area di luar coverage jadi 0.
    # Erode dikit buat buang fringe interpolasi di tepi coverage.
    full = np.full((gray_b.shape[0], gray_b.shape[1]), 255, dtype=np.uint8)
    valid = cv2.warpPerspective(
        full, H, (w_a, h_a),
        flags=cv2.INTER_NEAREST,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    # Homography ORB bisa menyisakan drift translasi kecil pada garis tipis.
    # Rapikan residual itu tanpa mengubah model perspektif utama.
    residual = np.eye(2, 3, dtype=np.float32)
    criteria = (
        cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
        50,
        1e-5,
    )
    try:
        cv2.findTransformECC(
            gray_a,
            warped,
            residual,
            cv2.MOTION_TRANSLATION,
            criteria,
            inputMask=valid,
        )
        inverse_flags = cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP
        warped = cv2.warpAffine(
            warped,
            residual,
            (w_a, h_a),
            flags=inverse_flags,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=255,
        )
        valid = cv2.warpAffine(
            valid,
            residual,
            (w_a, h_a),
            flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
    except cv2.error:
        logger.debug("[qc-vdiff] ECC refinement gagal; pakai hasil ORB")
    valid = cv2.erode(valid, np.ones((5, 5), np.uint8))
    return warped, valid


def _change_mask(
    gray_a: np.ndarray, gray_b_aligned: np.ndarray, valid: np.ndarray
) -> np.ndarray:
    """Binary mask piksel berubah. Blur dulu supaya anti-aliasing gak noise."""
    blur_a = cv2.GaussianBlur(gray_a, (3, 3), 0)
    blur_b = cv2.GaussianBlur(gray_b_aligned, (3, 3), 0)
    diff = cv2.absdiff(blur_a, blur_b)
    _, mask = cv2.threshold(diff, _DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)
    mask[valid == 0] = 0  # area di luar coverage warp bukan perubahan beneran
    kernel = np.ones((3, 3), np.uint8)
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)


def _anaglyph(
    gray_a: np.ndarray, gray_b_aligned: np.ndarray, valid: np.ndarray
) -> bytes:
    """Composite anaglyph RGB → PNG bytes.

    Magenta = ink cuma di REV_A (terhapus), hijau = ink cuma di REV_B (baru),
    abu-abu = ink sama di keduanya, putih = kertas. Area di luar coverage
    warp di-render netral (abu-abu) biar gak keliatan kayak removed palsu.
    """
    ink_a = gray_a < _INK_THRESHOLD
    ink_b = gray_b_aligned < _INK_THRESHOLD
    covered = valid > 0

    h, w = gray_a.shape[:2]
    canvas = np.full((h, w, 3), 255, dtype=np.uint8)
    canvas[ink_a & ink_b] = _COLOR_COMMON
    canvas[ink_a & ~ink_b & covered] = _COLOR_REMOVED
    canvas[~ink_a & ink_b] = _COLOR_ADDED
    canvas[ink_a & ~covered] = _COLOR_COMMON  # ink A di luar coverage: netral

    # cv2.imencode expect BGR
    ok, buf = cv2.imencode(".png", cv2.cvtColor(canvas, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("cv2.imencode PNG gagal")
    return buf.tobytes()


def _extract_regions(
    mask: np.ndarray,
) -> tuple[tuple[float, float, float, float], ...]:
    """Cluster change mask → bbox normalized, urut area terbesar, cap _MAX_REGIONS."""
    h, w = mask.shape[:2]
    min_area = _MIN_REGION_AREA_FRAC * h * w

    # Dilate dulu supaya perubahan bertetangga (misal angka dimensi) nge-cluster
    kernel = np.ones((5, 5), np.uint8)
    clustered = cv2.dilate(mask, kernel, iterations=2)

    contours, _ = cv2.findContours(clustered, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes: list[tuple[float, tuple[float, float, float, float]]] = []
    for c in contours:
        x, y, bw, bh = cv2.boundingRect(c)
        if bw * bh < min_area:
            continue
        boxes.append(
            (float(bw * bh), (x / w, y / h, (x + bw) / w, (y + bh) / h))
        )
    boxes.sort(key=lambda t: -t[0])
    return tuple(
        tuple(round(v, 4) for v in bbox) for _, bbox in boxes[:_MAX_REGIONS]
    )


def _diff_pair(page_num: int, bytes_a: bytes, bytes_b: bytes) -> PageDiff:
    """Diff 1 pasangan halaman. Selalu return PageDiff (aligned=False kalau gagal)."""
    unaligned = PageDiff(
        page=page_num, aligned=False, changed_ratio=-1.0, regions=(), anaglyph_png=None
    )
    gray_a = _decode_gray(bytes_a)
    gray_b = _decode_gray(bytes_b)
    if gray_a is None or gray_b is None:
        return unaligned

    alignment = _align(gray_a, gray_b)
    if alignment is None:
        logger.info(f"[qc-vdiff] p{page_num}: alignment gagal — skip pixel diff")
        return unaligned

    gray_b_aligned, valid = alignment
    mask = _change_mask(gray_a, gray_b_aligned, valid)
    changed_ratio = float(np.count_nonzero(mask)) / mask.size
    regions = _extract_regions(mask)
    anaglyph = _anaglyph(gray_a, gray_b_aligned, valid)

    return PageDiff(
        page=page_num,
        aligned=True,
        changed_ratio=round(changed_ratio, 6),
        regions=regions,
        anaglyph_png=anaglyph,
    )


def diff_from_b64(
    pages_a_b64: list[str], pages_b_b64: list[str]
) -> tuple[PageDiff, ...]:
    """Diff halaman berpasangan index (A p1 vs B p1, dst) sampai min(n_a, n_b)."""
    n = min(len(pages_a_b64), len(pages_b_b64))
    diffs = []
    for i in range(n):
        diffs.append(
            _diff_pair(
                i + 1,
                base64.b64decode(pages_a_b64[i]),
                base64.b64decode(pages_b_b64[i]),
            )
        )
    return tuple(diffs)


def build_hint_text(diffs: tuple[PageDiff, ...], n_a: int, n_b: int) -> str:
    """Susun blok hint hasil pixel-diff buat di-append ke prompt VLM diff.

    Return string kosong kalau gak ada pasangan yang berhasil di-align
    (biar prompt fallback identik dengan perilaku lama).
    """
    if not any(d.aligned for d in diffs):
        return ""

    lines = [
        "",
        "",
        "=== HASIL PIXEL-DIFF LOKAL (OpenCV — GROUND TRUTH VISUAL) ===",
    ]
    if n_a != n_b:
        lines.append(
            f"Catatan: jumlah halaman beda (REV_A={n_a}, REV_B={n_b}) — "
            f"pixel-diff cuma untuk {min(n_a, n_b)} pasangan pertama."
        )
    for d in diffs:
        if not d.aligned:
            lines.append(f"Halaman {d.page}: alignment gagal — bandingkan manual dari gambar.")
            continue
        pct = d.changed_ratio * 100
        if not d.regions:
            lines.append(
                f"Halaman {d.page}: {pct:.2f}% piksel berubah — TIDAK ada area perubahan "
                f"signifikan terdeteksi. Kemungkinan besar halaman ini identik."
            )
            continue
        lines.append(f"Halaman {d.page}: {pct:.2f}% piksel berubah. Area berubah (bbox normalized [x0,y0,x1,y1]):")
        for r in d.regions:
            lines.append(f"  - [{r[0]}, {r[1]}, {r[2]}, {r[3]}]")
    lines.append(
        "Fokuskan deskripsi perubahan pada area di atas. Area yang TIDAK tercantum "
        "hampir pasti tidak berubah — JANGAN mengarang perubahan di luar daftar ini."
    )
    return "\n".join(lines)
