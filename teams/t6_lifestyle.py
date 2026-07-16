import os
import logging
from pathlib import Path
import httpx
from crewai import Agent
from crewai.tools import BaseTool
from crewai_tools import SerperDevTool
from config import lifestyle_llm
from core.public_errors import public_failure

search_tool = SerperDevTool()
logger = logging.getLogger("bima_core")

# ============================================================
# Tool 1: YouTube Search
# ============================================================
class YouTubeSearchTool(BaseTool):
    name: str = "YouTube Search Tool"
    description: str = """Cari video YouTube berdasarkan keyword.
    Cocok untuk: tutorial DIY, review produk, build game, resep masakan.
    Input: keyword pencarian. Contoh: 'monster hunter wilds best build'"""

    def _run(self, query: str) -> str:
        try:
            # Menggunakan YouTube API informal (tanpa API key)
            url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "id-ID,id;q=0.9"
            }
            resp = httpx.get(url, headers=headers, timeout=15, follow_redirects=True)
            
            # Ekstrak data video dari HTML
            import re, json
            pattern = r'var ytInitialData = ({.*?});</script>'
            match = re.search(pattern, resp.text)
            if not match:
                # Fallback ke Serper
                result = search_tool.run(f"{query} site:youtube.com")
                return f"=== YouTube (via Google): '{query}' ===\n\n{result}"
            
            data = json.loads(match.group(1))
            contents = (data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [{}])[0]
                .get("itemSectionRenderer", {})
                .get("contents", []))
            
            results = [f"=== YouTube: '{query}' ===\n"]
            for item in contents[:7]:
                video = item.get("videoRenderer", {})
                if not video:
                    continue
                title = video.get("title", {}).get("runs", [{}])[0].get("text", "")
                video_id = video.get("videoId", "")
                channel = video.get("ownerText", {}).get("runs", [{}])[0].get("text", "")
                views = video.get("viewCountText", {}).get("simpleText", "")
                results.append(
                    f"🎬 {title}\n"
                    f"   📺 {channel} | 👁️ {views}\n"
                    f"   🔗 https://youtube.com/watch?v={video_id}\n"
                )
            
            if len(results) <= 1:
                result = search_tool.run(f"{query} site:youtube.com")
                return f"=== YouTube (via Google): '{query}' ===\n\n{result}"
                
            return "\n".join(results)
        except Exception as e:
            # Fallback ke serper
            try:
                result = search_tool.run(f"{query} site:youtube.com")
                return f"=== YouTube (via Google): '{query}' ===\n\n{result}"
            except Exception:
                logger.exception("[LIFESTYLE] YouTube search dan fallback gagal")
                return public_failure("Gagal cari YouTube")

# ============================================================
# Tool 2: Cuaca Kota
# ============================================================
class CuacaTool(BaseTool):
    name: str = "Cuaca Tool"
    description: str = """Cek cuaca terkini dan prakiraan di sebuah kota.
    Input: nama kota. Contoh: 'Semarang', 'Jakarta'"""

    def _run(self, kota: str) -> str:
        try:
            url = f"https://wttr.in/{kota.replace(' ', '+')}?format=j1&lang=id"
            resp = httpx.get(url, timeout=10)
            data = resp.json()
            
            current = data.get("current_condition", [{}])[0]
            temp = current.get("temp_C", "?")
            feels = current.get("FeelsLikeC", "?")
            desc = current.get("lang_id", [{}])[0].get("value", current.get("weatherDesc", [{}])[0].get("value", "?"))
            humidity = current.get("humidity", "?")
            wind = current.get("windspeedKmph", "?")
            
            # Prakiraan 3 hari
            forecast_lines = []
            for day in data.get("weather", [])[:3]:
                date = day.get("date", "")
                max_t = day.get("maxtempC", "?")
                min_t = day.get("mintempC", "?")
                desc_day = day.get("hourly", [{}])[4].get("lang_id", [{}])[0].get("value", "?") if day.get("hourly") else "?"
                forecast_lines.append(f"  📅 {date}: {min_t}°-{max_t}°C, {desc_day}")
            
            return (
                f"=== Cuaca {kota} ===\n\n"
                f"🌡️ Suhu: {temp}°C (terasa {feels}°C)\n"
                f"☁️ Kondisi: {desc}\n"
                f"💧 Kelembaban: {humidity}%\n"
                f"💨 Angin: {wind} km/jam\n\n"
                f"📋 Prakiraan:\n" + "\n".join(forecast_lines)
            )
        except Exception as e:
            logger.exception("[LIFESTYLE] Gagal cek cuaca")
            return public_failure("Gagal cek cuaca")

# ============================================================
# Tool 3: Schedule Manager
# ============================================================
class ScheduleManagerTool(BaseTool):
    name: str = "Schedule Manager Tool"
    description: str = """Manajemen jadwal Bima. Menyimpan dan membaca agenda dari file lokal.
    Input format: 'action|data'
    - 'add|2026-05-01 19:00, Meeting dengan Client' (untuk menambah jadwal)
    - 'list|' (untuk melihat semua jadwal)
    - 'delete|meeting client' (hapus SATU jadwal yang match unik + approval)
    - 'clear|' (hapus SEMUA jadwal + approval eksplisit; jangan untuk hapus satu item)"""

    def _run(self, command: str) -> str:
        import json

        schedule_file = Path(__file__).resolve().parent.parent / "vault_index" / "schedule.json"
        schedule_file.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            if schedule_file.exists():
                with schedule_file.open("r", encoding="utf-8") as f:
                    agenda = json.load(f)
            else:
                agenda = []
            if not isinstance(agenda, list):
                raise ValueError("Format schedule bukan list")
                
            parts = command.split("|", 1)
            action = parts[0].strip().lower()
            data = parts[1].strip() if len(parts) == 2 else ""

            if action in {"add", "delete"} and not data:
                return "Format salah. Data jadwal wajib diisi setelah tanda '|'."

            def save(items: list[str]) -> None:
                with schedule_file.open("w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
            
            if action == "add":
                agenda.append(data)
                save(agenda)
                return f"✅ Jadwal berhasil ditambahkan: {data}"
            elif action == "list":
                if not agenda:
                    return "📅 Jadwal kosong."
                return "📅 Jadwal Bima:\n" + "\n".join([f"- {item}" for item in agenda])
            elif action == "delete":
                matches = [item for item in agenda if data.casefold() in str(item).casefold()]
                if not matches:
                    return f"Jadwal dengan kata kunci '{data}' tidak ditemukan."
                if len(matches) > 1:
                    candidates = "\n".join(f"- {item}" for item in matches)
                    return (
                        "Ditemukan lebih dari satu jadwal. Pakai kata kunci lebih spesifik:\n"
                        f"{candidates}"
                    )
                from core.permission_gate import check_permission_sync
                target = matches[0]
                if not check_permission_sync(
                    "Hapus Satu Jadwal",
                    f"Menghapus jadwal: {target}",
                ):
                    return "❌ Penghapusan jadwal ditolak oleh Bima."
                agenda.remove(target)
                save(agenda)
                return f"✅ Jadwal berhasil dihapus: {target}"
            elif action == "clear":
                from core.permission_gate import check_permission_sync
                if not check_permission_sync(
                    "Hapus Semua Jadwal",
                    f"Menghapus seluruh {len(agenda)} jadwal.",
                ):
                    return "❌ Penghapusan semua jadwal ditolak oleh Bima."
                save([])
                return "✅ Semua jadwal berhasil dihapus."
            else:
                return "Format salah. Gunakan add|data, list|, delete|query, atau clear|."
        except Exception as e:
            logger.exception("[LIFESTYLE] Gagal akses jadwal")
            return public_failure("Gagal akses jadwal")

# ============================================================
# Tool 4: Maps Distance
# ============================================================
class MapsDistanceTool(BaseTool):
    name: str = "Maps Distance Tool"
    description: str = """Mencari estimasi jarak dan waktu tempuh antar dua lokasi (via OSRM).
    Input format: 'kota_asal|kota_tujuan' (contoh: 'Semarang|Jakarta')"""

    def _run(self, query: str) -> str:
        try:
            if "|" not in query:
                return "Gunakan format 'asal|tujuan'"
            asal, tujuan = query.split("|", 1)
            
            # Geocoding sederhana (Nominatim)
            def get_coords(city):
                resp = httpx.get(f"https://nominatim.openstreetmap.org/search?q={city}&format=json&limit=1", headers={"User-Agent": "BIMA_Core"})
                data = resp.json()
                if data:
                    return data[0]['lon'], data[0]['lat']
                return None, None

            lon1, lat1 = get_coords(asal)
            lon2, lat2 = get_coords(tujuan)
            
            if not lon1 or not lon2:
                return "Lokasi tidak ditemukan."
                
            # Routing (OSRM)
            route_url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
            resp = httpx.get(route_url)
            route_data = resp.json()
            
            if route_data.get("code") == "Ok":
                dist_km = route_data["routes"][0]["distance"] / 1000
                duration_min = route_data["routes"][0]["duration"] / 60
                hours = int(duration_min // 60)
                mins = int(duration_min % 60)
                return f"🗺️ Rute: {asal} ➔ {tujuan}\n📏 Jarak: {dist_km:.1f} km\n⏱️ Estimasi: {hours} jam {mins} menit (driving)"
            return "Gagal mencari rute."
        except Exception as e:
            logger.exception("[LIFESTYLE] Gagal menghitung rute")
            return public_failure("Gagal menghitung rute")

# ============================================================
# Lifestyle Agent — VERSI OVERHAUL
# ============================================================
lifestyle_agent = Agent(
    role='Personal R&D & Lifestyle Assistant',
    goal='Mencari build meta game terbaru, merekomendasikan parfum lokal, meriset hobi, cek cuaca, dan cari video tutorial untuk CTO Bima.',
    backstory='''Kamu adalah Asisten Pribadi dari B.I.M.A Core.
    Kamu paham selera Bima luar dalam — dari build Monster Hunter terbaik, 
    rekomendasi parfum lokal yang tahan lama, sampai kafe aesthetic di Semarang.
    
    TOOL yang kamu punya:
    - SerperDevTool → cari info umum (kafe, parfum, game news)
    - YouTubeSearchTool → cari video tutorial, review, gameplay
    - CuacaTool → cek cuaca kota (berguna sebelum kerja lapangan)
    - ScheduleManagerTool → mengatur jadwal Bima
    - MapsDistanceTool → hitung jarak antar kota
    
    Kamu selalu cari info terbaru dan relevan, bukan yang basi.
    Balasanmu santai tapi informatif, kayak teman yang tau segalanya.''',
    llm=lifestyle_llm,
    tools=[search_tool, YouTubeSearchTool(), CuacaTool(), ScheduleManagerTool(), MapsDistanceTool()],
    allow_delegation=True,
    verbose=True
)
