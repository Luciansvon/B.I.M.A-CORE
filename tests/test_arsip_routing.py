from langchain_core.messages import AIMessage

from core.langgraph_nodes import arsip
from core.langgraph_nodes.intent_classifier import classify_intent


def test_natural_vault_search_routes_to_arsip() -> None:
    teams, confidence, _ = classify_intent(
        "apa isi catatan preferensi musikku?", False
    )

    assert teams == ["arsip"]
    assert confidence >= 0.85


def test_natural_vault_save_routes_to_arsip() -> None:
    teams, confidence, _ = classify_intent("catat ini dong", False)

    assert teams == ["arsip"]
    assert confidence >= 0.85


def test_manager_message_is_not_upstream_data() -> None:
    state = {
        "messages": [AIMessage(content="Manager routing ke tim Arsip")],
        "temp_data": {},
    }

    assert arsip._get_upstream_data(state) == ""


def test_last_search_result_is_upstream_data() -> None:
    state = {
        "messages": [AIMessage(content="Manager routing ke tim Arsip")],
        "temp_data": {"last_search_result": "  hasil pencarian vault  "},
    }

    assert arsip._get_upstream_data(state) == "hasil pencarian vault"
