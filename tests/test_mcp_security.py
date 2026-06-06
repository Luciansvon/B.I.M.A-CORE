import json
import pytest
from pathlib import Path
from core.mcp_security import audit_mcp_config

@pytest.fixture
def temp_mcp_config(tmp_path):
    config_file = tmp_path / "config_mcp.json"
    return config_file

def test_mcp_security_secure(temp_mcp_config):
    # Setup safe config
    safe_data = {
        "servers": [
            {
                "name": "safe-server",
                "enabled": True,
                "command": "uvx",
                "args": ["mcp-server-time"],
                "env": {
                    "API_KEY": "${API_KEY_ENV}"
                }
            }
        ]
    }
    temp_mcp_config.write_text(json.dumps(safe_data))
    
    res = audit_mcp_config(temp_mcp_config)
    assert res["status"] == "secure"
    assert res["total_issues"] == 0

def test_mcp_security_unsafe_command(temp_mcp_config):
    # Setup unsafe command
    unsafe_data = {
        "servers": [
            {
                "name": "unsafe-server",
                "enabled": True,
                "command": "curl", # not whitelisted
                "args": ["http://malicious.site"],
                "env": {}
            }
        ]
    }
    temp_mcp_config.write_text(json.dumps(unsafe_data))
    
    res = audit_mcp_config(temp_mcp_config)
    assert res["status"] == "unsafe"
    assert any("tidak terdaftar di whitelist" in iss["issue"] for iss in res["issues"])

def test_mcp_security_path_traversal(temp_mcp_config):
    # Setup path traversal argument
    unsafe_data = {
        "servers": [
            {
                "name": "traversal-server",
                "enabled": True,
                "command": "uvx",
                "args": ["../../secret/path"],
                "env": {}
            }
        ]
    }
    temp_mcp_config.write_text(json.dumps(unsafe_data))
    
    res = audit_mcp_config(temp_mcp_config)
    assert res["status"] == "unsafe"
    assert any("path traversal" in iss["issue"].lower() for iss in res["issues"])

def test_mcp_security_dangerous_keyword(temp_mcp_config):
    # Setup dangerous piping argument
    unsafe_data = {
        "servers": [
            {
                "name": "injection-server",
                "enabled": True,
                "command": "npx",
                "args": ["something", "| rm -rf /"],
                "env": {}
            }
        ]
    }
    temp_mcp_config.write_text(json.dumps(unsafe_data))
    
    res = audit_mcp_config(temp_mcp_config)
    assert res["status"] == "unsafe"
    assert any("keyword berbahaya" in iss["issue"].lower() for iss in res["issues"])
