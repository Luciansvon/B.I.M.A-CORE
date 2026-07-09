# Audit Upgrade Sistem ANISA — Juli 2026

Tanggal: 9 Juli 2026. Audit peluang upgrade berdasar teknologi terbaru (GitHub/HF 2026), mengikuti disiplin `.clauderules` Log 1 (kroscek yang sudah ada dulu) + feedback MCP audit (grep tool/model aktual, bukan asumsi). Lanjutan dari audit Juni 2026 dan migrasi embedder → Qwen3 (9 Juli).

## Temuan kunci: library sudah current, yang perlu di-upgrade = MODEL-nya

Semua dependency inti sudah versi terbaru — **bukan** kasus "paket basi":

| Lib | Versi terpasang | Status |
|---|---|---|
| crewai | 1.14.3 | current |
| langgraph | 1.1.10 | current |
| discord.py | 2.7.1 | current |
| transformers | 5.7.0 | current |
| torch | 2.12.0 (cu130) | current |
| sentence-transformers | 5.4.1 | current |
| faster-whisper | 1.2.1 | current |
| f5-tts | 1.1.20 | current |
| browser-use | 0.12.6 | current |
| scrapling | 0.4.7 | current |
| lancedb | 0.30.0 | current |

Jadi peluang upgrade = **ganti model di dalam lib yang sudah current**, bukan bump paket.

---

## TIER 1 — Clear win, low-effort, bisa di-benchmark

### 1. Reranker RAG: `ms-marco-MiniLM-L-6-v2` (English) → multilingual

* **Lokasi**: [teams/t3_arsip.py:31](../teams/t3_arsip.py#L31) — `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device="cpu")`. Dipakai re-rank hasil vault search (baris 301-304) + di-warmup di [core/discord_bot.py:217](../core/discord_bot.py#L217).
* **Masalah**: Ini **persis bug yang baru kita fix di embedder** — model reranking English dipakai buat konten Indonesia. Reranker jalan SETELAH retrieval, nge-reorder kandidat. Setelah embedder naik ke Qwen3 multilingual, reranker English bisa **mendemote balik** hasil Indonesia yang benar → membatalkan sebagian gain kemarin. Pipeline jadi tidak konsisten (retriever multilingual, reranker English).
* **SOTA 2026**: Qwen3-Reranker series = pilihan teratas multilingual (100+ bahasa, 32k context). Dua opsi:
  - **`BAAI/bge-reranker-v2-m3`** — drop-in `CrossEncoder` (API sama persis, ganti 1 baris di t3_arsip.py), multilingual, proven. **Effort minimal.**
  - **`Qwen/Qwen3-Reranker-0.6B`** — sepasang dengan Qwen3-Embedding, kemungkinan kualitas tertinggi, TAPI pakai format causal-LM (bukan CrossEncoder API) → butuh loader custom, lebih banyak kode.
* **Rekomendasi**: benchmark `bge-reranker-v2-m3` vs `ms-marco` di data Indonesia (metode sama kayak embedder). Kalau menang → swap 1 baris. Model ~568MB (download via HF token + hf_transfer yang sudah ada).
* **Catatan**: reranker juga disebut di [core/bm25_index.py](../core/bm25_index.py) (merge → rerank → top-K), jadi upgrade ini kena vault RAG dan repo RAG. bge-reranker-v2-m3 multilingual + tetap bagus buat English/code → aman dua-duanya.

### 2. STT: faster-whisper `small` → `large-v3-turbo`

* **Lokasi**: [core/stt.py:30](../core/stt.py#L30) — `STT_MODEL_SIZE` default `"small"` (244M param, dipilih demi kecepatan CPU).
* **Masalah**: `small` akurasinya lemah buat Indonesia (bahasa low-resource, model kecil makin kena). Voice note Discord/WA sering salah transkrip.
* **Upgrade**: `large-v3-turbo` (809M, decoder 4 layer) — **~6x lebih cepat dari large-v3, akurasi mendekati large**, jauh di atas `small`. **Lib sama** (faster-whisper 1.2.1 sudah support), cukud set `STT_MODEL_SIZE=large-v3-turbo`. Kamu punya **GPU** → latency tetap rendah. Effort: 1 env var + restart.
* **Bukan pilihan**: distil-whisper (praktis English-only), Voxtral/Canary (lib beda, lebih berat, tidak jelas kuat di Indonesia).
* **Rekomendasi**: coba `large-v3-turbo` di GPU, tes beberapa voice note Indonesia, bandingkan transkrip vs `small`. Reversible (env var).

---

## TIER 2 — Worth considering, medium effort

### 3. OCR: `easyocr` → VLM (reuse Gemini) atau OCR modern 2026

* **Lokasi**: [core/ocr.py](../core/ocr.py) — easyocr 1.7.2 (arsitektur CRNN, relatif tua).
* **Peluang**: Kamu SUDAH punya Gemini Vision (`google/gemini-3.5-flash`) buat furniture QC. Untuk `!ocr` teks umum, VLM biasanya jauh lebih akurat daripada easyocr (layout, tulisan tangan, tabel) — tanpa dependency/model baru, pakai yang sudah dibayar. Alternatif lokal: PaddleOCR v5 / dots.ocr (2026) kalau mau tetap offline.
* **Rekomendasi**: pertimbangkan route `!ocr` ke Gemini Vision existing (nol dependency baru), simpan easyocr sebagai fallback offline. Perlu cek dulu volume/latency/biaya.

---

## TIER 3 — Biarkan (sudah optimal / refactor tidak sepadan)

* **LLM models**: sudah modern — DeepSeek v4 Flash (routing/umum), v4 Pro (coding), Gemini 3.5 Flash (visual), Claude Sonnet 5 (Threads). Tidak ada win jelas. (Audit Juni: "model swap = only clear win" sudah dieksekusi.)
* **TTS**: F5-TTS Indo V2 (Eempostor finetune) itu pilihan sengaja buat voice-clone Indonesia. TTS generik 2026 (Kokoro/Chatterbox/Orpheus) malah kehilangan kualitas Indonesia. Biarkan.
* **Orchestration**: CrewAI 1.14 + LangGraph 1.1 dual-framework. Jalan, tapi konsolidasi = refactor besar berisiko tinggi, gain tidak jelas. Jangan sentuh tanpa alasan kuat.
* **Scraping/web**: scrapling 0.4.7 + browser-use 0.12.6 + agent-reach (X) — semua modern 2025/2026. Current.
* **Image gen**: OpenRouter + Gemini Flash Image — **terkunci** (permintaan eksplisit Bima, jangan diutak).
* **Vision QC**: furniture_qc baru pindah ke `supervision` (Roboflow) — current.

---

## Rekomendasi urutan eksekusi

1. **Reranker → bge-reranker-v2-m3** (Tier 1.1): benchmark dulu (metode = embedder kemarin), kalau menang swap 1 baris. Melengkapi migrasi embedder. **Prioritas tertinggi** — konsistensi pipeline.
2. **STT → large-v3-turbo** (Tier 1.2): paling low-effort (env var), tes voice note Indonesia. Bisa barengan.
3. **OCR → VLM** (Tier 2): kalau `!ocr` sering dipakai & easyocr sering meleset.

Semua Tier 1 reversible dan bisa dibuktikan dengan angka sebelum commit — sesuai disiplin "benchmark first" Bima.
