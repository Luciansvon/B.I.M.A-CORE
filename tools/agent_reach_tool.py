import os
import json
import logging
import subprocess
import shutil
import httpx
from crewai.tools import BaseTool

logger = logging.getLogger('bima_core')

class XReachTool(BaseTool):
    name: str = "X Twitter Reach Tool"
    description: str = """Mencari tweet terbaru dari X/Twitter menggunakan agent-reach CLI.
    Jika CLI gagal, otomatis fallback ke RapidAPI.
    Input: keyword. Contoh: 'japandi furniture', 'AI agent 2026'"""

    def _run(self, query: str) -> str:
        # Pesan error CLI default — di-overwrite kalau CLI raise. Disimpan di variabel
        # terpisah karena nama exception `as e` dihapus Python begitu blok except kelar,
        # jadi gak bisa direferensikan lagi di jalur fallback di bawah.
        cli_err = "twitter CLI tidak mengembalikan hasil"
        # 1. Coba pakai twitter CLI terlebih dahulu (dijalankan langsung di WSL)
        try:
            twitter_bin = shutil.which("twitter") or "twitter"
            cmd = [twitter_bin, "search", query, "-n", "10", "--json"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # Parse output
            data = json.loads(result.stdout)
            # twitter returns JSON list or dict depending on version
            tweets = []
            if isinstance(data, list):
                tweets = data
            elif isinstance(data, dict):
                tweets = data.get("tweets", data.get("data", []))
            
            if tweets:
                results = [f"=== X/Twitter (via twitter-cli): '{query}' ===\n"]
                for t in tweets[:7]:
                    user = t.get("user", {}).get("name", "unknown")
                    username = t.get("user", {}).get("username", t.get("user", {}).get("screen_name", ""))
                    text = t.get("text", "")[:280]
                    likes = t.get("likes", t.get("favorite_count", 0))
                    rts = t.get("retweets", t.get("retweet_count", 0))
                    date = t.get("created_at", "")[:10]
                    results.append(
                        f"🐦 {user} (@{username})\n"
                        f"   {text}\n"
                        f"   ❤️ {likes} | 🔁 {rts} | 📅 {date}\n"
                    )
                return "\n".join(results)
        except Exception as e:
            cli_err = str(e)
            logger.warning(f"twitter CLI gagal: {cli_err}. Fallback ke RapidAPI...")

        # 2. Fallback ke RapidAPI XScraper logic
        RAPIDAPI_KEY = os.environ.get("RAPIDAPI_KEY", "")
        if not RAPIDAPI_KEY:
            return f"twitter CLI gagal ({cli_err}) dan RAPIDAPI_KEY tidak ditemukan di .env"

        try:
            url = "https://twitter135.p.rapidapi.com/v2/Search/"
            headers = {
                "x-rapidapi-host": "twitter135.p.rapidapi.com",
                "x-rapidapi-key": RAPIDAPI_KEY,
            }
            params = {"q": query, "count": "10", "type": "Latest"}
            resp = httpx.get(url, headers=headers, params=params, timeout=15)
            data = resp.json()

            tweets_data = (
                data.get("data", {})
                .get("search_by_raw_query", {})
                .get("search_timeline", {})
                .get("timeline", {})
                .get("instructions", [])
            )

            tweets = []
            for instruction in tweets_data:
                entries = instruction.get("entries", [])
                for entry in entries:
                    content = entry.get("content", {}).get("itemContent", {})
                    tweet_result = content.get("tweet_results", {}).get("result", {})
                    legacy = tweet_result.get("legacy", {})
                    if legacy:
                        user = tweet_result.get("core", {}).get("user_results", {}).get("result", {}).get("legacy", {})
                        tweets.append({
                            "text": legacy.get("full_text", "")[:280],
                            "user": user.get("name", "unknown"),
                            "username": user.get("screen_name", ""),
                            "likes": legacy.get("favorite_count", 0),
                            "retweets": legacy.get("retweet_count", 0),
                            "date": legacy.get("created_at", "")
                        })

            if not tweets:
                raise ValueError("Tidak ada tweet ditemukan di RapidAPI 1")

            results = [f"=== X/Twitter (RapidAPI Fallback 1): '{query}' ===\n"]
            for t in tweets[:7]:
                results.append(
                    f"🐦 {t['user']} (@{t['username']})\n"
                    f"   {t['text']}\n"
                    f"   ❤️ {t['likes']} | 🔁 {t['retweets']} | 📅 {t['date'][:10]}\n"
                )
            return "\n".join(results)

        except Exception as e1:
            try:
                url = "https://twitter-api45.p.rapidapi.com/search.php"
                headers = {
                    "x-rapidapi-host": "twitter-api45.p.rapidapi.com",
                    "x-rapidapi-key": RAPIDAPI_KEY,
                }
                params = {"query": query, "search_type": "Latest"}
                resp = httpx.get(url, headers=headers, params=params, timeout=15)
                data = resp.json()

                timeline = data.get("timeline", [])
                if not timeline:
                    return f"Tidak ada tweet untuk '{query}'."

                results = [f"=== X/Twitter (RapidAPI Fallback 2): '{query}' ===\n"]
                for t in timeline[:7]:
                    text = t.get("text", "")[:280]
                    user = t.get("user", {}).get("name", "unknown")
                    username = t.get("user", {}).get("screen_name", "")
                    likes = t.get("favorite_count", 0)
                    rts = t.get("retweet_count", 0)
                    results.append(
                        f"🐦 {user} (@{username})\n"
                        f"   {text}\n"
                        f"   ❤️ {likes} | 🔁 {rts}\n"
                    )
                return "\n".join(results)

            except Exception as e2:
                return f"Gagal scrape X via twitter CLI & RapidAPI.\nError CLI: {cli_err}\nError API 1: {e1}\nError API 2: {e2}"

class JinaReaderTool(BaseTool):
    name: str = "Jina Reader Web Fetch Tool"
    description: str = """Mengambil konten lengkap halaman web (URL) menggunakan Jina Reader API.
    Sangat bagus untuk mengekstrak artikel, berita, dokumentasi, atau postingan blog
    ke format Markdown bersih yang mudah dibaca LLM.
    Input: URL lengkap. Contoh: 'https://github.com/Panniantong/Agent-Reach'"""

    def _run(self, url: str) -> str:
        if not url.startswith("http://") and not url.startswith("https://"):
            return "Error: Input harus berupa URL lengkap (dimulai dengan http:// atau https://)"

        try:
            headers = {
                "Accept": "text/markdown",
                "User-Agent": "BIMA-Core-Jina-Reader"
            }
            # Kita bisa pakai Jina Reader endpoint: https://r.jina.ai/<url>
            jina_url = f"https://r.jina.ai/{url}"
            resp = httpx.get(jina_url, headers=headers, timeout=25)
            if resp.status_code == 200:
                content = resp.text
                if len(content) > 6000:
                    content = content[:6000] + "\n\n...[Konten dipotong karena terlalu panjang]..."
                return f"=== Konten Web (via Jina Reader): {url} ===\n\n{content}"
            else:
                return f"Gagal fetch via Jina Reader. Status code: {resp.status_code}"
        except Exception as e:
            return f"Gagal fetch via Jina Reader: {e}"
