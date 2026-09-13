# BIMA_CORE P0 Security Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Menutup seluruh temuan P0 audit: path traversal/exfiltration, kebocoran checkpoint antar-user, collision callback Discord, dan XSS activity log.

**Architecture:** Satu helper stdlib menangani path trust boundary; satu pembentuk thread ID dipakai engine dan callback registry; frontend merender log sebagai text node. `source_channel` tetap menyimpan jenis channel, sedangkan `conversation_id` menyimpan scope chat/channel nyata.

**Tech Stack:** Python 3.12, pathlib, FastAPI/Pydantic, LangGraph, pytest, Node.js syntax check, React JSX.

**Dirty-worktree policy:** Jangan commit file implementasi karena beberapa target sudah berisi perubahan uncommitted Bima. Gunakan diff terarah dan jangan stage file yang overlap.

---

## File Map

- Create `core/path_security.py`: helper sanitasi output dan confinement input.
- Create `tests/test_p0_path_security.py`: regression path traversal dan exfiltration.
- Modify `teams/t4_admin/excel_tool.py`: output `.xlsx` aman.
- Modify `teams/t4_admin/pdf_tool.py`: output `.pdf` aman.
- Modify `teams/t4_admin/word_tool.py`: output `.docx` aman.
- Modify `tools/code_visualizer.py`: scan hanya di workspace.
- Modify `tools/image_gen_tool.py`: reference image hanya dari `outputs/`.
- Create `tests/test_p0_thread_isolation.py`: regression thread/callback isolation.
- Modify `core/langgraph_nodes/state.py`: `conversation_id` dan pembentuk thread ID tunggal.
- Modify `core/langgraph_engine.py`: thread/checkpoint/callback memakai user + conversation.
- Modify `core/wa_server.py`: sender WhatsApp wajib diteruskan ke engine.
- Modify `whatsapp/index.js`: kirim `sender_id` ke bridge.
- Modify `core/discord_bot.py`: kirim channel/DM ID nyata.
- Create `tests/test_p0_dashboard_xss.py`: regression activity-log XSS.
- Modify `dashboard/guild-panels.jsx`: render activity log sebagai text node.
- Modify `dashboard/guild-app.jsx`: hilangkan HTML markup dari data log internal.
- Modify `dashboard/guild-data.jsx`: ubah simulated log template menjadi plain text.
- Modify `error_solutions.md`: catat root cause, dampak, dan pencegahan P0 setelah test lulus.

### Task 1: Shared Path Security Helper

**Files:**
- Create: `core/path_security.py`
- Create: `tests/test_p0_path_security.py`

- [x] **Step 1: Write failing helper tests**

```python
from pathlib import Path

import pytest

from core.path_security import resolve_allowed_path, safe_output_path


def test_safe_output_path_keeps_traversal_inside_root(tmp_path: Path) -> None:
    output = tmp_path / "outputs"
    output.mkdir()

    result = safe_output_path(
        output,
        "../../../../home/bima/.bashrc",
        default_stem="dokumen",
        suffix=".pdf",
        timestamp="20260712_120000",
    )

    assert result.parent == output.resolve()
    assert result.name == "bashrc_20260712_120000.pdf"


def test_resolve_allowed_path_rejects_absolute_outside_root(tmp_path: Path) -> None:
    allowed = tmp_path / "outputs"
    allowed.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"not-an-image")

    with pytest.raises(ValueError, match="Path tidak diizinkan"):
        resolve_allowed_path(secret, (allowed,), allowed_suffixes={".png"})


def test_resolve_allowed_path_rejects_symlink_escape(tmp_path: Path) -> None:
    allowed = tmp_path / "outputs"
    allowed.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"secret")
    link = allowed / "reference.png"
    link.symlink_to(secret)

    with pytest.raises(ValueError, match="Path tidak diizinkan"):
        resolve_allowed_path(link, (allowed,), allowed_suffixes={".png"})


def test_resolve_allowed_path_accepts_existing_file_in_root(tmp_path: Path) -> None:
    allowed = tmp_path / "outputs"
    allowed.mkdir()
    image = allowed / "reference.png"
    image.write_bytes(b"image")

    result = resolve_allowed_path(image, (allowed,), allowed_suffixes={".png"})

    assert result == image.resolve()
```

- [x] **Step 2: Run RED test**

Run:

```bash
source bima_env/bin/activate
pytest tests/test_p0_path_security.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'core.path_security'`.

- [x] **Step 3: Implement the minimal helper**

```python
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable


_UNSAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._ -]+")
_KNOWN_DOCUMENT_SUFFIXES = (".pdf", ".docx", ".xlsx")


def safe_output_path(
    root: Path,
    requested_name: object,
    *,
    default_stem: str,
    suffix: str,
    timestamp: str,
) -> Path:
    root = root.resolve()
    raw = str(requested_name or "").strip().replace("\\", "/")
    leaf = raw.rsplit("/", 1)[-1]
    for known_suffix in _KNOWN_DOCUMENT_SUFFIXES:
        if leaf.lower().endswith(known_suffix):
            leaf = leaf[: -len(known_suffix)]
            break
    stem = _UNSAFE_FILENAME_CHARS.sub("_", leaf).strip(" ._-")
    if not stem:
        stem = default_stem
    stem = stem[:80]
    candidate = (root / f"{stem}_{timestamp}{suffix}").resolve()
    if candidate.parent != root:
        raise ValueError("Path tidak diizinkan")
    return candidate


def resolve_allowed_path(
    candidate: str | os.PathLike[str],
    allowed_roots: Iterable[Path],
    *,
    base_dir: Path | None = None,
    allowed_suffixes: set[str] | None = None,
) -> Path:
    roots = tuple(root.resolve() for root in allowed_roots)
    if not roots:
        raise ValueError("Path tidak diizinkan")

    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = (base_dir or Path.cwd()) / path
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Path tidak diizinkan") from exc

    if not any(resolved == root or root in resolved.parents for root in roots):
        raise ValueError("Path tidak diizinkan")
    if allowed_suffixes is not None and resolved.suffix.lower() not in allowed_suffixes:
        raise ValueError("Path tidak diizinkan")
    return resolved
```

- [x] **Step 4: Run GREEN test**

Run: `pytest tests/test_p0_path_security.py -q`  
Expected: `4 passed`.

### Task 2: Constrain Admin Document Output

**Files:**
- Modify: `teams/t4_admin/excel_tool.py:1-10,117-119`
- Modify: `teams/t4_admin/pdf_tool.py:1-10,600-602`
- Modify: `teams/t4_admin/word_tool.py:1-10,492-494`
- Test: `tests/test_p0_path_security.py`

- [x] **Step 1: Add failing parameterized filename expectations**

Append:

```python
@pytest.mark.parametrize(
    ("requested", "suffix"),
    [
        ("../../outside", ".xlsx"),
        ("/etc/passwd", ".pdf"),
        (r"..\..\Windows\win.ini", ".docx"),
    ],
)
def test_document_output_names_cannot_change_parent(
    tmp_path: Path,
    requested: str,
    suffix: str,
) -> None:
    output = tmp_path / "outputs"
    output.mkdir()

    result = safe_output_path(
        output,
        requested,
        default_stem="dokumen",
        suffix=suffix,
        timestamp="20260712_120000",
    )

    assert result.parent == output.resolve()
    assert ".." not in result.name
```

- [x] **Step 2: Run test and confirm current integration is still absent**

Run:

```bash
pytest tests/test_p0_path_security.py -q
rg -n 'filepath = OUTPUT_DIR / filename' teams/t4_admin/{excel_tool,pdf_tool,word_tool}.py
```

Expected: helper test passes, while `rg` still finds all three unsafe joins. This is the integration RED evidence.

- [x] **Step 3: Replace each unsafe join**

Add to all three modules:

```python
from core.path_security import safe_output_path
```

Excel:

```python
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filepath = safe_output_path(
    OUTPUT_DIR,
    data.get("filename"),
    default_stem="laporan",
    suffix=".xlsx",
    timestamp=timestamp,
)
filename = filepath.name
```

PDF:

```python
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filepath = safe_output_path(
    OUTPUT_DIR,
    data.get("filename"),
    default_stem="dokumen",
    suffix=".pdf",
    timestamp=timestamp,
)
filename = filepath.name
```

Word:

```python
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
filepath = safe_output_path(
    OUTPUT_DIR,
    data.get("filename"),
    default_stem="dokumen",
    suffix=".docx",
    timestamp=timestamp,
)
filename = filepath.name
```

- [x] **Step 4: Verify helper integration and admin regressions**

Run:

```bash
! rg -n 'filepath = OUTPUT_DIR / filename' teams/t4_admin/{excel_tool,pdf_tool,word_tool}.py
pytest tests/test_p0_path_security.py tests/test_admin.py tests/test_admin_styles.py -q
```

Expected: unsafe join search returns no match; tests pass.

### Task 3: Constrain Code Visualizer and Image References

**Files:**
- Modify: `tools/code_visualizer.py:10-40`
- Modify: `tools/image_gen_tool.py:55-83`
- Modify: `tests/test_code_visualizer.py`
- Modify: `tests/test_p0_path_security.py`

- [x] **Step 1: Write failing integration tests**

Append to `tests/test_code_visualizer.py`:

```python
def test_codebase_visualizer_rejects_path_outside_workspace(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.py").write_text("SECRET = 'do-not-read'", encoding="utf-8")

    result = CodebaseVisualizerTool()._run(str(outside))

    assert result == "FAILED|Direktori tidak diizinkan."
```

Append to `tests/test_p0_path_security.py`:

```python
def test_image_gen_rejects_reference_outside_outputs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools import image_gen_tool

    output = tmp_path / "outputs"
    output.mkdir()
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"secret")
    monkeypatch.setattr(image_gen_tool, "_OUTPUT_DIR", output)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    result = image_gen_tool.ImageGenTool()._run("buat variasi", [str(secret)])

    assert result == "FAILED|Reference image tidak diizinkan"
```

- [x] **Step 2: Run RED tests**

Run:

```bash
pytest tests/test_code_visualizer.py::test_codebase_visualizer_rejects_path_outside_workspace \
  tests/test_p0_path_security.py::test_image_gen_rejects_reference_outside_outputs -q
```

Expected: visualizer returns success and image generator proceeds beyond confinement instead of returning the expected failure.

- [x] **Step 3: Apply confinement in both tools**

`tools/code_visualizer.py`:

```python
from core.path_security import resolve_allowed_path

# inside _run
base_path = Path(__file__).resolve().parent.parent
try:
    scan_dir = resolve_allowed_path(
        target_dir,
        (base_path,),
        base_dir=base_path,
    )
except ValueError:
    logger.warning("[CODE_VIS] Tolak target di luar workspace")
    return "FAILED|Direktori tidak diizinkan."
if not scan_dir.is_dir():
    return "FAILED|Direktori tidak ditemukan."
```

`tools/image_gen_tool.py`, before opening each reference:

```python
from core.path_security import resolve_allowed_path

# inside the reference loop
try:
    safe_img_path = resolve_allowed_path(
        img_path,
        (_OUTPUT_DIR,),
        base_dir=_OUTPUT_DIR.parent,
        allowed_suffixes=set(_MIME_MAP),
    )
except ValueError:
    logger.warning("[IMAGE_GEN] Tolak reference image di luar outputs")
    return "FAILED|Reference image tidak diizinkan"

try:
    mime = _guess_mime(str(safe_img_path))
    with safe_img_path.open("rb") as handle:
        b64 = base64.b64encode(handle.read()).decode()
    content_parts.append({
        "type": "image_url",
        "image_url": {"url": f"data:{mime};base64,{b64}"},
    })
    ref_used.append(str(safe_img_path))
except OSError:
    logger.exception("[IMAGE_GEN] Gagal membaca reference image")
    return "FAILED|Reference image gagal dibaca"
```

- [x] **Step 4: Run GREEN tests**

Run:

```bash
pytest tests/test_p0_path_security.py tests/test_code_visualizer.py -q
```

Expected: all tests pass and no external API call occurs for the rejected image.

### Task 4: Unify Thread and Callback Identity

**Files:**
- Modify: `core/langgraph_nodes/state.py:1-75`
- Modify: `core/langgraph_engine.py:328-365`
- Create: `tests/test_p0_thread_isolation.py`

- [x] **Step 1: Write failing thread identity tests**

```python
from core.langgraph_nodes.state import build_thread_id


def test_whatsapp_senders_get_distinct_thread_ids() -> None:
    first = build_thread_id("628111", "whatsapp", "628111")
    second = build_thread_id("628222", "whatsapp", "628222")

    assert first != second


def test_discord_channels_get_distinct_thread_ids_for_same_user() -> None:
    first = build_thread_id("123", "discord", "channel-1")
    second = build_thread_id("123", "discord", "channel-2")

    assert first != second


def test_legacy_call_has_stable_fallback_scope() -> None:
    assert build_thread_id("123", "discord", "") == "discord:123:discord"
```

- [x] **Step 2: Run RED test**

Run: `pytest tests/test_p0_thread_isolation.py -q`  
Expected: import fails because `build_thread_id` does not exist.

- [x] **Step 3: Add one canonical builder and state field**

`core/langgraph_nodes/state.py`:

```python
def build_thread_id(
    user_id: str = "",
    source_channel: str = "",
    conversation_id: str = "",
) -> str:
    user = user_id or "anon"
    channel = source_channel or "unknown"
    conversation = conversation_id or channel
    return f"{channel}:{user}:{conversation}"


def _derive_thread_id_from_state(state: "BimaState") -> str:
    return build_thread_id(
        state.get("discord_user_id", ""),
        state.get("source_channel", ""),
        state.get("conversation_id", ""),
    )
```

Add to `BimaState`:

```python
conversation_id: NotRequired[str]
```

`core/langgraph_engine.py`:

```python
async def run_langgraph_engine(
    user_request: str,
    konteks_waktu: str,
    attachment_paths: list | None = None,
    progress_callback=None,
    discord_user_id: str = "",
    source_channel: str = "",
    conversation_id: str = "",
):
    from core.langgraph_nodes.state import build_thread_id

    # initial_state includes:
    "conversation_id": conversation_id,

    thread_id = build_thread_id(
        discord_user_id,
        source_channel,
        conversation_id,
    )
    _engine_thread_id = thread_id
    config: dict = {"configurable": {"thread_id": thread_id}}
```

Remove both duplicated f-string thread-ID constructions.

- [x] **Step 4: Run GREEN test and state syntax check**

Run:

```bash
pytest tests/test_p0_thread_isolation.py -q
python3 -m py_compile core/langgraph_nodes/state.py core/langgraph_engine.py
```

Expected: tests pass and compilation exits 0.

### Task 5: Propagate Real WhatsApp and Discord Scope

**Files:**
- Modify: `whatsapp/index.js:425-435,710-716`
- Modify: `core/wa_server.py:29-36,120-130`
- Modify: `core/discord_bot.py:529-538`
- Modify: `tests/test_security_fixes.py`
- Modify: `tests/test_p0_thread_isolation.py`

- [x] **Step 1: Write failing bridge validation/source tests**

Append to `tests/test_security_fixes.py`:

```python
def test_wa_bridge_rejects_missing_sender_id() -> None:
    from core.wa_server import app as wa_app

    client = TestClient(wa_app)
    with patch("core.wa_server._WA_TOKEN", "test-token-rahasia"):
        response = client.post(
            "/chat",
            json={"message": "hello", "token": "test-token-rahasia"},
        )

    assert response.status_code == 400
    assert response.json() == {"error": "Sender ID wajib diisi"}
```

Append to `tests/test_p0_thread_isolation.py`:

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_whatsapp_bridge_payload_contains_sender_id() -> None:
    source = (PROJECT_ROOT / "whatsapp" / "index.js").read_text(encoding="utf-8")

    assert "async function sendToAnisa(message, senderId, attachmentPaths = [])" in source
    assert "sender_id: senderId" in source
    assert "sendToAnisa(perintah, senderId, attachmentPaths)" in source


def test_discord_passes_real_conversation_id() -> None:
    source = (PROJECT_ROOT / "core" / "discord_bot.py").read_text(encoding="utf-8")

    assert "conversation_id=str(message.channel.id)" in source
```

- [x] **Step 2: Run RED tests**

Run:

```bash
pytest tests/test_security_fixes.py::test_wa_bridge_rejects_missing_sender_id \
  tests/test_p0_thread_isolation.py -q
```

Expected: WA request is accepted past sender validation and source assertions fail.

- [x] **Step 3: Pass sender and conversation IDs through both bridges**

`whatsapp/index.js`:

```javascript
async function sendToAnisa(message, senderId, attachmentPaths = []) {
    const res = await axios.post(`${CONFIG.bridgeUrl}/chat`, {
        message,
        sender_id: senderId,
        token: CONFIG.bridgeToken,
        attachment_paths: attachmentPaths,
    }, {
        headers: { 'Content-Type': 'application/json' },
        timeout: CONFIG.requestTimeout,
    });
}

// call site
result = await sendToAnisa(perintah, senderId, attachmentPaths);
```

`core/wa_server.py`:

```python
class ChatRequest(BaseModel):
    message: str
    sender_id: str = ""
    token: str = ""
    attachment_paths: list[str] = []


# after auth check
sender_id = req.sender_id.strip()
if not sender_id:
    return JSONResponse({"error": "Sender ID wajib diisi"}, status_code=400)


# engine call
hasil = await run_langgraph_engine(
    user_request=perintah,
    konteks_waktu=konteks_waktu,
    attachment_paths=other_paths,
    progress_callback=None,
    discord_user_id=sender_id,
    source_channel="whatsapp",
    conversation_id=sender_id,
)
```

`core/discord_bot.py` engine call:

```python
discord_user_id=str(message.author.id),
source_channel="discord",
conversation_id=str(message.channel.id),
```

- [x] **Step 4: Verify Python and Node paths**

Run:

```bash
pytest tests/test_security_fixes.py tests/test_p0_thread_isolation.py -q
node --check whatsapp/index.js
```

Expected: tests pass and Node syntax check exits 0.

### Task 6: Remove Activity-Log XSS Sink

**Files:**
- Modify: `dashboard/guild-panels.jsx:68-95,273-278`
- Modify: `dashboard/guild-app.jsx:132-197,230-350`
- Modify: `dashboard/guild-data.jsx:132-167`
- Create: `tests/test_p0_dashboard_xss.py`

- [x] **Step 1: Write failing source regression test**

```python
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_activity_panel_renders_log_message_as_text() -> None:
    source = (PROJECT_ROOT / "dashboard" / "guild-panels.jsx").read_text(
        encoding="utf-8"
    )
    activity = source.split("function ActivityPanel", 1)[1].split("// ── VAULT", 1)[0]

    assert "dangerouslySetInnerHTML" not in activity
    assert '<span className="msg-text">{l.text}</span>' in activity


def test_log_data_does_not_contain_agent_name_html_markup() -> None:
    for relative in ("dashboard/guild-app.jsx", "dashboard/guild-panels.jsx"):
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        assert '<span class="agent-name">' not in source
        assert '<span class=\\"agent-name\\">' not in source
```

- [x] **Step 2: Run RED test**

Run: `pytest tests/test_p0_dashboard_xss.py -q`  
Expected: both tests fail on current HTML sink/markup.

- [x] **Step 3: Render logs as text and replace internal markup**

`dashboard/guild-panels.jsx`:

```jsx
<span className="msg-text">{l.text}</span>
```

Replace log payload strings in both JSX files:

```javascript
`[ANISA] error: ${text.slice(0, 80)}`
`[ANISA] respond · quest dispatched`
`[LORD] kirim perintah ke [ANISA]`
`[${a.name}] → ${m.state}`
`[${a?.name || ev.agent}] → ${ev.state}`
`[${agent.name}] completed quest · loot drop`
`[${agent.name}] rested · MP refilled`
`[${agent.name}] received Token Elixir`
`[${agent.name}] menerima quest: ${action.label}`
```

Keep ChatPanel's `dangerouslySetInnerHTML={{ __html: formatMd(m.text) }}` unchanged because `formatMd()` escapes `&`, `<`, and `>` before adding its own markup; the audited sink is ActivityPanel.

Ubah `LOG_TEMPLATES` dan `genLog()` di `guild-data.jsx` menjadi plain text (`[%a]`, `%n`, `%t`) agar simulated log tidak menampilkan tag mentah setelah sink HTML dihapus.

- [x] **Step 4: Run GREEN test**

Run: `pytest tests/test_p0_dashboard_xss.py -q`  
Expected: `2 passed`.

### Task 7: P0 Verification, Runtime Smoke, and Error Log

**Files:**
- Modify: `error_solutions.md`
- Verify all P0 files.

- [x] **Step 1: Run targeted P0 suite**

```bash
source bima_env/bin/activate
pytest \
  tests/test_p0_path_security.py \
  tests/test_code_visualizer.py \
  tests/test_p0_thread_isolation.py \
  tests/test_security_fixes.py \
  tests/test_p0_dashboard_xss.py \
  tests/test_admin.py \
  tests/test_admin_styles.py -q
```

Expected: all targeted tests pass. If any fail, stop and report without patching outside this approved plan.

- [x] **Step 2: Run syntax and static security checks**

```bash
python3 -m py_compile \
  core/path_security.py \
  core/langgraph_engine.py \
  core/langgraph_nodes/state.py \
  core/wa_server.py \
  core/discord_bot.py \
  teams/t4_admin/excel_tool.py \
  teams/t4_admin/pdf_tool.py \
  teams/t4_admin/word_tool.py \
  tools/code_visualizer.py \
  tools/image_gen_tool.py
node --check whatsapp/index.js
git diff --check
```

Expected: every command exits 0.

- [x] **Step 3: Run full regression suite**

Run: `bima_env/bin/pytest -q`  
Expected: full suite passes. Stop and report any unrelated/pre-existing failure; do not auto-patch it.

- [x] **Step 4: Record non-trivial P0 errors and prevention**

Append one factual section to `error_solutions.md` with:

```markdown
## Log — P0 Security Audit Remediation (2026-07-12)

### Deskripsi Masalah (Root Cause)
- Path dari LLM/user di-resolve atau di-join tanpa containment terhadap root tepercaya.
- Thread checkpoint/callback memakai channel literal dan WhatsApp tidak mengirim sender ID.
- Activity log merender string backend melalui `dangerouslySetInnerHTML`.

### Dampak terhadap Sistem
- File arbitrary dapat dibaca/ditimpa atau dikirim ke API eksternal.
- Riwayat dan progress callback dapat bocor/tertukar antar-user atau channel.
- Payload backend dapat mengeksekusi JavaScript di dashboard.

### Solusi / Tindakan Pencegahan
- Gunakan helper path tunggal dengan `resolve()` + containment dan sanitasi nama output.
- Bentuk thread ID dari jenis channel, user ID, dan conversation ID nyata.
- Render event log sebagai React text node; HTML hanya boleh berasal dari formatter yang escape input.
```

Tambahkan hanya kendala nyata yang muncul saat implementasi; jangan menulis token/path sensitif.

- [x] **Step 5: Restart affected services and smoke-check**

```bash
pm2 restart anisa-v3 bima-whatsapp
pm2 logs anisa-v3 --nostream --lines 50
pm2 logs bima-whatsapp --nostream --lines 50
python healthcheck.py
```

Expected: processes online, no import/syntax error, healthcheck succeeds. Jangan `pm2 save` karena process definition tidak berubah.

- [x] **Step 6: Show final scoped diff**

```bash
git status --short
git diff -- \
  core/path_security.py \
  core/langgraph_nodes/state.py \
  core/langgraph_engine.py \
  core/wa_server.py \
  core/discord_bot.py \
  whatsapp/index.js \
  dashboard/guild-panels.jsx \
  dashboard/guild-app.jsx \
  teams/t4_admin/excel_tool.py \
  teams/t4_admin/pdf_tool.py \
  teams/t4_admin/word_tool.py \
  tools/code_visualizer.py \
  tools/image_gen_tool.py \
  tests/test_p0_path_security.py \
  tests/test_p0_thread_isolation.py \
  tests/test_p0_dashboard_xss.py \
  tests/test_security_fixes.py \
  tests/test_code_visualizer.py \
  error_solutions.md
```

Expected: only approved P0 changes plus pre-existing Bima hunks in overlapping files; no unrelated cleanup.
