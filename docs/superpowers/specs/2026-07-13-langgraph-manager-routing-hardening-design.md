# LangGraph Manager Routing Hardening Design

## Tujuan

Memperbaiki temuan `error_solutions.md` Log 73–77 tanpa mengganti arsitektur LangGraph, tanpa menambah dependency, dan tanpa menambah jumlah panggilan LLM untuk chat santai.

## Ruang Lingkup

- Memvalidasi 22 keputusan route manager secara fail-closed.
- Menghentikan pembuatan `AIMessage` tersembunyi pada route spesialis.
- Mencegah token/tag route manager bocor melalui stream progress global.
- Mencegah Admin/Seniman membaca pesan request lama sebagai output upstream.
- Memindahkan pembacaan SQLite sinkron di manager keluar dari event loop.
- Menghapus CrewAI manager lama dan target MCP yang tidak punya consumer runtime.
- Menambah regression test sebelum perubahan production.

## Bukan Ruang Lingkup

- Cost guardrail untuk seluruh `Crew.kickoff()`.
- Indirect prompt injection dari hasil web.
- MCP security gate di `main.py`.
- Blocking SQLite pada node selain manager.
- Memperluas regex fast-path ke bahasa natural yang ambigu.

## Keputusan Arsitektur

Manager tetap satu panggilan LLM karena sekitar 73% keputusan manager adalah chat `santai`. Memisahkan router dan chat menjadi dua node LLM akan menggandakan biaya dan latensi pada jalur yang paling sering dipakai.

```text
classifier_node
├── intent eksplisit → specialist_node
└── ambigu → manager_node (satu LLM call)
               ├── santai → AIMessage balasan → END
               └── spesialis → state route saja → specialist_node
```

Manager adalah router/chat fallback. Urutan kerja spesialis tetap deterministik di `core/langgraph_engine.py`.

## Kontrak Route

`core/langgraph_nodes/manager.py` memiliki satu mapping canonical dari nama route ke urutan tim:

- Single-team: `santai`, `intel`, `seniman`, `admin`, `visual`, `arsip`, `lifestyle`, `mekanik`, `saham`, `kodok`, `observer`.
- Multi-team: seluruh 11 kombinasi Intel/Arsip/Seniman/Admin yang sudah didukung graph.

Parser menerima tepat satu tag `[ROUTE: ...]`, case-insensitive, lalu memvalidasinya terhadap mapping. Kondisi berikut menghasilkan `ManagerRouteError`:

- Tag route hilang.
- Tag route lebih dari satu.
- Nama atau urutan route tidak dikenal.
- Route `santai` tidak memiliki isi balasan setelah tag dihapus.

Error diteruskan ke wrapper `make_resilient()`. Wrapper melakukan retry sesuai kebijakan yang sudah ada dan akhirnya mengirim pesan internal-safe bila dua percobaan gagal. Invalid output tidak boleh berubah diam-diam menjadi `santai`.

## Kontrak Output Manager

- Route `santai`: return `messages=[AIMessage(reply)]`, `active_teams=["santai"]`, `is_finished=True`.
- Route spesialis: return `active_teams=[...]`, `is_finished=False` tanpa update `messages`.
- Prompt diubah dari “20 pilihan” menjadi “22 pilihan”.
- Prompt meminta tag + balasan hanya untuk `santai`; route spesialis mengeluarkan tag saja.
- `run_langgraph_engine()` tidak meneruskan event stream dari `manager_node`; chat santai tetap dikirim lewat final state, sedangkan stream node spesialis tetap aktif.

## Proteksi Upstream Current-turn

Karena checkpoint menyimpan `messages` lintas request, Admin/Seniman tidak boleh memakai `messages[-1]` pada route langsung.

- Seniman membaca pesan terakhir hanya jika `active_teams` menunjukkan Intel atau Arsip sudah berjalan pada request aktif.
- Admin membaca pesan terakhir hanya jika `active_teams` menunjukkan Intel, Arsip, atau Seniman sudah berjalan pada request aktif.
- Route langsung mengandalkan `user_request`, `temp_data`, dan history fallback yang sudah ada.

Guard dibuat sebagai helper kecil yang bisa diuji, bukan berdasarkan isi teks pesan.

## Event-loop Safety

`get_recent_context(5)` dipanggil lewat `await asyncio.to_thread(...)` sebelum system prompt dibangun. Tidak ada perubahan pada format memori atau database.

## Penghapusan CrewAI Manager Mati

- Empat caller `simpan_sesi()` memakai `memory.memory_engine.add_session` secara langsung.
- Mapping `manager` di `core/agent_registry.py` dihapus.
- `teams/t1_manager.py` dihapus setelah semua caller dan registry bersih.
- `manager_llm` yang hanya dipakai agent lama dihapus dari `config.py`.
- MCP `sequential_thinking` dinonaktifkan dan dilepas dari target agent.
- Target/allowlist `manager` di MCP Memory dan Time dihapus; target aktif lain dipertahankan.

Tidak ada CrewAI hierarchical manager pengganti karena LangGraph sudah menjadi orkestrator production.

## Fast-path

Rasio fast-path rendah dicatat sebagai karakteristik classifier konservatif, bukan alasan menambah regex spekulatif. Perubahan ini tidak menambah pattern Admin/HTML/Intel baru karena request seperti “riset lalu buat PDF” mudah salah dipotong menjadi single-team.

Efisiensi diperoleh dengan memperkecil output manager pada route spesialis dan menghapus tool/agent mati.

## Pengujian

TDD dilakukan per perilaku:

1. Test 22 route valid gagal sebelum mapping/parser baru ada.
2. Test tag hilang, ganda, dan tidak dikenal gagal sebelum validasi baru ada.
3. Test route spesialis tidak menambah `messages`; route santai tetap menghasilkan reply.
4. Test stream event manager ditolak dan stream event spesialis diterima.
5. Test upstream guard menolak pesan lama pada route langsung dan menerima pesan pada route multi-team.
6. Test registry/config membuktikan tidak ada target MCP `manager` dan tidak ada import `teams.t1_manager`.
7. Focused pytest dijalankan setelah setiap siklus RED/GREEN.
8. Full pytest, syntax check file tersentuh, JSON parse `config_mcp.json`, dan `git diff --check` menjadi verification gate akhir.

## Risiko dan Mitigasi

- Model gagal mengikuti format tag: parser fail-closed dan wrapper retry.
- Admin/Seniman kehilangan konteks: route multi-team tetap boleh membaca output node sebelumnya; route langsung memakai request aktif.
- Import rusak setelah menghapus `t1_manager`: regression test mencari semua referensi dan smoke-import entrypoint terkait.
- Config MCP tidak valid: parse JSON dan test registry dijalankan sebelum restart.

## Kriteria Selesai

- Seluruh test baru terbukti RED lalu GREEN.
- Tidak ada fallback invalid route ke `santai`.
- Route spesialis tidak menambahkan pesan manager.
- Stream progress tidak mengekspos token route manager.
- Tidak ada consumer/import `teams.t1_manager`.
- Tidak ada MCP aktif yang menargetkan `manager`.
- Focused test dan full test lulus tanpa failure baru.
