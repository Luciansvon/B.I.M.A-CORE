# Discord Image-Only Vision Hotfix

## Root cause

`core/discord_bot.py` hanya mengizinkan pesan kosong jika attachment-nya audio. Pesan berisi gambar tanpa caption berhenti sebelum proses download, sehingga `attachment_paths` tidak pernah sampai ke LangGraph/Visual.

## Task list

- [x] Tambah regression test untuk keputusan menerima attachment Discord tanpa teks.
- [x] Izinkan pesan kosong jika memiliki attachment gambar yang didukung.
- [x] Beri intent eksplisit `analisis gambar ini` agar classifier langsung memilih tim Visual.
- [x] Lewati CrewAI controller untuk image-only dan panggil `ImageAnalyzerTool` langsung dengan batas output tool 1.500 token.
- [x] Jalankan test target, syntax check, lalu restart proses Discord backend.
- [x] Catat root cause dan pencegahan di `error_solutions.md`.

## Hasil verifikasi runtime

- Discord berhasil mengunduh gambar tanpa caption, membentuk prompt `analisis gambar ini`, dan menjalankan tim Visual.
- Eksekusi Vision berikutnya berhenti pada OpenRouter HTTP 402: CrewAI meminta batas output 65.536 token, sementara akun hanya diberi affordability sekitar 1.867 token.
- Fast-path langsung diterapkan tanpa mengubah model/config global; verifikasi provider dilakukan setelah restart kedua.
- Smoke call terhadap gambar Discord tersimpan berhasil dan Gemini Vision mengembalikan analisis penuh dengan `max_tokens=1500`.

## Batas perubahan

- Tidak mengubah aturan WhatsApp.
- Tidak membuat semua file tanpa caption otomatis diproses; bypass khusus format gambar yang sudah didukung Discord.
- Tidak menambah dependency.
