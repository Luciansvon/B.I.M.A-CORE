from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_activity_panel_renders_log_message_as_text() -> None:
    source = (PROJECT_ROOT / "dashboard" / "guild-panels.jsx").read_text(
        encoding="utf-8"
    )
    activity = source.split("function ActivityPanel", 1)[1].split(
        "// ── VAULT",
        1,
    )[0]

    assert "dangerouslySetInnerHTML" not in activity
    assert '<span className="msg-text">{l.text}</span>' in activity


def test_log_data_does_not_contain_agent_name_html_markup() -> None:
    for relative in (
        "dashboard/guild-app.jsx",
        "dashboard/guild-data.jsx",
        "dashboard/guild-panels.jsx",
    ):
        source = (PROJECT_ROOT / relative).read_text(encoding="utf-8")
        assert '<span class="agent-name">' not in source
        assert '<span class=\\"agent-name\\">' not in source
        assert "<a>" not in source
        assert "<n>" not in source
