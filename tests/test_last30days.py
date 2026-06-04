import os
import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
from langchain_core.messages import AIMessage, HumanMessage

from tools.last30days_tool import Last30DaysResearchTool
from core.langgraph_nodes.intel import intel_node
from core.langgraph_nodes.state import BimaState


def test_last30days_tool_import():
    tool = Last30DaysResearchTool()
    assert tool.name == "Last 30 Days Research Tool"
    assert tool.args_schema is not None


def test_last30days_tool_run_mock():
    tool = Last30DaysResearchTool()
    # Panggil dengan mock=True agar menggunakan data lokal
    res = tool._run(topic="Cursor IDE", quick=True, days=30, mock=True)
    
    assert res.startswith("SUCCESS|")
    parts = res.split("|", 2)
    assert len(parts) == 3
    
    html_path = Path(parts[1])
    compact_md = parts[2]
    
    assert html_path.exists()
    assert html_path.suffix == ".html"
    assert "last30days" in compact_md.lower()
    
    # Clean up generated html file
    if html_path.exists():
        html_path.unlink()


@pytest.mark.asyncio
async def test_intel_node_last30days_routing():
    # Buat state input
    state = BimaState(
        messages=[],
        user_request="bagaimana tren dan sentimen orang tentang next.js baru-baru ini?",
        realtime_context="Waktu: 2026-06-04",
        attachment_paths=[],
        current_plan="",
        active_teams=["intel"],
        temp_data={},
        is_finished=False,
        discord_user_id="12345",
        source_channel="discord"
    )
    
    # Mocking:
    # 1. default_llm.invoke untuk mengekstrak topik & merangkum
    mock_llm_response_topic = AIMessage(content="Next.js")
    mock_llm_response_summary = AIMessage(content="Analisis: Komunitas sangat senang dengan Next.js.")
    
    # 2. last30days_tool._run
    dummy_html_file = Path(__file__).resolve().parent / "dummy_test_report.html"
    dummy_html_file.write_text("<html>Dummy</html>", encoding="utf-8")
    mock_tool_run_result = f"SUCCESS|{dummy_html_file}|# Next.js\n- Sentimen: Positif"
    
    try:
        with patch("core.langgraph_nodes.intel.default_llm") as mock_llm:
            # Set mock responses for invoke calls
            mock_llm.invoke.side_effect = [mock_llm_response_topic, mock_llm_response_summary]
            
            with patch("core.langgraph_nodes.intel.last30days_tool._run", return_value=mock_tool_run_result) as mock_tool_run:
                
                # Jalankan node
                result = await intel_node(state)
                
                # Verifikasi pemanggilan
                mock_tool_run.assert_called_once_with(topic="Next.js")
                assert mock_llm.invoke.call_count == 2
                
                # Verifikasi output state
                assert "messages" in result
                assert len(result["messages"]) == 1
                final_msg = result["messages"][0]
                assert isinstance(final_msg, AIMessage)
                assert "SUCCESS|" in final_msg.content
                assert str(dummy_html_file) in final_msg.content
                
                temp_data = result.get("temp_data", {})
                assert temp_data.get("last_30days_html_brief") == str(dummy_html_file)
                assert temp_data.get("last_search_result") == "# Next.js\n- Sentimen: Positif"
                assert result.get("is_finished") is True  # Karena tidak ada downstream node aktif
    finally:
        if dummy_html_file.exists():
            dummy_html_file.unlink()
