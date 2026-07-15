# Audit 18 Repo untuk BIMA_CORE — 15 Juli 2026

## Kesimpulan cepat

```text
IMPLEMENTASI UTAMA : obsidian-skills -> Arsip/Vault
                     DuckDB         -> Admin/Data Analysis

PILOT TERISOLASI   : Strix          -> security scan lokal/CI

AMBIL POLA SAJA    : awesome-llm-apps

KONDISIONAL        : Meilisearch, Novu, Directus, SheetJS, InfluxDB, DBeaver

JANGAN SEKARANG    : ClickHouse, Prisma, TiDB, sqlmap, TypeORM,
                     SurrealDB, CockroachDB, RocksDB
```

Jawaban singkat: **bisa diimplementasikan, tetapi tidak masuk akal memasukkan semua repo.** Untuk kondisi BIMA_CORE saat ini, keuntungan paling jelas datang dari adaptasi Obsidian Skills dan DuckDB. Strix layak diuji sebagai proses terisolasi, bukan diberi akses langsung sebagai tool agen produksi.

## Kondisi BIMA_CORE yang sudah ada

- Backend utama Python 3.12; Node.js hanya dipakai untuk bridge WhatsApp.
- Arsip dan Repo RAG sudah memakai LanceDB + BM25 hybrid search.
- Memory, cache pencarian, biaya LLM, dan histori saham sudah memakai beberapa SQLite lokal.
- Admin sudah membaca CSV/Excel dengan pandas/openpyxl dan membuat chart.
- Notifikasi sudah Discord-first dengan Apprise fallback; WhatsApp juga sudah punya bridge sendiri.
- SecurityScannerTool saat ini hanya menjalankan Bandit + Flake8. Audit sebelumnya masih mencatat security debt, jadi scanner ofensif wajib diisolasi.

Konsekuensinya: ORM JavaScript, database distributed, dan mesin search baru akan menduplikasi fondasi yang sudah bekerja.

## Penilaian per repo

| Repo | Fungsi sebenarnya | Cocok ke BIMA_CORE? | Keputusan |
|---|---|---:|---|
| [Shubhamsaboo/awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps) | Kumpulan contoh agent, RAG, skills, voice, dan generative UI; bukan framework tunggal. | Sedang | **Ambil pola saja.** Audit contoh RAG failure diagnostics, trust-gated agent, dan eval; jangan menyalin seluruh repo atau menambah framework agent ketiga. |
| [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | Skills standar untuk Obsidian CLI dan format Markdown, Bases, serta JSON Canvas. | Sangat tinggi | **Implementasi utama.** Adaptasi skill terpilih ke Tim Arsip/Bima_Vault. Utamakan format file terbuka; Obsidian CLI dibuat opsional agar bot tetap jalan headless. |
| [usestrix/strix](https://github.com/usestrix/strix) | Agent pentest dinamis: SAST, DAST, exploit validation, report, dan CI. Membutuhkan Docker + API LLM. | Tinggi, berisiko | **Pilot terisolasi.** Jalankan hanya pada codebase/domain milik Bima, non-interaktif, target allowlist, output report-only, tanpa auto-fix/commit. Pin versi/image; jangan pakai `curl | bash` di production. |
| [novuhq/novu](https://github.com/novuhq/novu) | Infrastruktur komunikasi multi-channel: inbox, email, SMS, push, chat, workflow, digest, dan preference. | Rendah sekarang | **Kondisional.** BIMA sudah Discord + WhatsApp + Apprise. Novu baru berguna jika nanti ada banyak user, inbox web, preference, workflow bercabang, atau audit delivery. |
| [meilisearch/meilisearch](https://github.com/meilisearch/meilisearch) | Search server via REST API dengan full-text, semantic/hybrid search, filter, facet, dan multi-tenancy. | Sedang | **Kondisional.** Jangan mengganti LanceDB + BM25 sebelum ada benchmark yang membuktikan latency/relevansi buruk atau kebutuhan search dashboard multi-user. Menambah daemon, sinkronisasi index, RAM, dan backup. |
| [dbeaver/dbeaver](https://github.com/dbeaver/dbeaver) | Aplikasi desktop untuk membuka, query, edit, migrasi, dan visualisasi database. | Berguna sebagai alat dev | **Tidak diintegrasikan ke bot.** Install terpisah di Windows untuk inspeksi SQLite. Ini tool manusia, bukan library/runtime BIMA_CORE. |
| [ClickHouse/ClickHouse](https://github.com/ClickHouse/ClickHouse) | Database kolumnar OLAP untuk analitik real-time berskala besar. | Rendah | **Jangan sekarang.** Cocok bila event/log mencapai skala besar dan dashboard agregasi berat; saat ini SQLite/file log jauh lebih hemat. |
| [prisma/prisma](https://github.com/prisma/prisma) | ORM Node.js/TypeScript: type-safe client, migration, dan Studio. | Sangat rendah | **Jangan.** Backend utama Python dan bridge Node tidak memiliki domain database. Menambah Prisma hanya menciptakan schema/migration stack kedua. |
| [pingcap/tidb](https://github.com/pingcap/tidb) | Database SQL distributed, MySQL-compatible, ACID, HA, HTAP, dan vector search. | Sangat rendah | **Jangan.** Dibuat untuk cluster dan pertumbuhan besar; BIMA solo/local tidak butuh consensus, replica, atau operator cluster. |
| [duckdb/duckdb](https://github.com/duckdb/duckdb) | Database analitik embedded/in-process; SQL langsung atas CSV/Parquet dan integrasi pandas. | Sangat tinggi | **Implementasi utama.** Tambahkan jalur read-only di DataAnalysisTool untuk file tabel besar dan query SQL terkontrol. Tetap pakai pandas/openpyxl untuk Excel dan rendering chart. |
| [sqlmapproject/sqlmap](https://github.com/sqlmapproject/sqlmap) | Tool otomatis untuk mendeteksi dan mengeksploitasi SQL injection. | Rendah dan sensitif | **Jangan jadi tool agen.** Fungsinya terlalu sempit dan ofensif. Jika pentest disetujui, Strix terisolasi sudah mencakup pengujian injection dalam workflow lebih luas. |
| [typeorm/typeorm](https://github.com/typeorm/typeorm) | ORM TypeScript/JavaScript untuk banyak database. | Sangat rendah | **Jangan.** Alasan sama dengan Prisma; tidak cocok dengan backend Python dan tidak ada kebutuhan ORM pada WA bridge. |
| [directus/directus](https://github.com/directus/directus) | Backend/headless CMS: REST/GraphQL, admin Studio, auth, workflow, dan MCP di atas SQL DB. | Sedang untuk produk lain | **Kondisional sebagai service terpisah.** Bisa dipakai untuk katalog furnitur/admin content, tetapi jangan ditanam ke core bot. Lisensinya punya syarat organisasi yang harus ditinjau. |
| [SheetJS/sheetjs](https://github.com/SheetJS/sheetjs) | Toolkit JavaScript untuk baca/tulis spreadsheet di browser/Node. Repo GitHub hanya mirror lama; source aktif pindah ke git.sheetjs.com. | Rendah sekarang | **Kondisional.** Pakai hanya bila dashboard harus import/export XLSX langsung di browser. Backend sudah punya openpyxl/pandas, jadi saat ini duplikat. |
| [surrealdb/surrealdb](https://github.com/surrealdb/surrealdb) | Database multi-model: document, graph, relational, time-series, vector/hybrid, realtime. | Menarik, tetapi rendah | **Jangan migrasi.** Secara teori bisa menyatukan banyak store, tetapi migrasi memory + vault + RAG sangat besar dan menghilangkan kesederhanaan file Markdown/SQLite. |
| [cockroachdb/cockroach](https://github.com/cockroachdb/cockroach) | Distributed SQL yang fokus pada HA lintas node/datacenter dan strong consistency. | Sangat rendah | **Jangan.** Kompleksitas cluster tanpa manfaat pada bot solo. |
| [facebook/rocksdb](https://github.com/facebook/rocksdb) | Embedded persistent key-value storage engine level rendah. | Sangat rendah | **Jangan.** Bukan database siap pakai untuk aplikasi Python; binding/native build dan desain schema menjadi beban. SQLite/DiskCache/LanceDB sudah menutup kebutuhan. |
| [influxdata/influxdb](https://github.com/influxdata/influxdb) | Time-series/event database untuk monitoring, telemetry, market data, dan dashboard real-time. | Sedang nanti | **Kondisional.** Masuk akal jika observability/saham menyimpan data time-series besar dan butuh query dashboard cepat. Sekarang `saham_history.db`, cost DB, PM2, dan log sudah cukup. |

## Bentuk implementasi yang masuk akal

### Paket A — direkomendasikan

1. Adaptasi `obsidian-skills` terpilih ke Arsip:
   - validasi Markdown/frontmatter;
   - pembuatan dan pembaruan `.base`/Bases;
   - pembuatan JSON Canvas untuk hubungan catatan;
   - path dibatasi ke `Bima_Vault/`;
   - tes tidak merusak file vault lama.
2. Tambahkan DuckDB secara kecil:
   - dependency Python yang dipin;
   - tool read-only untuk CSV/Parquet;
   - path allowlist `outputs/`/attachment temp;
   - larang statement mutasi, extension install, dan akses network;
   - fallback ke pandas untuk Excel/chart.

### Paket B — sesudah Paket A stabil

Pilot Strix manual di container terpisah:

- target pertama hanya checkout lokal BIMA_CORE;
- scan mode cepat dan non-interaktif;
- credential terpisah dengan budget rendah;
- hasil ditulis sebagai report, tidak auto-patch;
- setiap temuan diverifikasi manual sebelum masuk backlog;
- domain publik hanya boleh dipindai setelah scope/izin tertulis jelas.

### Yang tidak perlu dibangun sekarang

- Meilisearch tidak mengganti RAG hanya karena populer; harus menang benchmark relevansi dan latency.
- Novu tidak mengganti Discord/WA/Apprise sebelum ada kebutuhan multi-user/inbox/preferences.
- Database cluster tidak dipasang untuk menyelesaikan masalah yang belum ada.
- Prisma dan TypeORM tidak dipakai pada backend Python.
- DBeaver dipakai sebagai aplikasi desktop, bukan dependency proyek.

## Gate sebelum perubahan

Workspace saat audit sudah memiliki banyak perubahan milik user. Implementasi harus memakai minimal diff dan tidak menormalkan/mengutak-atik file di luar scope. Sebelum CODE, buat `PLAN.md`, minta approval Bima, tambah unit test, lalu jalankan pytest sesuai aturan repo.
