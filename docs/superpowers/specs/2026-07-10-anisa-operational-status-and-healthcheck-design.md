# Anisa Operational Status and Healthcheck Design

**Tanggal:** 2026-07-10

## Tujuan

Menyediakan snapshot status Anisa yang selalu diperbarui sehingga agent cukup membaca satu file kecil, sekaligus memperbaiki healthcheck yang saat ini menghasilkan false error dan menambah regression test.

## Scope

1. Sidecar collector memperbarui `runtime/anisa_status.json` setiap 30 detik.
2. Snapshot mencakup status PM2, resource sistem, health aplikasi, indeks RAG, Git, dan error operasional terakhir yang sudah disanitasi.
3. Snapshot dianggap basi setelah 90 detik; agent hanya melakukan diagnosis lebih dalam jika snapshot basi atau status bermasalah.
4. `scripts/healthcheck.py` memakai project root yang benar dan dapat diuji tanpa menjalankan pemeriksaan saat di-import.
5. Unit test mencakup resolusi project root, status indeks, freshness snapshot, penulisan atomic, dan sanitasi error.
6. `.env` diarahkan ke vault lokal WSL setelah perubahan konfigurasi disetujui.
7. Dependensi WhatsApp yang terdeteksi `npm audit` diperbarui tanpa `--force`, kemudian diverifikasi ulang.
8. Semua kesalahan, akar masalah, bukti, dan solusi dicatat di `error_solutions.md`.

## Arsitektur

```text
PM2 + system metrics + health endpoint + indexes + Git + logs
                              |
                    scripts/status_collector.py
                     (interval 30 detik, sidecar)
                              |
                 atomic replace: temp -> final
                              |
                    runtime/anisa_status.json
                              |
                 agent membaca satu snapshot
```

Collector berjalan sebagai proses PM2 terpisah agar tetap bisa melaporkan ketika `anisa-v3` berhenti. Data dikumpulkan dengan timeout pendek dan kegagalan satu sumber tidak membatalkan seluruh snapshot. File ditulis ke file sementara dalam direktori yang sama lalu diganti secara atomic.

## Kontrak Snapshot

```json
{
  "schema_version": 1,
  "updated_at": "2026-07-10T21:30:00+07:00",
  "overall": "healthy",
  "services": {
    "anisa-v3": {"status": "online", "uptime_seconds": 1200, "restarts": 0},
    "bima-whatsapp": {"status": "online", "uptime_seconds": 1100, "restarts": 0},
    "bima-tunnel": {"status": "online", "uptime_seconds": 1150, "restarts": 0}
  },
  "resources": {
    "cpu_percent": 18.2,
    "ram_percent": 63.1,
    "disk_percent": 22.4
  },
  "health": {"backend": "reachable"},
  "indexes": {
    "search_index": "ready",
    "repo_index": "ready",
    "vault_index": "ready"
  },
  "code": {"commit": "94b406d", "dirty": true},
  "last_error": null
}
```

Nilai `overall`:

- `healthy`: seluruh service wajib online, backend reachable, snapshot valid, dan resource di bawah threshold.
- `degraded`: sumber non-kritis gagal, indeks tidak siap, atau threshold peringatan terlampaui.
- `down`: `anisa-v3` offline atau health backend tidak reachable.

## Freshness dan Fallback Agent

Agent membaca `runtime/anisa_status.json` terlebih dahulu.

- Umur <= 90 detik dan `healthy`: gunakan snapshot tanpa scan tambahan.
- Umur <= 90 detik dan `degraded/down`: periksa hanya komponen yang ditandai bermasalah.
- Umur > 90 detik, file hilang, atau JSON rusak: jalankan diagnosis langsung dan laporkan snapshot collector bermasalah.

## Keamanan

- Error log disanitasi terhadap pola token, API key, bearer token, dan nilai environment sensitif.
- Snapshot tidak menyimpan isi `.env`, command line lengkap, atau isi pesan pengguna.
- `npm audit fix --force` tidak digunakan.
- Perubahan `.env` hanya menyentuh `OBSIDIAN_PATH`.

## Healthcheck dan Testing

`scripts/healthcheck.py` dipisahkan menjadi fungsi yang dapat dipanggil test dan memakai `Path(__file__).resolve().parent.parent` sebagai root. Eksekusi CLI ditempatkan di bawah `if __name__ == "__main__":`.

Test minimum:

1. Project root menunjuk direktori yang memiliki `core/`, `teams/`, dan `main.py`.
2. Import modul tidak otomatis menjalankan healthcheck.
3. Folder indeks yang ada dilaporkan siap.
4. Snapshot ditulis sebagai JSON valid melalui atomic replace.
5. Snapshot lama terdeteksi stale setelah 90 detik.
6. Error sensitif disanitasi sebelum ditulis.
7. Status keseluruhan mengikuti prioritas `down > degraded > healthy`.

Verifikasi akhir mencakup pytest baru, pytest terkait, eksekusi healthcheck nyata, `node --check whatsapp/index.js`, `npm audit`, dan validasi satu snapshot collector.

## Batasan

- Tidak menambah database status atau dashboard histori.
- Tidak melakukan scan seluruh repository setiap 30 detik; Git hanya membaca commit dan status ringkas.
- Tidak mengubah fitur QC yang sedang memiliki perubahan lokal.
- Tidak melakukan refactor di luar healthcheck, collector, konfigurasi PM2, test terkait, dan dokumentasi error.
