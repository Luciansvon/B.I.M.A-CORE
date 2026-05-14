import sys, os, winsound, shutil, time, json, subprocess, ctypes
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QScrollArea, QVBoxLayout
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal, QObject
from PyQt5.QtGui import QMovie, QFont, QTransform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UKURAN_ANISA = 100
WSL_BRAIN_DIR = r"\\wsl.localhost\Ubuntu\home\bima_lucian\BIMA_CORE"
ALLOWED_EXTENSIONS = ('.txt', '.pdf', '.docx', '.jpg', '.png', '.csv', '.xlsx')

def get_path(filename):
    import tempfile
    path = os.path.join(BASE_DIR, filename)
    path = path if path.lower().endswith(".gif") else path + ".gif"
    
    temp_dir = tempfile.gettempdir()
    dest_path = os.path.join(temp_dir, os.path.basename(path))
    
    try:
        if not os.path.exists(dest_path) or os.path.getsize(path) != os.path.getsize(dest_path):
            shutil.copy2(path, dest_path)
        return dest_path.replace("\\", "/")
    except Exception as e:
        print("Gagal menyalin GIF:", e)
        return path.replace("\\", "/")

# ============================================================
# UPGRADE #5: Windows Toast Notification (zero dependency)
# ============================================================
def show_toast(title, message):
    """Kirim Windows 10/11 toast notification tanpa install apapun"""
    try:
        # Potong pesan agar tidak terlalu panjang di notif
        short_msg = message[:150].replace('"', "'").replace('\n', ' ')
        ps_script = f'''
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$text = $template.GetElementsByTagName("text")
$text.Item(0).AppendChild($template.CreateTextNode("{title}")) | Out-Null
$text.Item(1).AppendChild($template.CreateTextNode("{short_msg}")) | Out-Null
$toast = [Windows.UI.Notifications.ToastNotification]::new($template)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("Anisa - B.I.M.A Core").Show($toast)
'''
        subprocess.Popen(
            ['powershell', '-WindowStyle', 'Hidden', '-Command', ps_script],
            creationflags=0x08000000  # CREATE_NO_WINDOW
        )
    except Exception as e:
        print(f"[TOAST] Error: {e}", flush=True)

# ============================================================
# UPGRADE #4: Personality & Mood System
# ============================================================
PERSONALITY_FILE = os.path.join(BASE_DIR, "personality.json")

class PersonalityEngine:
    def __init__(self):
        self.data = self._load()
    
    def _load(self):
        default = {
            "mood": 70,           # 0-100 (0=sedih, 50=netral, 100=senang)
            "total_tasks": 0,
            "tasks_today": 0,
            "errors_today": 0,
            "last_date": "",
            "last_interaction": 0
        }
        try:
            if os.path.exists(PERSONALITY_FILE):
                with open(PERSONALITY_FILE, "r") as f:
                    saved = json.load(f)
                    default.update(saved)
        except: pass
        return default
    
    def _save(self):
        try:
            with open(PERSONALITY_FILE, "w") as f:
                json.dump(self.data, f, indent=2)
        except: pass
    
    def _reset_daily(self):
        today = time.strftime("%Y-%m-%d")
        if self.data["last_date"] != today:
            self.data["last_date"] = today
            self.data["tasks_today"] = 0
            self.data["errors_today"] = 0
            # Mood sedikit naik di hari baru (fresh start!)
            self.data["mood"] = min(100, self.data["mood"] + 5)
    
    def on_task_complete(self, duration):
        self._reset_daily()
        self.data["total_tasks"] += 1
        self.data["tasks_today"] += 1
        self.data["last_interaction"] = time.time()
        # Task selesai cepat (<30s) = lebih happy
        if duration < 30:
            self.data["mood"] = min(100, self.data["mood"] + 8)
        else:
            self.data["mood"] = min(100, self.data["mood"] + 3)
        self._save()
    
    def on_error(self):
        self._reset_daily()
        self.data["errors_today"] += 1
        self.data["mood"] = max(0, self.data["mood"] - 10)
        self._save()
    
    def on_chat(self):
        self._reset_daily()
        self.data["last_interaction"] = time.time()
        self.data["mood"] = min(100, self.data["mood"] + 2)
        self._save()
    
    def get_greeting(self):
        """Sapaan berdasarkan waktu dan mood"""
        hour = int(time.strftime("%H"))
        mood = self.data["mood"]
        tasks = self.data["tasks_today"]
        
        # Waktu
        if hour < 6:
            waktu = "Masih begadang nih komandan? 🌙"
        elif hour < 11:
            waktu = "Selamat pagi komandan! ☀️"
        elif hour < 15:
            waktu = "Selamat siang komandan! 🌤️"
        elif hour < 18:
            waktu = "Selamat sore komandan! 🌅"
        else:
            waktu = "Selamat malam komandan! 🌙"
        
        # Mood
        if mood >= 80:
            feel = "Anisa lagi happy banget hari ini! 🥰✨"
        elif mood >= 60:
            feel = "Anisa siap tempur! 💪"
        elif mood >= 40:
            feel = "Anisa agak capek, tapi masih semangat! 😊"
        elif mood >= 20:
            feel = "Hmm... Anisa lagi agak lesu nih 😔"
        else:
            feel = "Anisa butuh semangat dari komandan... 🥺"
        
        # Stats
        if tasks > 0:
            stats = f"\n📊 Hari ini sudah selesai {tasks} tugas!"
        else:
            stats = ""
        
        return f"{waktu}\n{feel}{stats}"
    
    def flavor_text(self, event):
        """Tambahan ekspresi berdasarkan mood"""
        mood = self.data["mood"]
        if event == "task_completed":
            if mood >= 80:
                return ["Yeay! 🎉", "Mantap! 🔥", "Keren banget! ✨", "Gampang! 💅"][self.data["total_tasks"] % 4]
            elif mood >= 50:
                return ["Selesai! ✅", "Oke beres! 👍", "Done! 📋"][self.data["total_tasks"] % 3]
            else:
                return "Akhirnya selesai juga... 😮‍💨"
        elif event == "chat_received":
            if mood >= 70:
                return "Ooh ada pesan nih! 🤩"
            else:
                return "Ada pesan masuk... 📩"
        return ""

class ComicBubble(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.setStyleSheet("""
            QScrollArea {background: white; border: 3px solid black; border-radius: 12px;}
            QLabel {color: black; background: white; padding: 10px; font-weight: bold;}
            QScrollBar:vertical { width: 10px; }
        """)
        self.label = QLabel("")
        self.label.setWordWrap(True)
        self.label.setFont(QFont("Arial", 10))
        self.setWidget(self.label)
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sp = self.sizePolicy()
        sp.setRetainSizeWhenHidden(True)
        self.setSizePolicy(sp)
        self.hide()

    def update_text(self, text):
        self.label.setText(text)
        self.label.adjustSize()
        self.setFixedHeight(min(max(self.label.height() + 25, 50), 200))
        QTimer.singleShot(10, lambda: self.verticalScrollBar().setValue(self.verticalScrollBar().maximum()))

# Path langsung ke file event
PET_EVENT_FILE = r"\\wsl.localhost\Ubuntu\home\bima_lucian\BIMA_CORE\outputs\pet_event.json"

class FilePollingClient(QObject):
    on_event_received = pyqtSignal(str, object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_timestamp = 0
        self.last_mtime = 0
        print(f"[PET] Memantau event file: {PET_EVENT_FILE}", flush=True)
        
        try:
            exists = os.path.exists(PET_EVENT_FILE)
            print(f"[PET] File exists saat startup: {exists}", flush=True)
        except Exception as e:
            print(f"[PET] Error cek path awal: {e}", flush=True)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_file)
        self.timer.start(800)

    def check_file(self):
        try:
            try:
                stat = os.stat(PET_EVENT_FILE)
            except (FileNotFoundError, OSError):
                return
            
            current_mtime = stat.st_mtime
            if current_mtime == self.last_mtime:
                return
            self.last_mtime = current_mtime
            
            import tempfile
            temp_copy = os.path.join(tempfile.gettempdir(), "pet_event_copy.json")
            shutil.copy2(PET_EVENT_FILE, temp_copy)
            
            with open(temp_copy, "r", encoding="utf-8") as f:
                content = f.read().strip()
            if not content:
                return
            payload = json.loads(content)
            
            ts = payload.get("timestamp", 0)
            if ts > self.last_timestamp:
                self.last_timestamp = ts
                event = payload.get("event", "")
                data_dict = payload.get("data", {})
                print(f"[PET] ✅ Event diterima: {event} (ts={ts})", flush=True)
                self.on_event_received.emit(event, data_dict)
        except Exception as e:
            print(f"[PET] Poll error: {e}", flush=True)

class AnisaPet(QWidget):
    def __init__(self):
        super().__init__()
        self.is_talking, self.is_walking = False, False
        self.full_text, self.current_index = "", 0
        self.walk_dx, self.is_facing_left = -3, True
        self.personality = PersonalityEngine()

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAcceptDrops(True)

        self.screen_geo = QApplication.primaryScreen().availableGeometry()
        self.screen_width = self.screen_geo.width()
        self.setFixedHeight(360)
        self.setFixedWidth(260)

        self.bubble = ComicBubble()
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)
        self.img_label.setFixedHeight(UKURAN_ANISA)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(self.bubble, alignment=Qt.AlignHCenter | Qt.AlignBottom)
        layout.addWidget(self.img_label, alignment=Qt.AlignHCenter | Qt.AlignBottom)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.movie_idle = QMovie(get_path("anisa_idle"))
        self.movie_idle.setScaledSize(QSize(UKURAN_ANISA, UKURAN_ANISA))
        self.movie_idle.frameChanged.connect(self.update_frame)

        self.movie_walk = QMovie(get_path("anisa_walk"))
        self.movie_walk.setScaledSize(QSize(UKURAN_ANISA, UKURAN_ANISA))
        self.movie_walk.frameChanged.connect(self.update_frame)

        self.movie_idle.start()
        self.movie_walk.start()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_logic)
        self.timer.start(100)

        self.type_timer = QTimer(self)
        self.type_timer.timeout.connect(self.typewriter_tick)
        
        self.close_timer = QTimer(self)
        self.close_timer.setSingleShot(True)
        self.close_timer.timeout.connect(self.close_bubble)

        self.roam_max_x = self.screen_width - self.width() 
        self.roam_min_x = self.screen_width - self.width() - 228 
        self.move(self.roam_max_x, self.screen_geo.height() - self.height())
        
        self.poller = FilePollingClient()
        self.poller.on_event_received.connect(self.process_wsl_event)
        
        self.show()
        
        # Sapaan startup berdasarkan personality
        greeting = self.personality.get_greeting()
        QTimer.singleShot(1500, lambda: self.talk(greeting))
        show_toast("Anisa Pet 🌸", "Anisa sudah online dan siap tempur!")

    def process_wsl_event(self, event, data):
        self.set_animation("idle")
        
        if event == "bot_ready":
            self.talk("B.I.M.A Core sudah online komandan! Anisa siap tempur! 🌸✨")
            show_toast("🟢 B.I.M.A Core Online", "Semua sistem siap tempur!")
            
        elif event == "chat_received":
            self.personality.on_chat()
            user = data.get("user", "Seseorang")
            isi_pesan = data.get("message", "")
            flavor = self.personality.flavor_text("chat_received")
            
            if data.get("has_attachment"):
                self.talk(f"{flavor}\n📩 Pesan + file dari {user}:\n\"{isi_pesan}\"\n\nAnisa periksa dulu ya! 🤔")
            else:
                self.talk(f"{flavor}\n📩 Pesan dari {user}:\n\"{isi_pesan}\"\n\nAnisa lagi mikir nih... 🤔")
            
            show_toast(f"📩 Pesan dari {user}", isi_pesan[:100])
            
        elif event == "agent_assigned":
            team = data.get("team", "Agen")
            if "santai" in data.get("mode", ""):
                self.talk("Nggak ada tugas berat, kita ngobrol santai aja yuk! 😊")
            else:
                self.talk(f"Oke, aku minta tolong ke {team} buat ngerjain ini! Tunggu bentar ya 🚀")
                
        elif event == "file_generated":
            filename = data.get("filename", "")
            size = data.get("size_kb", 0)
            self.talk(f"Selesai! File {filename} ({size:.1f} KB) udah jadi nih! 📁")
            show_toast("📁 File Baru!", f"{filename} ({size:.1f} KB)")
            
        elif event == "task_completed":
            team = data.get("team", "Tim")
            durasi = data.get("duration_seconds", 0)
            hasil = data.get("result_text", "")
            
            self.personality.on_task_complete(durasi)
            flavor = self.personality.flavor_text("task_completed")
            mood = self.personality.data["mood"]
            
            mood_bar = "❤️" * (mood // 20) + "🖤" * (5 - mood // 20)
            self.talk(f"{flavor} [{team} | {durasi}s]\nMood: {mood_bar}\n\nBerikut laporannya:\n{hasil}")
            
            show_toast(f"✅ {team} Selesai!", f"{flavor} ({durasi}s)")

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() or event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        try: os.makedirs(WSL_BRAIN_DIR, exist_ok=True)
        except Exception as e:
            self.talk(f"Duh! Anisa gak bisa akses WSL sayang. Error: {e}")
            return

        if event.mimeData().hasUrls():
            berhasil, gagal = [], []
            for url in event.mimeData().urls():
                filepath = url.toLocalFile()
                ext = os.path.splitext(filepath)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    gagal.append(os.path.basename(filepath))
                    continue
                try:
                    filename = os.path.basename(filepath)
                    name, extension = os.path.splitext(filename)
                    dest_filename = f"{name}_{int(time.time())}{extension}"
                    shutil.copy2(filepath, os.path.join(WSL_BRAIN_DIR, dest_filename))
                    berhasil.append(filename)
                except Exception as e: gagal.append(f"{os.path.basename(filepath)} ({e})")

            if berhasil: self.talk(f"Siap komandan! {len(berhasil)} file masuk otak WSL!\nSekarang ketik /serap di Telegram ya! 🌸✨")
            if gagal: self.talk(f"⚠️ {len(gagal)} file gagal/ditolak.")

        elif event.mimeData().hasText():
            text = event.mimeData().text()
            dest_path = os.path.join(WSL_BRAIN_DIR, f"Catatan_Bima_{int(time.time())}.txt")
            try:
                with open(dest_path, "w", encoding="utf-8") as f: f.write(text)
                self.talk("Catatan masuk ke otak Anisa! Ketik /serap di Telegram ya! 🌸✨")
            except: self.talk("Gagal nyimpen catatan sayang :(")

        event.acceptProposedAction()

    def update_frame(self):
        pix = self.movie_walk.currentPixmap() if self.is_walking else self.movie_idle.currentPixmap()
        if not pix.isNull():
            if self.is_facing_left: pix = pix.transformed(QTransform().scale(-1, 1))
            self.img_label.setPixmap(pix)

    def set_animation(self, mode):
        self.is_walking = (mode == "walk")

    def talk(self, message):
        if self.type_timer.isActive():
            self.type_timer.stop()
        if self.close_timer.isActive():
            self.close_timer.stop()

        self.set_animation("idle")
        self.is_talking = True
        self.full_text = message
        self.current_index = 0
        self.bubble.show()
        
        # Langsung mainkan suara ketik saat pesan masuk!
        ketik = self._find_sound("ketik")
        if ketik:
            self._play_sound(ketik, "ketik_alias")
        
        # Suara Notifikasi tambahan (opsional)
        notif = self._find_sound("notif")
        if notif:
            self._play_sound(notif, "notif_alias")

        self.type_timer.start(10)

    def typewriter_tick(self):
        if self.current_index < len(self.full_text):
            self.current_index += 1
            self.bubble.update_text(self.full_text[:self.current_index])
            try:
                if self.current_index % 3 == 0:
                    ketik = self._find_sound("ketik")
                    if ketik:
                        self._play_sound(ketik, "ketik_alias")
                    else:
                        winsound.Beep(600, 8)
            except: pass
        else:
            self.type_timer.stop()
            # Waktu tampil bubble lebih lama untuk teks panjang
            display_time = max(8000, len(self.full_text) * 30)
            self.close_timer.start(display_time)

    def _find_sound(self, name):
        """Cari file suara dengan nama tertentu (support wav/mp3/mp4/m4a)"""
        for ext in ('.mp3', '.mp4', '.m4a', '.wav'):
            path = os.path.join(BASE_DIR, name + ext)
            if os.path.exists(path):
                return path
        return None

    def _play_sound(self, filepath, alias="snd"):
        """Putar audio menggunakan Windows MCI — support mp3/mp4/wav/m4a tanpa install tambahan"""
        mci = ctypes.windll.winmm.mciSendStringW
        mci(f'close {alias}', None, 0, 0)
        mci(f'open "{filepath}" alias {alias}', None, 0, 0)
        mci(f'play {alias}', None, 0, 0)

    def close_bubble(self):
        self.is_talking = False
        self.bubble.hide()

    def update_logic(self):
        if self.is_talking:
            self.set_animation("idle")
            return
        self.set_animation("walk")
        current_x = self.x()
        if current_x <= self.roam_min_x:
            self.walk_dx, self.is_facing_left = abs(self.walk_dx), False
        elif current_x >= self.roam_max_x:
            self.walk_dx, self.is_facing_left = -abs(self.walk_dx), True
        self.move(current_x + self.walk_dx, self.y())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_pos = event.globalPos() - self.pos()
            event.accept()
        elif event.button() == Qt.RightButton:
            self._start_mini_game()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self.drag_pos)
            event.accept()

    # ============================================================
    # UPGRADE #10: Mini-Games (Klik kanan Anisa)
    # ============================================================
    def _start_mini_game(self):
        import random
        game = random.choice(["emoji_quiz", "fun_fact", "fortune", "mood_check", "joke"])
        
        if game == "emoji_quiz":
            quizzes = [
                ("🐍 + 💻 = ?", "Python!"),
                ("🦀 + ⚡ = ?", "Rust!"),
                ("☕ + 📱 = ?", "Java!"),
                ("💎 + 🚂 = ?", "Ruby on Rails!"),
                ("🐘 + 🗄️ = ?", "PostgreSQL!"),
                ("🔥 + 🦊 = ?", "Firefox!"),
                ("🍎 + 🖥️ = ?", "macOS!"),
                ("🪟 + 💙 = ?", "Windows!"),
            ]
            q, a = random.choice(quizzes)
            self.talk(f"🎮 Tebak bahasa/app ini!\n\n{q}\n\n...jawabannya: {a}")
            self.personality.data["mood"] = min(100, self.personality.data["mood"] + 3)
            self.personality._save()
            
        elif game == "fun_fact":
            facts = [
                "🧠 Tahukah kamu? Otak manusia bisa memproses gambar dalam 13 milidetik!",
                "🦀 Rust sudah jadi bahasa 'paling dicintai' di StackOverflow 8 tahun berturut-turut!",
                "🐍 Python dinamai dari Monty Python, bukan ular!",
                "💾 Floppy disk pertama bisa menyimpan 80 KB — setara 1 email pendek!",
                "🌐 Website pertama di dunia masih online di info.cern.ch!",
                "🤖 AI pertama yang mengalahkan manusia di catur: Deep Blue (1997)!",
                "📡 Sinyal WiFi sebenarnya menggunakan frekuensi yang sama dengan microwave!",
                "🚀 Kode Apollo 11 ditulis oleh Margaret Hamilton — sepanjang 145.000 baris!",
            ]
            self.talk(random.choice(facts))
            
        elif game == "fortune":
            fortunes = [
                "🔮 Hari ini akan ada breakthrough di project kamu!",
                "🌟 Kode yang kamu tulis hari ini akan jadi masterpiece!",
                "💡 Inspirasi besar akan datang saat kamu ngopi nanti!",
                "🎯 Bug yang kamu cari ternyata ada di line yang paling tidak disangka!",
                "🌈 Semua deploy hari ini akan lancar tanpa error!",
                "⚡ Kamu akan menemukan library baru yang mengubah segalanya!",
                "🏆 Seseorang akan kagum dengan code kamu hari ini!",
                "🍀 Keberuntungan ada di sisi kamu — ship it!",
            ]
            self.talk(f"🥠 Ramalan Anisa:\n\n{random.choice(fortunes)}")
            self.personality.data["mood"] = min(100, self.personality.data["mood"] + 2)
            self.personality._save()
            
        elif game == "mood_check":
            p = self.personality.data
            mood = p["mood"]
            mood_bar = "❤️" * (mood // 20) + "🖤" * (5 - mood // 20)
            self.talk(
                f"📊 Status Anisa:\n\n"
                f"Mood: {mood_bar} ({mood}%)\n"
                f"Total Tasks: {p.get('total_tasks', 0)}\n"
                f"Tasks Hari Ini: {p.get('tasks_today', 0)}\n"
                f"Errors Hari Ini: {p.get('errors_today', 0)}\n\n"
                f"{'Anisa lagi happy! 🥰' if mood >= 70 else 'Kasih Anisa tugas biar semangat! 💪' if mood >= 40 else 'Anisa butuh perhatian... 🥺'}"
            )
            
        elif game == "joke":
            jokes = [
                "Kenapa programmer pakai kacamata?\nKarena mereka nggak bisa C# (see sharp)! 😂",
                "Apa bedanya bug dan fitur?\nKalau ada di production, itu fitur! 😏",
                "Kenapa array mulai dari 0?\nKarena mereka punya zero self-esteem! 🤣",
                "Git commit -m 'fix final'\nNarrator: It was not the final fix. 😅",
                "Ada 10 tipe orang di dunia:\nYang mengerti binary dan yang tidak! 🤓",
                "Knock knock!\nRace condition.\nWho's there? 🏃💨",
            ]
            self.talk(f"😂 Jokes Receh:\n\n{random.choice(jokes)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    pet = AnisaPet()
    sys.exit(app.exec_())
