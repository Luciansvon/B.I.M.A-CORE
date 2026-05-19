#!/usr/bin/env python3
"""F5-TTS worker subprocess — isolated process untuk F5-TTS inference.

Spawned per request dari core/tts.py supaya:
- Kalau crash / OOM / hang, anisa-v3 (parent) selamat
- CUDA context isolated → VRAM auto-released saat process exit (no leak)
- Failure manifests as non-zero exit code → parent fallback edge-tts

Args:
    argv[1] = gen_text (string)
    argv[2] = output_wav_path (absolute path)

Env vars (from parent process):
    TTS_HF_REPO, TTS_CKPT_FILE, TTS_VOCAB_FILE — model location
    TTS_BASE_MODEL — base config (F5TTS_v1_Base default)
    TTS_DEVICE — cuda|cpu
    TTS_REF_AUDIO, TTS_REF_TEXT — voice cloning reference
    TTS_SPEED — 0.5-2.0, default 0.9

Exit codes:
    0 = success, WAV file written
    1 = error (text in stderr)
    2 = bad args
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: tts_worker.py '<text>' <output.wav>", file=sys.stderr)
        return 2

    text = sys.argv[1].strip()
    wav_fp = Path(sys.argv[2])

    if not text:
        print("Empty text", file=sys.stderr)
        return 2

    # CUDA cleanup before load — clear any stale context
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    try:
        from huggingface_hub import hf_hub_download
        from f5_tts.api import F5TTS
    except ImportError as e:
        print(f"F5-TTS deps missing: {e}", file=sys.stderr)
        return 1

    repo = os.environ.get("TTS_HF_REPO", "Eempostor/F5-TTS-INDO-FINETUNE-V2")
    ckpt_name = os.environ.get("TTS_CKPT_FILE", "f5_tts_indo_v2.pt")
    vocab_name = os.environ.get("TTS_VOCAB_FILE", "vocab.txt")
    base_model = os.environ.get("TTS_BASE_MODEL", "F5TTS_v1_Base")
    device = os.environ.get("TTS_DEVICE", "cuda")

    # Defaults match core/tts.py constants — kalau env gak diset, pakai default path/text
    default_ref_audio = str(Path(__file__).resolve().parent.parent / "assets" / "tts_ref.wav")
    default_ref_text = "Halo, saya Anisa, asisten AI yang siap membantu kamu."

    ref_audio = os.environ.get("TTS_REF_AUDIO") or default_ref_audio
    ref_text = os.environ.get("TTS_REF_TEXT") or default_ref_text

    if not Path(ref_audio).exists():
        print(f"TTS_REF_AUDIO missing or not found: {ref_audio}", file=sys.stderr)
        return 1

    try:
        speed = float(os.environ.get("TTS_SPEED", "0.9"))
    except ValueError:
        speed = 0.9

    cache_dir = str(Path(__file__).resolve().parent.parent / "assets" / "f5_tts_cache")

    try:
        ckpt_path = hf_hub_download(repo_id=repo, filename=ckpt_name, cache_dir=cache_dir)
        vocab_path = hf_hub_download(repo_id=repo, filename=vocab_name, cache_dir=cache_dir)
    except Exception as e:
        print(f"HF download failed: {e}", file=sys.stderr)
        return 1

    try:
        tts = F5TTS(
            model=base_model,
            ckpt_file=ckpt_path,
            vocab_file=vocab_path,
            device=device,
        )
        tts.infer(
            ref_file=ref_audio,
            ref_text=ref_text,
            gen_text=text,
            file_wave=str(wav_fp),
            speed=speed,
        )
    except Exception as e:
        print(f"F5-TTS inference error: {e}", file=sys.stderr)
        return 1

    if not wav_fp.exists():
        print("Output WAV missing after inference", file=sys.stderr)
        return 1

    print(f"OK:{wav_fp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
