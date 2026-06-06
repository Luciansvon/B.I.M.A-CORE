import os
import urllib.request
import urllib.parse
import json
import re
from pathlib import Path

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

def get_public_tunnel_url() -> str | None:
    log_path = Path(__file__).resolve().parent.parent / "logs" / "tunnel-error.log"
    if not log_path.exists():
        return None
    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
        urls = re.findall(r'https://[a-zA-Z0-9-]+\.trycloudflare\.com', content)
        if urls:
            return urls[-1]
    except Exception as e:
        print(f"Gagal mendeteksi URL tunnel dari log: {e}")
    return None

def main():
    print("=" * 60)
    print("Testing Threads API Image Post — BIMA_CORE")
    print("=" * 60)
    
    env = load_env()
    token = env.get('THREADS_ACCESS_TOKEN')
    
    if not token:
        print("Error: THREADS_ACCESS_TOKEN tidak ditemukan di .env!")
        return

    tunnel_url = get_public_tunnel_url()
    if not tunnel_url:
        print("Error: URL tunnel Cloudflare tidak ditemukan di logs/tunnel-error.log!")
        return
    
    print(f"Detected Public Tunnel URL: {tunnel_url}")

    # Cari file gambar di outputs/
    outputs_dir = Path(__file__).resolve().parent.parent / "outputs"
    image_files = [p for p in outputs_dir.glob("anisa_img_*") if p.is_file()]
    if not image_files:
        # Buat file dummy jika tidak ada gambar
        dummy_path = outputs_dir / "anisa_img_dummy.png"
        if not dummy_path.exists():
            # Tulis file kosong/dummy 1x1 piksel atau teks untuk testing
            dummy_path.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82")
            print("Membuat gambar dummy: outputs/anisa_img_dummy.png")
        image_name = "anisa_img_dummy.png"
    else:
        # Gunakan gambar terbaru
        image_files.sort(key=lambda x: x.stat().st_mtime)
        image_name = image_files[-1].name

    public_image_url = f"{tunnel_url}/outputs/{image_name}"
    print(f"Public Image URL: {public_image_url}")
    print(f"Silakan pastikan link di atas bisa dibuka di browser Anda dan menampilkan gambar.")
    print("-" * 60)

    # Step 1: Create a media container
    print("Langkah 1: Membuat wadah media (media container)...")
    text_content = "Uji coba posting foto otomatis dari B.I.M.A Core. 🖼️🤖"
    
    container_url = "https://graph.threads.net/v1.0/me/threads"
    container_data = urllib.parse.urlencode({
        'media_type': 'IMAGE',
        'image_url': public_image_url,
        'text': text_content,
        'access_token': token
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(container_url, data=container_data)
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            creation_id = res_data.get('id')
            print(f"Sukses membuat container! ID Wadah: {creation_id}")
    except Exception as e:
        print(f"Gagal membuat container: {e}")
        if hasattr(e, 'read'):
            err_body = e.read().decode('utf-8')
            print(f"Response error body: {err_body}")
        return

    # Step 2: Publish the media container
    print("\nLangkah 2: Mempublikasikan postingan...")
    publish_url = "https://graph.threads.net/v1.0/me/threads_publish"
    publish_data = urllib.parse.urlencode({
        'creation_id': creation_id,
        'access_token': token
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(publish_url, data=publish_data)
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            post_id = res_data.get('id')
            print("-" * 60)
            print("POSTINGAN FOTO BERHASIL DIPUBLIKASIKAN!")
            print(f"ID Postingan: {post_id}")
            print("-" * 60)
    except Exception as e:
        print(f"Gagal mempublikasikan: {e}")
        if hasattr(e, 'read'):
            err_body = e.read().decode('utf-8')
            print(f"Response error body: {err_body}")
        return

if __name__ == '__main__':
    main()
