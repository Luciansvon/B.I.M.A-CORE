"""Canonical mapping from MCP agent names to CrewAI agent objects."""

AGENT_REGISTRY: dict[str, str] = {
    "intel": "teams.t5_intel:intel_agent",
    "mekanik": "teams.t8_mekanik:mekanik_agent",
    "arsip": "teams.t3_arsip:arsip_agent",
    "visual": "teams.t2_visual:visual_agent",
    "seniman": "teams.t7_seniman:seniman_agent",
    "admin": "teams.t4_admin:admin_agent",
    "lifestyle": "teams.t6_lifestyle:lifestyle_agent",
    "saham": "teams.t9_saham:saham_agent",
    "kodok": "teams.t10_kodok:kodok_agent",
}
