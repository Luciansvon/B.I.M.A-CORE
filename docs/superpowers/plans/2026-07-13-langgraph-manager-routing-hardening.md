# LangGraph Manager Routing Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mengeraskan kontrak route LangGraph manager, menghentikan pesan manager tersembunyi, dan menghapus CrewAI manager/MCP mati tanpa menambah panggilan LLM atau dependency.

**Architecture:** Pertahankan classifier konservatif dan satu LLM call pada fallback manager. Manager memvalidasi satu dari 22 route melalui mapping canonical; hanya route `santai` menghasilkan `AIMessage`, sedangkan route spesialis hanya memperbarui state. Admin/Seniman membaca pesan sebelumnya hanya bila graph request aktif memang memiliki tim upstream.

**Tech Stack:** Python 3.12, LangGraph, LangChain `AIMessage`, pytest, CrewAI existing runtime, JSON MCP config.

---

## Safety Constraints

- Worktree sudah memiliki banyak perubahan milik Bima; jangan reset, checkout, stage, commit, atau push.
- Jangan install/remove dependency dan jangan mengubah `.env`.
- Edit hanya file yang tercantum pada PLAN ini.
- Satu siklus RED→GREEN per task; jangan menumpuk beberapa fix sebelum test terkait lulus.
- Jika test gagal karena sebab di luar expected RED, berhenti dan investigasi; jangan auto-patch.
- Restart production hanya setelah focused test, full pytest, syntax, dan config validation lulus.

## File Map

- Create: `tests/test_manager_routing.py` — kontrak parser, output node, dan upstream guard.
- Modify: `core/langgraph_nodes/manager.py` — mapping route, parser fail-closed, route-only specialist output, SQLite offload.
- Modify: `core/langgraph_engine.py` — blokir token manager dari stream user-facing.
- Modify: `core/langgraph_nodes/state.py` — helper current-turn upstream.
- Modify: `core/langgraph_nodes/admin.py` — konsumsi upstream terjaga.
- Modify: `core/langgraph_nodes/seniman.py` — konsumsi upstream terjaga.
- Modify: `tests/test_agent_registry.py` — regression legacy manager/MCP.
- Modify: `core/discord_bot.py` — simpan sesi langsung.
- Modify: `core/wa_server.py` — simpan sesi langsung.
- Modify: `core/dashboard_server.py` — simpan sesi langsung.
- Modify: `core/furniture_qc.py` — simpan sesi QC langsung.
- Modify: `core/agent_registry.py` — hapus registry manager mati.
- Modify: `config.py` — hapus `manager_llm` mati.
- Modify: `config_mcp.json` — nonaktifkan Sequential Thinking dan hapus target manager.
- Delete: `teams/t1_manager.py` — CrewAI manager yang tidak pernah dieksekusi.
- Modify: `error_solutions.md` — catat status dan bukti verifikasi.

### Task 1: Canonical Route Parser

**Files:**
- Create: `tests/test_manager_routing.py`
- Modify: `core/langgraph_nodes/manager.py`

- [ ] **Step 1: Tulis test mapping 22 route dan invalid output**

```python
import pytest

import core.langgraph_nodes.manager as manager


EXPECTED_ROUTES = {
    "santai": ["santai"],
    "intel": ["intel"],
    "seniman": ["seniman"],
    "admin": ["admin"],
    "visual": ["visual"],
    "arsip": ["arsip"],
    "lifestyle": ["lifestyle"],
    "mekanik": ["mekanik"],
    "saham": ["saham"],
    "kodok": ["kodok"],
    "observer": ["observer"],
    "seniman+admin": ["seniman", "admin"],
    "arsip+seniman": ["arsip", "seniman"],
    "arsip+admin": ["arsip", "admin"],
    "arsip+seniman+admin": ["arsip", "seniman", "admin"],
    "intel+seniman": ["intel", "seniman"],
    "intel+admin": ["intel", "admin"],
    "intel+arsip": ["intel", "arsip"],
    "intel+seniman+admin": ["intel", "seniman", "admin"],
    "intel+arsip+seniman": ["intel", "arsip", "seniman"],
    "intel+arsip+admin": ["intel", "arsip", "admin"],
    "intel+arsip+seniman+admin": ["intel", "arsip", "seniman", "admin"],
}


def test_manager_route_table_is_complete() -> None:
    assert getattr(manager, "ROUTE_TEAMS") == EXPECTED_ROUTES


@pytest.mark.parametrize("route, teams", EXPECTED_ROUTES.items())
def test_parse_manager_output_accepts_every_route(route: str, teams: list[str]) -> None:
    suffix = "\nHalo Bima" if route == "santai" else ""
    parsed_route, parsed_teams, reply = manager.parse_manager_output(
        f"[ROUTE: {route.upper()}]{suffix}"
    )

    assert parsed_route == route
    assert parsed_teams == teams
    assert reply == ("Halo Bima" if route == "santai" else "")


@pytest.mark.parametrize(
    "raw",
    [
        "tidak ada tag",
        "[ROUTE: unknown]",
        "[ROUTE: intel]\n[ROUTE: admin]",
        "[ROUTE: santai]",
    ],
)
def test_parse_manager_output_rejects_invalid_contract(raw: str) -> None:
    error_type = getattr(manager, "ManagerRouteError")
    with pytest.raises(error_type):
        manager.parse_manager_output(raw)
```

- [ ] **Step 2: Jalankan test dan pastikan RED karena kontrak belum ada**

Run:

```bash
bima_env/bin/python -m pytest tests/test_manager_routing.py -q
```

Expected: FAIL pada `ROUTE_TEAMS`, `parse_manager_output`, atau `ManagerRouteError` yang belum tersedia; bukan collection/import error dependency.

- [ ] **Step 3: Tambahkan mapping dan parser minimum**

Tambahkan di `core/langgraph_nodes/manager.py` setelah logger:

```python
ROUTE_TEAMS = {
    "santai": ["santai"],
    "intel": ["intel"],
    "seniman": ["seniman"],
    "admin": ["admin"],
    "visual": ["visual"],
    "arsip": ["arsip"],
    "lifestyle": ["lifestyle"],
    "mekanik": ["mekanik"],
    "saham": ["saham"],
    "kodok": ["kodok"],
    "observer": ["observer"],
    "seniman+admin": ["seniman", "admin"],
    "arsip+seniman": ["arsip", "seniman"],
    "arsip+admin": ["arsip", "admin"],
    "arsip+seniman+admin": ["arsip", "seniman", "admin"],
    "intel+seniman": ["intel", "seniman"],
    "intel+admin": ["intel", "admin"],
    "intel+arsip": ["intel", "arsip"],
    "intel+seniman+admin": ["intel", "seniman", "admin"],
    "intel+arsip+seniman": ["intel", "arsip", "seniman"],
    "intel+arsip+admin": ["intel", "arsip", "admin"],
    "intel+arsip+seniman+admin": ["intel", "arsip", "seniman", "admin"],
}

_ROUTE_TAG = re.compile(r"\[ROUTE:\s*([a-z]+(?:\+[a-z]+)*)\]", re.IGNORECASE)


class ManagerRouteError(ValueError):
    """LLM manager mengembalikan route di luar kontrak graph."""


def parse_manager_output(content: str) -> tuple[str, list[str], str]:
    matches = _ROUTE_TAG.findall(content or "")
    if len(matches) != 1:
        raise ManagerRouteError(f"expected one route tag, got {len(matches)}")

    route = matches[0].lower()
    teams = ROUTE_TEAMS.get(route)
    if teams is None:
        raise ManagerRouteError(f"unknown route: {route}")

    reply = _ROUTE_TAG.sub("", content, count=1).strip()
    if route == "santai" and not reply:
        raise ManagerRouteError("santai route requires a reply")
    return route, list(teams), reply
```

Hapus import `Literal` yang tidak dipakai. Jangan ubah `manager_node()` pada task ini.

- [ ] **Step 4: Jalankan test dan pastikan GREEN**

```bash
bima_env/bin/python -m pytest tests/test_manager_routing.py -q
```

Expected: seluruh test Task 1 PASS.

### Task 2: Manager Route-only Output dan SQLite Offload

**Files:**
- Modify: `tests/test_manager_routing.py`
- Modify: `core/langgraph_nodes/manager.py`
- Modify: `core/langgraph_engine.py`

- [ ] **Step 1: Tambahkan test node specialist, santai, dan thread offload**

```python
import asyncio
import threading
from types import SimpleNamespace


class FakeStreamingLLM:
    def __init__(self, output: str):
        self.output = output

    async def astream(self, _messages):
        yield SimpleNamespace(content=self.output)


def run_manager(monkeypatch, output: str):
    main_thread = threading.get_ident()
    memory_threads: list[int] = []

    async def no_progress(_state, _message):
        return None

    async def empty_recall(_query, _limit):
        return ""

    def recent_context(_limit):
        memory_threads.append(threading.get_ident())
        return "histori test"

    monkeypatch.setattr(manager, "default_llm", FakeStreamingLLM(output))
    monkeypatch.setattr(manager, "notify_progress", no_progress)
    monkeypatch.setattr(manager.agentmemory_client, "recall", empty_recall)
    monkeypatch.setattr(manager, "get_recent_context", recent_context)

    result = asyncio.run(
        manager.manager_node(
            {
                "messages": [],
                "user_request": "test request",
                "realtime_context": "",
            }
        )
    )
    return result, main_thread, memory_threads


def test_specialist_route_does_not_add_hidden_message(monkeypatch) -> None:
    result, main_thread, memory_threads = run_manager(
        monkeypatch,
        "[ROUTE: intel]\nnarasi yang harus dibuang",
    )

    assert result == {"active_teams": ["intel"], "is_finished": False}
    assert memory_threads and memory_threads[0] != main_thread


def test_santai_route_returns_only_clean_reply(monkeypatch) -> None:
    result, _, _ = run_manager(monkeypatch, "[ROUTE: santai]\nHalo Bima")

    assert result["active_teams"] == ["santai"]
    assert result["is_finished"] is True
    assert len(result["messages"]) == 1
    assert result["messages"][0].content == "Halo Bima"


def test_manager_stream_event_is_not_user_facing() -> None:
    import core.langgraph_engine as engine

    manager_event = {"metadata": {"langgraph_node": "manager_node"}}
    intel_event = {"metadata": {"langgraph_node": "intel_node"}}

    assert engine.is_user_facing_stream_event(manager_event) is False
    assert engine.is_user_facing_stream_event(intel_event) is True
```

- [ ] **Step 2: Jalankan test dan pastikan RED pada pesan tersembunyi/offload**

```bash
bima_env/bin/python -m pytest tests/test_manager_routing.py -q
```

Expected: specialist result masih memiliki `messages` dan `get_recent_context()` masih berjalan pada thread event loop.

- [ ] **Step 3: Refactor `manager_node()` minimum**

Sebelum membangun `system_prompt`:

```python
recent_context = await asyncio.to_thread(get_recent_context, 5)
```

Ganti interpolasi SQLite inline menjadi:

```python
{compress_context(recent_context, target_ratio=0.5)}
```

Ubah instruksi output prompt menjadi:

```text
FORMAT OUTPUT WAJIB:
- Kalau route `santai`: baris pertama `[ROUTE: santai]`, lalu balasan untuk Bima.
- Kalau route spesialis: keluarkan tepat satu tag `[ROUTE: ...]` tanpa narasi lain.
- Pilih tepat satu dari 22 route di atas.
```

Ganti seluruh blok parser `if/elif`, fallback empty-content, dan return lama dengan:

```python
route, active_teams, reply = parse_manager_output(raw_content)
logger.info(
    f"[LANGGRAPH MANAGER] Keputusan rute: {route.upper()} | "
    f"Tim aktif: {active_teams}"
)

update = {
    "active_teams": active_teams,
    "is_finished": route == "santai",
}
if route == "santai":
    update["messages"] = [AIMessage(content=reply)]
return update
```

Hapus variabel `messages`, `response`, `content`, `upper_content`, dan `next_route` yang tidak lagi dipakai. Pertahankan `AIMessage` untuk cabang santai.

Tambahkan helper kecil di `core/langgraph_engine.py`:

```python
def is_user_facing_stream_event(event: dict) -> bool:
    metadata = event.get("metadata", {}) or {}
    return metadata.get("langgraph_node") != "manager_node"
```

Pada cabang `on_chat_model_stream`, sebelum mengambil chunk:

```python
if not is_user_facing_stream_event(event):
    continue
```

Filter dilakukan sebelum `stream_buffer += token` dan `emit('llm_token', ...)`. Jangan menonaktifkan stream node spesialis.

- [ ] **Step 4: Jalankan focused test dan pastikan GREEN**

```bash
bima_env/bin/python -m pytest tests/test_manager_routing.py -q
```

Expected: seluruh test Task 1–2 PASS.

### Task 3: Current-turn Upstream Guard

**Files:**
- Modify: `tests/test_manager_routing.py`
- Modify: `core/langgraph_nodes/state.py`
- Modify: `core/langgraph_nodes/admin.py`
- Modify: `core/langgraph_nodes/seniman.py`

- [ ] **Step 1: Tambahkan test helper upstream**

```python
from langchain_core.messages import AIMessage
import core.langgraph_nodes.state as state_module


@pytest.mark.parametrize("target", ["admin", "seniman"])
def test_direct_route_rejects_stale_upstream_message(target: str) -> None:
    helper = getattr(state_module, "get_current_upstream_text")
    state = {
        "active_teams": [target],
        "messages": [AIMessage(content="STALE REQUEST LAMA")],
    }

    assert helper(state, target) == ""


@pytest.mark.parametrize(
    "active_teams, target",
    [
        (["intel", "seniman"], "seniman"),
        (["arsip", "seniman"], "seniman"),
        (["intel", "admin"], "admin"),
        (["arsip", "admin"], "admin"),
        (["seniman", "admin"], "admin"),
    ],
)
def test_multiteam_route_accepts_current_upstream_message(
    active_teams: list[str], target: str
) -> None:
    helper = getattr(state_module, "get_current_upstream_text")
    state = {
        "active_teams": active_teams,
        "messages": [AIMessage(content="HASIL REQUEST AKTIF")],
    }

    assert helper(state, target) == "HASIL REQUEST AKTIF"
```

- [ ] **Step 2: Jalankan test dan pastikan RED karena helper belum ada**

```bash
bima_env/bin/python -m pytest tests/test_manager_routing.py -q
```

Expected: FAIL pada `get_current_upstream_text` yang belum tersedia.

- [ ] **Step 3: Implement helper dan pakai di dua consumer**

Tambahkan setelah `BimaState` di `core/langgraph_nodes/state.py`:

```python
_UPSTREAM_TEAMS = {
    "seniman": frozenset({"intel", "arsip"}),
    "admin": frozenset({"intel", "arsip", "seniman"}),
}


def get_current_upstream_text(
    state: BimaState,
    target_team: str,
    max_chars: int = 2500,
) -> str:
    allowed = _UPSTREAM_TEAMS.get(target_team, frozenset())
    if not allowed.intersection(state.get("active_teams", [])):
        return ""

    messages = state.get("messages", []) or []
    if not messages:
        return ""
    last = messages[-1]
    return (getattr(last, "content", "") or str(last))[:max_chars].strip()
```

Di `admin.py` dan `seniman.py`, import helper lalu ganti pembacaan `prev_messages[-1]` dengan:

```python
upstream_text = get_current_upstream_text(state, "admin")  # admin.py
```

```python
upstream_text = get_current_upstream_text(state, "seniman")  # seniman.py
```

Bangun `upstream_block` hanya jika `upstream_text` tidak kosong. Jangan ubah `temp_data`, history fallback, atau prompt lain.

- [ ] **Step 4: Jalankan focused test dan pastikan GREEN**

```bash
bima_env/bin/python -m pytest tests/test_manager_routing.py -q
```

Expected: seluruh test Task 1–3 PASS.

### Task 4: Hapus CrewAI Manager dan MCP Mati

**Files:**
- Modify: `tests/test_agent_registry.py`
- Modify: `core/discord_bot.py`
- Modify: `core/wa_server.py`
- Modify: `core/dashboard_server.py`
- Modify: `core/furniture_qc.py`
- Modify: `core/agent_registry.py`
- Modify: `config.py`
- Modify: `config_mcp.json`
- Delete: `teams/t1_manager.py`

- [ ] **Step 1: Tambahkan regression test legacy manager**

Tambahkan ke `tests/test_agent_registry.py`:

```python
def test_legacy_manager_has_no_registry_or_mcp_target() -> None:
    config = json.loads((PROJECT_ROOT / "config_mcp.json").read_text(encoding="utf-8"))

    assert "manager" not in AGENT_REGISTRY
    assert all(
        "manager" not in server.get("attach_to", [])
        for server in config["servers"]
    )
    assert all(
        "manager" not in server.get("tool_allowlist_by_agent", {})
        for server in config["servers"]
    )


def test_legacy_manager_module_and_imports_are_removed() -> None:
    assert not (PROJECT_ROOT / "teams/t1_manager.py").exists()

    callers = [
        "core/discord_bot.py",
        "core/wa_server.py",
        "core/dashboard_server.py",
        "core/furniture_qc.py",
    ]
    for relative_path in callers:
        source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert "teams.t1_manager" not in source
```

- [ ] **Step 2: Jalankan test dan pastikan RED pada manager legacy**

```bash
bima_env/bin/python -m pytest tests/test_agent_registry.py -q
```

Expected: FAIL karena registry, MCP targets, module, dan caller lama masih ada.

- [ ] **Step 3: Pindahkan empat caller langsung ke `add_session`**

Ganti setiap import `teams.t1_manager.simpan_sesi` dengan:

```python
from memory.memory_engine import add_session
```

Ganti call:

```python
add_session(perintah, hasil)
```

Gunakan argumen lokal yang sama pada masing-masing caller:

- Discord: `add_session(perintah_lengkap, hasil_str)`.
- WhatsApp: `add_session(perintah, hasil)`.
- Dashboard: `add_session(command, hasil)`.
- Furniture QC: `add_session(perintah, hasil)`.

Pertahankan wrapper `try/except` best-effort yang sudah ada.

- [ ] **Step 4: Hapus registry, LLM, file agent, dan target MCP mati**

- Hapus entry `"manager": "teams.t1_manager:manager_agent"` dari `AGENT_REGISTRY`.
- Hapus comment/assignment `manager_llm` dari `config.py`; jangan ubah LLM spesialis.
- Hapus `teams/t1_manager.py` memakai `apply_patch`.
- Ubah server Sequential Thinking menjadi:

```json
{
  "name": "sequential_thinking",
  "description": "Sequential Thinking — DISABLED karena CrewAI manager lama sudah dihapus dan tidak ada consumer runtime.",
  "enabled": false,
  "transport": "stdio",
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-sequential-thinking@2026.7.4"],
  "env": {},
  "tools": null,
  "attach_to": [],
  "requires_bin": "npx"
}
```

- Pada `memory_anthropic`, sisakan allowlist `arsip` dan `attach_to: ["arsip"]`.
- Pada `time`, gunakan `attach_to: ["saham", "lifestyle"]`.

- [ ] **Step 5: Jalankan registry test dan JSON validation**

```bash
bima_env/bin/python -m pytest tests/test_agent_registry.py -q
bima_env/bin/python -m json.tool config_mcp.json
```

Expected: registry tests PASS dan JSON parser exit 0.

- [ ] **Step 6: Pastikan tidak ada referensi legacy tersisa**

```bash
rg -n -e teams.t1_manager -e manager_agent -e manager_llm core teams tests config.py main.py
```

Expected: tidak ada match. Jika ada match baru, berhenti dan telusuri caller; jangan hapus buta.

### Task 5: Verification, Documentation, dan Production Smoke

**Files:**
- Modify: `error_solutions.md`

- [ ] **Step 1: Jalankan focused regression suite**

```bash
bima_env/bin/python -m pytest tests/test_manager_routing.py tests/test_agent_registry.py tests/test_arsip_routing.py -q
```

Expected: seluruh test PASS, 0 failure.

- [ ] **Step 2: Jalankan syntax/import checks file tersentuh**

```bash
bima_env/bin/python -m py_compile core/langgraph_engine.py core/langgraph_nodes/manager.py core/langgraph_nodes/state.py core/langgraph_nodes/admin.py core/langgraph_nodes/seniman.py core/discord_bot.py core/wa_server.py core/dashboard_server.py core/furniture_qc.py core/agent_registry.py config.py tests/test_manager_routing.py tests/test_agent_registry.py
bima_env/bin/python -c "from core.langgraph_nodes.manager import manager_node, parse_manager_output; from core.langgraph_engine import run_langgraph_engine; print('imports OK')"
```

Expected: exit 0 dan `imports OK`.

- [ ] **Step 3: Jalankan full suite**

```bash
bima_env/bin/python -m pytest -q
```

Expected: 0 failure. Jika ada failure, laporkan output dan jangan restart production atau mengubah test agar hijau.

- [ ] **Step 4: Audit diff tanpa mengganggu perubahan Bima**

```bash
git diff --ignore-space-at-eol --check -- core/langgraph_engine.py core/langgraph_nodes/manager.py core/langgraph_nodes/state.py core/langgraph_nodes/admin.py core/langgraph_nodes/seniman.py core/discord_bot.py core/wa_server.py core/dashboard_server.py core/furniture_qc.py core/agent_registry.py config.py config_mcp.json tests/test_manager_routing.py tests/test_agent_registry.py
git diff --stat -- core/langgraph_engine.py core/langgraph_nodes/manager.py core/langgraph_nodes/state.py core/langgraph_nodes/admin.py core/langgraph_nodes/seniman.py core/discord_bot.py core/wa_server.py core/dashboard_server.py core/furniture_qc.py core/agent_registry.py config.py config_mcp.json teams/t1_manager.py tests/test_manager_routing.py tests/test_agent_registry.py
```

Expected: diff-check exit 0; stat hanya mencakup file scope. Jangan stage/commit.

- [ ] **Step 5: Catat hasil faktual**

Tambahkan status verifikasi ke `error_solutions.md` hanya setelah command di atas selesai. Catat jumlah test aktual, file yang dihapus, MCP yang dinonaktifkan, dan command yang benar-benar dijalankan; jangan menulis klaim sebelum ada output.

- [ ] **Step 6: Restart backend dan smoke production**

```bash
pm2 restart anisa-v3 --update-env
pm2 logs anisa-v3 --nostream --lines 120
bima_env/bin/python scripts/healthcheck.py
```

Expected:

- `anisa-v3` status online.
- Tidak ada `[mcp_client] 'sequential_thinking' ... started` pada startup baru.
- Tidak ada `[mcp_inject] manager` pada startup baru.
- Healthcheck tidak memiliki critical failure baru.

Jika restart atau healthcheck gagal, simpan log ke `error_solutions.md`, jangan auto-patch, dan laporkan blocker ke Bima.

### Addendum: Stale MCP Hardening Contract

**Ditemukan saat full-suite verification:** `tests/test_mcp_hardening.py::test_manager_memory_tools_are_read_only` masih mewajibkan allowlist MCP untuk CrewAI manager yang dihapus pada Task 4.

**Files:**
- Modify: `tests/test_mcp_hardening.py`

- [ ] Ganti kontrak lama dengan regression test bahwa `manager` tidak ada pada `memory_anthropic.tool_allowlist_by_agent` maupun `attach_to`, dan `sequential_thinking` tetap disabled tanpa target manager.
- [ ] Jalankan `bima_env/bin/python -m pytest tests/test_mcp_hardening.py tests/test_agent_registry.py -q`.
- [ ] Ulang full suite; hasil yang diterima hanya enam failure Marp baseline yang sudah disetujui Bima.
