import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

# --- Test WA Bridge Server ---
def test_wa_bridge_auth():
    from core.wa_server import app as wa_app
    client = TestClient(wa_app)
    
    # Mock token di wa_server agar konsisten
    with patch("core.wa_server._WA_TOKEN", "test-token-rahasia"):
        # 1. Coba kirim tanpa token -> harus gagal 401
        res = client.post("/chat", json={"message": "hello", "token": ""})
        assert res.status_code == 401
        assert "Token tidak valid" in res.json()["detail"]
        
        # 2. Coba kirim dengan token salah -> harus gagal 401
        res = client.post("/chat", json={"message": "hello", "token": "salah"})
        assert res.status_code == 401
        assert "Token tidak valid" in res.json()["detail"]
        
        # 3. Coba kirim dengan token benar -> harus lolos auth
        # (Akan mengembalikan status busy / error dari LangGraph, bukan 401)
        res = client.post("/chat", json={"message": "", "token": "test-token-rahasia"})
        assert res.status_code != 401

def test_wa_bridge_empty_token_fallback():
    from core.wa_server import app as wa_app
    client = TestClient(wa_app)
    
    # Mock token kosong (seperti jika tidak diset di .env)
    with patch("core.wa_server._WA_TOKEN", ""):
        # Coba kirim dengan token sembarang -> harus tetap ditolak (401) karena server otomatis
        # men-generate token acak baru daripada membiarkan akses kosong.
        res = client.post("/chat", json={"message": "hello", "token": "sembarang"})
        assert res.status_code == 401
        assert "Token tidak valid" in res.json()["detail"]


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

# --- Test Dashboard Server ---
def test_dashboard_outputs_auth():
    from core.dashboard_server import app as dash_app
    client = TestClient(dash_app)
    
    with patch("core.dashboard_server._API_TOKEN", "dash-secret"):
        # 1. Coba panggil list_outputs tanpa token -> harus gagal 401
        res = client.get("/api/outputs")
        assert res.status_code == 401
        
        # 2. Coba panggil list_outputs dengan token salah -> harus gagal 401
        res = client.get("/api/outputs", headers={"Authorization": "Bearer salah"})
        assert res.status_code == 401
        
        # 3. Coba panggil list_outputs dengan token benar -> harus lolos auth (200)
        res = client.get("/api/outputs", headers={"Authorization": "Bearer dash-secret"})
        assert res.status_code == 200

        # 4. Coba panggil serve_output tanpa token -> harus gagal 401
        res = client.get("/outputs/test_file.pdf")
        assert res.status_code == 401
        
        # 5. Coba panggil serve_output dengan token benar -> harus lolos auth
        # (Akan mengembalikan 404 karena file test_file.pdf memang tidak ada, tapi bukan 401)
        res = client.get("/outputs/test_file.pdf", headers={"Authorization": "Bearer dash-secret"})
        assert res.status_code == 404
