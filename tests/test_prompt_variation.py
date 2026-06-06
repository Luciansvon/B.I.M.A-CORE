import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Tambahkan path root proyek agar module core bisa di-import
sys.path.append(str(Path(__file__).resolve().parent.parent))

async def main():
    print("=" * 60)
    print("Mengevaluasi Gaya Bahasa Baru Anisa (BIMA_SYSTEM_PROMPT)")
    print("=" * 60)
    
    # Load env
    load_dotenv(override=True)
    
    from core.threads_commands import generate_bima_draft
    
    test_prompts = [
        "Topik: Error compiler pas ngompile library di project baru",
        "Topik: Setup meja kerja desk setup minimalis tapi kabelnya berantakan",
        "Topik: Keluh kesah harga kopi susu arabica naik tapi rasa makin biasa aja"
    ]
    
    for idx, p in enumerate(test_prompts, 1):
        print(f"\n🧪 Pengujian {idx}: {p}")
        try:
            draft = await generate_bima_draft(p)
            print("-" * 40)
            print(f"Hasil Draf:\n{draft}")
            print("-" * 40)
            print(f"Karakter count: {len(draft)}")
        except Exception as e:
            print(f"❌ Gagal generate draf: {e}")
            
if __name__ == "__main__":
    asyncio.run(main())
