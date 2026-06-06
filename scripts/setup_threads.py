import os
import urllib.request
import urllib.parse
import json
from pathlib import Path

# Load existing .env if possible
def load_env():
    env_path = Path('.env')
    env_data = {}
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env_data[k.strip()] = v.strip()
    return env_data

def save_env(updates):
    env_path = Path('.env')
    lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
    # Update existing keys or append
    for key, val in updates.items():
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={val}\n"
                found = True
                break
        if not found:
            lines.append(f"\n# Threads API Config\n{key}={val}\n")
            
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

def main():
    print("=" * 60)
    print("Threads API Setup Helper — BIMA_CORE")
    print("=" * 60)
    
    env = load_env()
    
    app_id = env.get('THREADS_APP_ID') or input("Masukkan Threads App ID / ID Aplikasi Threads: ").strip()
    app_secret = env.get('THREADS_APP_SECRET') or input("Masukkan Threads App Secret / Rahasia Aplikasi Threads: ").strip()
    
    if not app_id or not app_secret:
        print("Error: App ID dan App Secret wajib diisi!")
        return

    # Update .env with app_id and app_secret
    save_env({
        'THREADS_APP_ID': app_id,
        'THREADS_APP_SECRET': app_secret
    })
    
    redirect_uri = "https://httpbin.org/anything"
    
    # Construct Authorization URL
    scopes = "threads_basic,threads_content_publish"
    auth_url = f"https://threads.net/oauth/authorize?client_id={app_id}&redirect_uri={urllib.parse.quote(redirect_uri)}&scope={scopes}&response_type=code"
    
    print("\nLangkah 1: Konfigurasi Redirect URI di Meta Developer Dashboard")
    print("Sebelum melanjutkan, pastikan Anda telah mendaftarkan Redirect URI berikut di pengaturan Threads API Anda:")
    print(f"👉  {redirect_uri}")
    print("Jika sudah, silakan lanjutkan.")
    input("\nTekan Enter setelah Anda memastikan Redirect URI terdaftar...")

    print("\nLangkah 2: Otorisasi Akun Threads Anda")
    print("Buka tautan berikut di browser Anda:")
    print("-" * 80)
    print(auth_url)
    print("-" * 80)
    print("\nSetelah Anda menyetujui, browser akan dialihkan ke halaman httpbin.org.")
    print("Cari parameter 'code' di URL bar browser Anda (misalnya: https://httpbin.org/anything?code=AQBxyz...)")
    
    auth_code = input("\nMasukkan kode 'code' tersebut di sini: ").strip()
    if not auth_code:
        print("Error: Kode otorisasi kosong.")
        return
        
    # If the user copied the whole URL by mistake, extract code
    if "code=" in auth_code:
        try:
            parsed = urllib.parse.urlparse(auth_code)
            auth_code = urllib.parse.parse_qs(parsed.query)['code'][0]
        except Exception:
            pass
            
    # Exchange code for short-lived token
    print("\nMenukarkan kode otorisasi dengan Short-Lived Access Token...")
    token_url = "https://graph.threads.net/oauth/access_token"
    data = urllib.parse.urlencode({
        'client_id': app_id,
        'client_secret': app_secret,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
        'code': auth_code
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(token_url, data=data)
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            short_token = res_data.get('access_token')
            user_id = res_data.get('user_id')
            print(f"Sukses mendapatkan Short-Lived Token! User ID: {user_id}")
    except Exception as e:
        print(f"Gagal menukarkan kode: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))
        return

    # Exchange short-lived token for long-lived token
    print("\nMenukarkan dengan Long-Lived Access Token (berlaku 60 hari)...")
    long_token_url = f"https://graph.threads.net/access_token?grant_type=th_exchange_token&client_secret={app_secret}&access_token={short_token}"
    
    try:
        with urllib.request.urlopen(long_token_url) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            long_token = res_data.get('access_token')
            expires_in = res_data.get('expires_in')
            print(f"Sukses mendapatkan Long-Lived Token! Berlaku selama: {expires_in} detik (sekitar 60 hari).")
    except Exception as e:
        print(f"Gagal mendapatkan Long-Lived Token: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))
        return

    # Save to .env
    save_env({
        'THREADS_ACCESS_TOKEN': long_token
    })
    print("\n" + "=" * 60)
    print("SETUP BERHASIL!")
    print("Token akses Threads Anda telah disimpan ke file .env.")
    print("=" * 60)

if __name__ == '__main__':
    main()
