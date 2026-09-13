# Team model router

Status: approved 2026-07-20; model catalog refreshed and implemented 2026-08-25.

## Goal

B.I.M.A Core memilih model berdasarkan peran tim dan tingkat pekerjaan. Model mahal atau reasoning tinggi hanya dipakai saat tugas membutuhkan kualitas tambahan. Semua model yang dipilih adalah rilis stabil, bukan preview, beta, experimental, atau alias `latest`.

Bot Threads tetap memakai `anthropic/claude-sonnet-5` tanpa reasoning effort `high`.

## Model mapping

* T1 Manager memakai `deepseek/deepseek-v4-flash-0731`.
* T2 Visual memakai `google/gemini-3.7-flash`.
* T3 Arsip memakai DeepSeek V4 Flash 0731 untuk pencarian biasa dan `qwen/qwen3.8-27b` untuk sintesis lintas dokumen.
* T4 Admin memakai DeepSeek V4 Flash 0731 untuk dokumen ringan dan `anthropic/claude-sonnet-5` dengan reasoning effort `high` untuk tulisan berat.
* T5 Intel memakai `qwen/qwen3.8-27b`.
* T6 Lifestyle memakai DeepSeek V4 Flash 0731.
* T7 Seniman memakai Gemini 3.7 Flash.
* T8 Mekanik memakai `deepseek/deepseek-v4-pro-0813`, dengan reasoning effort `high` untuk pekerjaan berat.
* T9 Saham memakai objek LLM khusus dengan DeepSeek V4 Pro 0813.
* T10 Kodok memakai DeepSeek V4 Pro 0813, dengan reasoning effort `high` untuk analisis repo berat.

T2 dan T6 tidak berubah. T9 berhenti memakai objek LLM milik T5.

## Routing rules

Router memakai aturan lokal tanpa panggilan LLM tambahan.

T3 masuk profil berat saat permintaan meminta perbandingan banyak dokumen, sintesis lintas sumber, atau rangkuman seluruh koleksi. Permintaan arsip lain memakai profil ringan.

T4 masuk profil berat untuk copywriting, caption, headline, tagline, landing page, broadcast, kampanye, iklan, promosi, proposal, kontrak, dan tulisan akademik. Excel, rekap, konversi format, perapian dokumen, serta permintaan tanpa sinyal tersebut memakai profil ringan.

T8 dan T10 masuk profil berat untuk pekerjaan repo-wide, multi-file, arsitektur, keamanan, refactor besar, atau debugging yang berulang. Penjelasan kode, diagnosis awal, dan perubahan sempit memakai profil normal.

Default tiap selector adalah profil yang lebih murah. Selector mencatat nama tim dan profil tanpa mencatat isi prompt.

## Components

`core/model_router.py` menyimpan model ID, profil tiap tim, aturan pemilihan profil, dan helper untuk membuat salinan lokal CrewAI agent dengan LLM terpilih.

`config.py` membuat objek CrewAI LLM dari profil tersebut. Nama lama seperti `admin_llm`, `intel_llm`, dan `mekanik_llm` tetap tersedia agar import lain tidak rusak. Objek tambahan diberi nama berdasarkan tim dan profil.

Node T3, T4, T8, dan T10 membuat salinan lokal dari agent canonical sebelum menjalankan Crew. Cara ini mencegah request paralel saling mengganti model. Salinan memakai daftar tool yang sama sehingga tool MCP yang disuntikkan saat startup tetap tersedia.

`core/langgraph_nodes/llm_config.py` mengekspor LLM LangChain khusus Intel dan Seniman. Panggilan langsung pada node tersebut tidak lagi diam-diam memakai `default_llm` DeepSeek Flash. `default_llm` tetap dipakai Manager, scheduler, context summarizer, dan tugas ringan bersama.

## Failure handling

Jalur berat mengirim daftar fallback melalui parameter `models` milik OpenRouter:

* T3: Qwen3.8 27B ke DeepSeek V4 Flash 0731.
* T4: Claude Sonnet 5 High ke DeepSeek V4 Flash 0731.
* T8 dan T10: DeepSeek V4 Pro 0813 ke DeepSeek V4 Flash 0731.

T5 Intel memakai DeepSeek V4 Flash sebagai fallback. T2 Visual, T7 Seniman, Canvas, Observer, OCR, dan QC memakai Gemini 3.1 Flash Lite sebagai fallback multimodal. T9 Saham memakai DeepSeek V4 Flash sebagai fallback.

Fallback hanya berjalan saat model utama menghasilkan error API, rate limit, downtime, atau moderation refusal. Hasil yang kurang bagus tidak memicu pemanggilan ulang otomatis.

## Tests

Tes fokus memeriksa:

* seluruh model ID memakai rilis stabil;
* reasoning effort dan urutan fallback;
* klasifikasi permintaan ringan dan berat;
* pemilihan LLM pada salinan agent tanpa memutasi agent canonical;
* Intel dan Seniman memakai LLM LangChain khusus;
* T9 tidak lagi berbagi objek LLM dengan T5;
* model Threads tetap sama dan tanpa effort `high`.

Tidak ada perubahan dependency, model generasi video, atau konfigurasi CI. Default model image di `.env.example` memakai rilis stabil `google/gemini-3.1-flash-image`; konfigurasi `.env` aktif tidak disentuh. Perubahan Python memerlukan restart `anisa-v3`.
