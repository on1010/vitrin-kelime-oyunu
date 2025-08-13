from highrise import *
from highrise.models import *
from asyncio import run as arun
from flask import Flask
from threading import Thread
from highrise.__main__ import *
import random
import asyncio
import time

class Bot(BaseBot):
    def __init__(self):
        super().__init__()
        self.current_word = ""
        self.current_hint = ""
        self.revealed_letters = []
        self.game_active = False
        self.user_scores = {}
        self.hint_task = None
        self.words_database = [
            {"word": "kiraz", "hint": "Sakura ağacında yetişir, kırmızı renkli meyve"},
            {"word": "güneş", "hint": "Gökyüzünde parlayan, ışık ve ısı veren yıldız"},
            {"word": "deniz", "hint": "Tuzlu su kütlesi, balıkların yaşadığı yer"},
            {"word": "kalem", "hint": "Yazı yazmak için kullanılan araç"},
            {"word": "kitap", "hint": "Sayfaları olan, okumak için kullanılan nesne"},
            {"word": "çiçek", "hint": "Bahçede yetişen, güzel kokan renkli bitki"},
            {"word": "kuşlar", "hint": "Gökyüzünde uçan, kanatları olan canlılar"},
            {"word": "mutluluk", "hint": "İnsanın içini ısıtan güzel duygu"},
            {"word": "dostluk", "hint": "İnsanlar arasındaki güzel bağ"},
            {"word": "sevgi", "hint": "Kalbin en güzel duygusu"},
            {"word": "umut", "hint": "Geleceğe dair olumlu beklenti"},
            {"word": "şarkı", "hint": "Müzikle birlikte söylenen sözler"},
            {"word": "dans", "hint": "Müzik eşliğinde yapılan hareket"},
            {"word": "yıldız", "hint": "Gecede gökyüzünde parlayan nokta"},
            {"word": "rüzgar", "hint": "Havada hissedilen esinti"},
            {"word": "yağmur", "hint": "Bulutlardan düşen su damlacıkları"},
            {"word": "gökkuşağı", "hint": "Yağmur sonrası gökyüzünde görülen renkli ışık"},
            {"word": "kelebek", "hint": "Renkli kanatları olan uçan böcek"},
            {"word": "çilek", "hint": "Kırmızı renkli, tatlı küçük meyve"},
            {"word": "balık", "hint": "Suda yaşayan, yüzgeçli canlı"},
            {"word": "ağaç", "hint": "Toprağa kök salan, dalları olan büyük bitki"},
            {"word": "çocuk", "hint": "Küçük yaştaki insan"},
            {"word": "oyuncak", "hint": "Çocukların oynadığı eşya"},
            {"word": "hediye", "hint": "Birine sevgiyle verilen armağan"},
            {"word": "kahve", "hint": "Sabahları içilen sıcak içecek"},
            {"word": "pasta", "hint": "Doğum günlerinde kesilen tatlı"},
            {"word": "müzik", "hint": "Kulağa hoş gelen sesler bütünü"},
            {"word": "resim", "hint": "Boyalarla kağıda çizilen sanat eseri"},
            {"word": "hikaye", "hint": "Anlatılan kurgusal olay"},
            {"word": "hayal", "hint": "Zihindeeki kurgusal düşünce"}
        ]

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        print("Kelime oyunu botu başlatıldı!")
        await self.highrise.tg.create_task(self.highrise.teleport(
            session_metadata.user_id, Position(9.0, 0.25, 0.5, "FrontRight")))
        await self.highrise.chat("🎮 Kelime Oyunu Başladı! 🎮")
        await self.highrise.chat("Komutlar: !oyun (oyun başlat), !skor (skorunu gör), !stop (oyunu durdur)")
        await asyncio.sleep(3)
        await self.start_word_game()

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        await self.highrise.chat(f"Hoş geldin {user.username}! Kelime oyununa katıl!")
        if user.id not in self.user_scores:
            self.user_scores[user.id] = {"score": 0, "username": user.username}

    async def on_user_leave(self, user: User):
        print(f"{user.username} oyunu terk etti")

    async def on_chat(self, user: User, message: str) -> None:
        message = message.strip().lower()

        # Initialize user if not exists
        if user.id not in self.user_scores:
            self.user_scores[user.id] = {"score": 0, "username": user.username}

        # Game commands
        if message == "!oyun" and await self.is_user_allowed(user):
            await self.start_word_game()
            return

        if message == "!stop" and await self.is_user_allowed(user):
            await self.stop_word_game()
            return

        if message == "!skor":
            user_score = self.user_scores[user.id]["score"]
            await self.highrise.chat(f"{user.username}: {user_score} puan")
            return

        if message == "!skorlar" and await self.is_user_allowed(user):
            await self.show_leaderboard()
            return

        # Check if guess is correct
        if self.game_active and message == self.current_word.lower():
            self.user_scores[user.id]["score"] += 20
            await self.highrise.chat(f"🎉 Tebrikler {user.username}! Doğru cevap: {self.current_word.upper()}")
            await self.highrise.chat(f"📈 +20 puan kazandın! Toplam puanın: {self.user_scores[user.id]['score']}")
            await asyncio.sleep(2)
            await self.start_new_round()

        # Moderator chat functionality
        if await self.is_user_allowed(user) and message.startswith(''):
            try:
                xxx = message[0:]
                await self.highrise.chat(xxx)
            except:
                print("error in chat")

    async def start_word_game(self):
        if self.game_active:
            await self.highrise.chat("⚠️ Oyun zaten devam ediyor!")
            return

        self.game_active = True
        await self.highrise.chat("🎮 Yeni kelime oyunu başlıyor! Hazır olun...")
        await asyncio.sleep(2)
        await self.start_new_round()

    async def start_new_round(self):
        if not self.game_active:
            return

        # Select random word
        word_data = random.choice(self.words_database)
        self.current_word = word_data["word"]
        self.current_hint = word_data["hint"]
        self.revealed_letters = []

        # Create initial display
        word_display = "_" * len(self.current_word)

        await self.highrise.chat(f"📝 İpucu: {self.current_hint}")
        await self.highrise.chat(f"🔤 Kelime: {' '.join(word_display)} ({len(self.current_word)} harf)")

        # Start hint task
        if self.hint_task:
            self.hint_task.cancel()
        self.hint_task = asyncio.create_task(self.give_hints())

    async def give_hints(self):
        try:
            hint_count = 0
            max_hints = min(3, len(self.current_word) - 1)  # Maximum 3 hints or word length - 1

            while hint_count < max_hints and self.game_active:
                await asyncio.sleep(5)  # Wait 5 seconds

                if not self.game_active:
                    break

                # Select a random position that hasn't been revealed
                available_positions = [i for i in range(len(self.current_word)) 
                                     if i not in self.revealed_letters]

                if available_positions:
                    pos = random.choice(available_positions)
                    self.revealed_letters.append(pos)

                    # Create word display with revealed letters
                    word_display = ""
                    for i, letter in enumerate(self.current_word):
                        if i in self.revealed_letters:
                            word_display += letter
                        else:
                            word_display += "_"

                    await self.highrise.chat(f"💡 İpucu {hint_count + 1}: {' '.join(word_display)}")
                    hint_count += 1

            # If no one guessed after all hints, reveal answer
            if self.game_active:
                await asyncio.sleep(5)
                if self.game_active:  # Check again in case it was stopped
                    await self.highrise.chat(f"⏰ Süre doldu! Cevap: {self.current_word.upper()}")
                    await asyncio.sleep(3)
                    await self.start_new_round()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in hint system: {e}")

    async def stop_word_game(self):
        self.game_active = False
        if self.hint_task:
            self.hint_task.cancel()
            self.hint_task = None
        await self.highrise.chat("🛑 Kelime oyunu durduruldu!")
        await self.show_leaderboard()

    async def show_leaderboard(self):
        if not self.user_scores:
            await self.highrise.chat("📊 Henüz kimse puan kazanmadı!")
            return

        # Sort users by score
        sorted_users = sorted(self.user_scores.items(), 
                            key=lambda x: x[1]["score"], reverse=True)

        await self.highrise.chat("🏆 SKOR TABLOSU 🏆")
        for i, (user_id, data) in enumerate(sorted_users[:5]):  # Top 5
            position_emoji = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
            await self.highrise.chat(f"{position_emoji} {data['username']}: {data['score']} puan")

    async def on_whisper(self, user: User, message: str) -> None:
        if await self.is_user_allowed(user) and message.startswith(''):
            try:
                xxx = message[0:]
                await self.highrise.chat(xxx)
            except:
                print("error in whisper")

    async def is_user_allowed(self, user: User) -> bool:
        user_privileges = await self.highrise.get_room_privilege(user.id)
        return user_privileges.moderator or user.username in ["Atekinz", ""]

    async def run(self, room_id, token) -> None:
        await __main__.main(self, room_id, token)

class WebServer():
    def __init__(self):
        self.app = Flask(__name__)

        @self.app.route('/')
        def index() -> str:
            return "Word Game Bot Alive"

    def run(self) -> None:
        self.app.run(host='0.0.0.0', port=8080)

    def keep_alive(self):
        t = Thread(target=self.run)
        t.start()

class RunBot():
    room_id = "65b0c62e2ba06c8f8a095355"
    bot_token = "b350dbbbb343dcff86546906b33952416ce80933bea0419d45240756e45cc5dc"
    bot_file = "main"
    bot_class = "Bot"

    def __init__(self) -> None:
        self.definitions = [
            BotDefinition(
                getattr(import_module(self.bot_file), self.bot_class)(),
                self.room_id, self.bot_token)
        ] 

    def run_loop(self) -> None:
        while True:
            try:
                arun(main(self.definitions)) 
            except Exception as e:
                import traceback
                print("Caught an exception:")
                traceback.print_exc()
                time.sleep(1)
                continue

if __name__ == "__main__":
    WebServer().keep_alive()
    RunBot().run_loop()