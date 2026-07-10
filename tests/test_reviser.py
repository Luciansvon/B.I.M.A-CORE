import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

async def main():
    print("=" * 60)
    print("Mengevaluasi Perbaikan XML Tag pada apply_smart_revision")
    print("=" * 60)
    
    # Load env
    load_dotenv(override=True)
    
    from core.threads_commands import apply_smart_revision
    
    # Test case 1: Feedback revisi biasa
    draft1 = "Sore-sore gini enaknya minum es teh sambil ngeliatin orang pusing mikir kerjaan wkwk 😭"
    feedback1 = "bikin lebih pendek, ganti es teh jadi kopi susu"
    
    # Test case 2: Feedback berupa teks final yang utuh (AI harus mengembalikan as-is di dalam tag)
    draft2 = "Kabel berantakan itu sebenarnya minimalis jiwa doang 😭 padahal udah beli cable tray velcro"
    feedback2 = "Gua gak setuju minimalis jiwa, kabel berantakan itu murni karena males rapihin aja titik."

    test_cases = [
        ("Feedback Revisi Biasa", draft1, feedback1),
        ("Feedback Teks Final/Opini Baru", draft2, feedback2)
    ]
    
    for label, draft, feedback in test_cases:
        print(f"\n🧪 Pengujian: {label}")
        print(f"Draf Awal : {draft}")
        print(f"Feedback  : {feedback}")
        try:
            revised = await apply_smart_revision(draft, feedback)
            print("-" * 40)
            print(f"Hasil Akhir (Harus Bersih Basa-Basi):\n{revised}")
            print("-" * 40)
            print(f"Karakter count: {len(revised)}")
            
            # Cek jika ada sisa tag atau basa-basi robotik
            assert "<draft>" not in revised, "Gagal: Tag <draft> masih tersisa di output!"
            assert "</draft>" not in revised, "Gagal: Tag </draft> masih tersisa di output!"
            assert "tentu" not in revised.lower() or len(revised) < 150, "Peringatan: Output kemungkinan mengandung basa-basi AI!"
            print("✅ Hasil revisi terbukti bersih!")
        except Exception as e:
            print(f"❌ Gagal revisi: {e}")
            
if __name__ == "__main__":
    asyncio.run(main())
