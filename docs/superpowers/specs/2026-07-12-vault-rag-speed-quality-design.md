# Desain Optimasi RAG Utama Anisa

Tanggal: 2026-07-12

## Tujuan

- Waktu retrieval hangat 1-3 detik pada perangkat Bima.
- Meningkatkan relevansi konteks Bahasa Indonesia tanpa mengganti LanceDB.
- Mengurangi kerja pencarian yang duplikat dan mencegah jawaban tanpa dukungan vault.
- Memastikan catatan baru masuk ke struktur yang konsisten tanpa merusak catatan lama.

## Kondisi Sekarang

- Sumber utama: Markdown di `Bima_Vault/`.
- Chunk: berdasarkan heading, sekitar 500 karakter dengan overlap 100 karakter.
- Retrieval menjalankan dense search, LanceDB FTS, dan BM25.
- Hasil FTS dikumpulkan tetapi tidak masuk fusion ranking final.
- BM25 dibaca dari pickle pada setiap query.
- Hingga 20 kandidat diproses `BAAI/bge-reranker-v2-m3` di CPU.
- Embedding dokumen hanya memakai isi chunk; nama file dan heading tidak ikut.
- Hasil akhir tidak memperluas konteks ke chunk tetangga.
- Auto-Save tidak memiliki kategori tervalidasi; seluruh 27 catatan Auto-Save existing berada di folder akar.
- Deduplikasi hanya berlaku pada nama file sama dan 200 karakter awal.
- Pesan Manager dapat keliru dianggap data upstream oleh node Arsip.
- Linker menghapus semua teks dari heading `Catatan Terkait` sampai akhir file sebelum membangun ulang bagian tersebut.

## Desain Terpilih

Pertahankan LanceDB, Qwen3 Embedding 0.6B, BGE reranker, dan format sumber Markdown. Optimasi dilakukan di pipeline retrieval agar perubahan kecil dan bisa dibandingkan dengan perilaku lama.

```text
Query pengguna
    |
    v
Qwen3 query embedding + retrieval instruction
    |
    +--------------------+
    |                    |
    v                    v
Dense top-N        BM25 top-N (cache RAM)
    |                    |
    +------ fusion ------+
              |
              v
       8-10 kandidat unik
              |
              v
       BGE reranker CPU
              |
              v
   relevance gate + chunk tetangga
              |
              v
      konteks dengan sumber
```

## Perubahan Teknis

### 1. Contextual document embedding

Teks yang di-embedding saat indexing berbentuk:

```text
Document: <nama file>
Section: <heading>
Content: <isi chunk>
```

Konten asli tetap disimpan untuk keluaran. Metadata membantu query yang menyebut topik/judul menemukan bagian yang tepat.

### 2. Query instruction khusus Qwen3

Query lokal Qwen3 memakai prompt retrieval khusus arsip Bahasa Indonesia. Dokumen tidak diberi instruction query. Backend cloud tetap memakai jalur yang kompatibel dengan API saat ini.

### 3. Satu jalur keyword search

Gunakan dense + BM25 sebagai hybrid retrieval. Hapus pemanggilan LanceDB FTS dari jalur query karena hasilnya saat ini tidak ikut fusion dan menduplikasi keyword search.

### 4. Cache BM25 di memori

BM25 dimuat sekali dan cache diinvalidasi setelah `index_vault()` membangun ulang indeks. Jika file BM25 rusak atau hilang, pencarian tetap berjalan dense-only dan mencatat warning.

### 5. Kandidat reranker lebih kecil

Fusion menghasilkan maksimal 10 kandidat unik untuk reranker, bukan minimal 20. Model reranker dipertahankan karena mendukung multilingual. Prewarm dilakukan melalui alur startup yang sudah ada tanpa thread/service baru.

### 6. Neighbor expansion

Sesudah top chunk terpilih, ambil maksimal satu chunk sebelum dan satu sesudahnya dari file yang sama. Tetangga hanya dipakai sebagai konteks, bukan menggantikan skor chunk utama. Duplikat dihapus dan total konteks dibatasi.

### 7. Relevance gate

Simpan skor reranker bersama hasil. Jika semua kandidat berada di bawah ambang yang ditentukan dari evaluasi lokal, kembalikan pesan bahwa data relevan tidak ditemukan. Ambang tidak ditebak; nilainya dipilih dari benchmark query Vault.

### 8. Schema simpan yang dipaksa oleh tool

`VaultSaveTool` menerima schema berikut:

```json
{
  "title": "judul catatan",
  "content": "isi catatan",
  "category": "Inbox|Riset|Proyek|Personal|Saham",
  "tags": ["tag-1", "tag-2"],
  "source": "Bima, Intel, Visual, atau URL sumber asli"
}
```

`title` dan `content` wajib berupa string nonkosong. Kategori di luar allowlist masuk `Inbox`; tags dibersihkan dan dibatasi; sumber kosong menjadi `Bima`. Folder dibuat hanya di bawah root Vault setelah validasi path.

### 9. Metadata dan nama stabil

Catatan baru memakai YAML frontmatter berisi `title`, `created`, `updated`, `category`, `tags`, `source`, dan `content_hash`. Nama file berasal dari slug judul yang stabil, bukan timestamp acak.

### 10. Deduplikasi dan update tanpa kehilangan data

- Hash isi yang sudah ada di Vault: skip.
- Judul ternormalisasi sama di folder mana pun, isi berbeda: backup file lalu tambahkan bagian update bertanggal ke file existing tanpa memindahkannya.
- Judul baru: buat file baru pada folder kategori.
- Jangan memindahkan atau menulis ulang 54 catatan existing secara otomatis.

### 11. Routing Arsip eksplisit

Data upstream hanya dianggap ada jika `temp_data.last_search_result` atau field hasil spesialis lain benar-benar terisi. Pesan Manager tidak dianggap sebagai data untuk disimpan. Permintaan pencarian tetap menggunakan `VaultSearchTool`.

Regex fast-path diperluas untuk bentuk natural seperti “apa isi catatan”, “ingat catatan”, dan perintah simpan singkat, tanpa menangkap percakapan umum.

### 12. Related-note block aman

Linker hanya mengganti blok yang dimiliki Anisa:

```markdown
<!-- anisa:related:start -->
### Catatan Terkait
...
<!-- anisa:related:end -->
```

Konten manual di luar marker tidak boleh dihapus. File tetap dibackup sebelum perubahan.

## Error Handling

- Dense search gagal: kembalikan error retrieval yang aman dan catat detail lokal.
- BM25 gagal: fallback dense-only.
- Reranker gagal: fallback urutan hybrid.
- Neighbor lookup gagal: tetap gunakan chunk utama.
- Re-index wajib dapat dibangun ulang dari Markdown tanpa kehilangan sumber.
- Category invalid: simpan ke `Inbox`, bukan gagal atau membuat folder bebas.
- Update file gagal setelah backup: file lama harus tetap utuh dan re-index tidak dijalankan.

## Verifikasi

Tambahkan pengujian untuk:

1. Metadata ikut dalam teks embedding, tetapi keluaran tetap memakai konten asli.
2. BM25 tidak dibaca ulang pada query kedua dan cache terinvalidasi setelah re-index.
3. FTS tidak dipanggil pada retrieval baru.
4. Reranker menerima maksimal 10 kandidat unik.
5. Neighbor expansion tidak menggandakan chunk dan tidak menyeberang file.
6. Fallback dense-only serta fallback tanpa reranker tetap bekerja.
7. Relevance gate menolak hasil lemah.
8. Save menolak title/content kosong dan membersihkan category/tags/source.
9. Save selalu berada di folder allowlist atau `Inbox`.
10. Content hash mencegah duplikat dan judul sama melakukan append setelah backup.
11. Manager message tidak memicu mode upstream-save; hasil Intel tetap memicunya.
12. Linker hanya mengganti blok marker dan mempertahankan konten manual setelahnya.

Benchmark lokal memakai sekumpulan query benar/salah dengan expected source. Catat p50/p95 latency hangat dan Recall@3 sebelum/sesudah. Target penerimaan:

- p95 retrieval hangat <= 3 detik.
- Recall@3 tidak turun dari baseline dan target meningkat.
- Query tanpa jawaban tidak menghasilkan konteks palsu.

## Di Luar Scope

- Migrasi ke SQLite-vec atau Qdrant.
- Mengganti model embedding/reranker.
- Migrasi, pemindahan, atau perubahan format 54 catatan Vault existing.
- Menghapus folder indeks lama sebelum benchmark dan persetujuan tindakan destruktif.
