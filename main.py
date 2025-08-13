
from highrise import *
from highrise.models import *
from asyncio import run as arun
from flask import Flask
from threading import Thread
from highrise.__main__ import *
import random
import asyncio
import time
import json
import os

class Bot(BaseBot):
    def __init__(self):
        super().__init__()
        self.current_word = ""
        self.current_hint = ""
        self.revealed_letters = []
        self.game_active = False
        self.user_scores = {}
        self.hint_task = None
        self.words_database = []
        self.saved_positions = {}
        self.current_question_index = 0  # Sıralı soru takibi
        self.load_questions()
        self.load_scores()
        self.load_positions()

    def load_questions(self):
        """JSON dosyasından soruları yükle"""
        try:
            with open('sorular.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.words_database = data.get('sorular', [])
            print(f"✅ {len(self.words_database)} soru yüklendi!")
        except FileNotFoundError:
            print("❌ sorular.json dosyası bulunamadı!")
            self.words_database = [
                {"kelime": "test", "ipucu": "Bu bir test kelimesidir"}
            ]
        except Exception as e:
            print(f"❌ Sorular yüklenirken hata: {e}")

    def load_scores(self):
        """JSON dosyasından skorları yükle"""
        try:
            with open('skorlar.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                skorlar = data.get('skorlar', {})
                # String ID'leri integer'a çevir
                self.user_scores = {int(k) if k.isdigit() else k: v for k, v in skorlar.items()}
            print(f"✅ {len(self.user_scores)} kullanıcı skoru yüklendi!")
        except FileNotFoundError:
            print("📊 Yeni skor dosyası oluşturulacak")
            self.user_scores = {}
        except Exception as e:
            print(f"❌ Skorlar yüklenirken hata: {e}")
            self.user_scores = {}

    def save_scores(self):
        """Skorları JSON dosyasına kaydet"""
        try:
            # Integer ID'leri string'e çevir (JSON uyumluluğu için)
            skorlar_str = {str(k): v for k, v in self.user_scores.items()}
            data = {"skorlar": skorlar_str}
            with open('skorlar.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Skorlar kaydedilirken hata: {e}")

    def load_positions(self):
        """Kayıtlı pozisyonları yükle"""
        try:
            with open('pozisyonlar.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.saved_positions = data.get('pozisyonlar', {})
            print(f"✅ {len(self.saved_positions)} pozisyon yüklendi!")
        except FileNotFoundError:
            print("📍 Yeni pozisyon dosyası oluşturulacak")
            self.saved_positions = {}
        except Exception as e:
            print(f"❌ Pozisyonlar yüklenirken hata: {e}")
            self.saved_positions = {}

    def save_positions(self):
        """Pozisyonları JSON dosyasına kaydet"""
        try:
            data = {"pozisyonlar": self.saved_positions}
            with open('pozisyonlar.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Pozisyonlar kaydedilirken hata: {e}")

    async def on_start(self, session_metadata: SessionMetadata) -> None:
        print("🎮 Vitrin Odası Kelime Oyunu Botu Başlatıldı!")
        print(f"📚 Toplam {len(self.words_database)} soru hazır!")
        
        # Kayıtlı pozisyon varsa oraya git, yoksa varsayılan pozisyona
        if self.saved_positions:
            # En son kaydedilen pozisyonu kullan
            last_position = list(self.saved_positions.values())[-1]
            saved_pos = Position(
                last_position["x"], 
                last_position["y"], 
                last_position["z"], 
                last_position["facing"]
            )
            await self.highrise.tg.create_task(self.highrise.teleport(
                session_metadata.user_id, saved_pos))
            print(f"📍 Kayıtlı pozisyona ışınlandım!")
        else:
            await self.highrise.tg.create_task(self.highrise.teleport(
                session_metadata.user_id, Position(9.0, 0.25, 0.5, "FrontRight")))
            print("📍 Varsayılan pozisyona ışınlandım!")
        
        await self.highrise.chat("⏱️ ✨ KELİME OYUNU ✨ ⏱️")
        await asyncio.sleep(1)
        await self.highrise.chat(f"📚 {len(self.words_database)} soru hazır!")
        await asyncio.sleep(1)
        await self.highrise.chat("🎯 KOMUTLAR: !oyun, !skor, !skorlar, !stop, !gel")
        await asyncio.sleep(1)
        await self.highrise.chat("🏆 İlk 5'te yerini al, skorunu koru!")
        await asyncio.sleep(3)
        await self.start_word_game()

    async def on_user_join(self, user: User, position: Position | AnchorPosition) -> None:
        if user.id not in self.user_scores:
            self.user_scores[user.id] = {"score": 0, "username": user.username}
            self.save_scores()

    async def on_user_leave(self, user: User):
        print(f"👋 {user.username} oyunu terk etti")

    async def on_chat(self, user: User, message: str) -> None:
        message = message.strip().lower()

        # Kullanıcı skoru başlat
        if user.id not in self.user_scores:
            self.user_scores[user.id] = {"score": 0, "username": user.username}
            self.save_scores()

        # Moderatör komutları
        if await self.is_user_allowed(user):
            if message.startswith("!skorsıfırla "):
                target_username = message.split(" ", 1)[1].replace("@", "")
                await self.reset_user_score(target_username)
                return
            
            if message == "!skorreset":
                await self.reset_all_scores()
                return
                
            if message == "!sorubaşla":
                self.current_question_index = 0
                await self.highrise.chat("🔄 Sorular başa alındı! Yeni oyun başlatılıyor...")
                await self.start_word_game()
                return

        # Oyun komutları
        if message == "!oyun":
            if await self.is_user_allowed(user):
                await self.start_word_game()
            else:
                await self.highrise.chat("🔒 Sadece moderatörler oyun başlatabilir!")
            return

        if message == "!stop":
            if await self.is_user_allowed(user):
                await self.stop_word_game()
            else:
                await self.highrise.chat("🔒 Sadece moderatörler oyunu durdurabilir!")
            return

        if message == "!skor":
            user_score = self.user_scores[user.id]["score"]
            rank = self.get_user_rank(user.id)
            await self.highrise.chat(f"📊 @{user.username}: {user_score} puan (#{rank})")
            return

        if message == "!skorlar":
            await self.show_leaderboard()
            return

        if message == "!yardım" or message == "!help":
            await self.highrise.chat("🎮 ═══ KOMUTLAR ═══ 🎮")
            await asyncio.sleep(0.5)
            await self.highrise.chat("🎯 !oyun - Yeni oyun başlat (Mod)")
            await self.highrise.chat("🛑 !stop - Oyunu durdur (Mod)")
            await self.highrise.chat("📊 !skor - Kendi skorunu gör")
            await self.highrise.chat("🏆 !skorlar - Skor tablosunu gör")
            await self.highrise.chat("✨ !gel - Botu yanına çağır (Mod)")
            await self.highrise.chat("🔄 !sorubaşla - Soruları başa al (Mod)")
            await asyncio.sleep(0.5)
            await self.highrise.chat("💡 Doğru tahmin: +20 puan!")
            return

        # !gel komutu - bot teleport
        if message == "!gel":
            if await self.is_user_allowed(user):
                try:
                    # Kullanıcının mevcut pozisyonunu al ve kaydet
                    response = await self.highrise.get_room_users()
                    user_position = None
                    
                    for room_user, position in response.content:
                        if room_user.id == user.id:
                            user_position = position
                            break
                    
                    if user_position:
                        # Pozisyonu kaydet
                        self.saved_positions[str(user.id)] = {
                            "x": user_position.x,
                            "y": user_position.y,
                            "z": user_position.z,
                            "facing": user_position.facing,
                            "username": user.username
                        }
                        self.save_positions()
                        
                        # Bot'u kullanıcının yanına ışınla
                        await self.highrise.teleport(self.highrise.my_id, user_position)
                        await self.highrise.chat(f"✨ @{user.username} yanına ışınlandım ve pozisyonunu kaydettim!")
                    else:
                        await self.highrise.chat("❌ Pozisyonunuz algılanamadı!")
                except Exception as e:
                    await self.highrise.chat("❌ Işınlanma başarısız!")
                    print(f"Teleport hatası: {e}")
            else:
                await self.highrise.chat("🔒 Sadece moderatörler beni çağırabilir!")
            return

        # Doğru cevap kontrolü
        if self.game_active and message == self.current_word.lower():
            # Oyunu durdur
            self.game_active = False
            if self.hint_task:
                self.hint_task.cancel()
                self.hint_task = None
            
            # Puan hesapla
            self.user_scores[user.id]["score"] += 20
            self.save_scores()
            rank = self.get_user_rank(user.id)
            
            # Tek mesajda cevabı ve puanı göster
            await self.highrise.chat(f"🎉 BRAVO @{user.username}! 📈 +20 puan! Toplam: {self.user_scores[user.id]['score']} (#{rank})")
            
            # Oyun değişkenlerini temizle
            self.current_word = ""
            self.current_hint = ""
            self.revealed_letters = []
            
            # 8 saniye bekle, sonra yeni kelimeye geç
            await asyncio.sleep(8)
            await self.start_new_round()

        # Moderatör chat özelliği kaldırıldı (her mesajı tekrarlıyordu)

    def get_user_rank(self, user_id):
        """Kullanıcının sırasını bul"""
        sorted_users = sorted(self.user_scores.items(), 
                            key=lambda x: x[1]["score"], reverse=True)
        for i, (uid, _) in enumerate(sorted_users, 1):
            if uid == user_id:
                return i
        return len(sorted_users)

    async def reset_user_score(self, username):
        """Belirli kullanıcının skorunu sıfırla"""
        found = False
        for user_id, data in self.user_scores.items():
            if data["username"].lower() == username.lower():
                data["score"] = 0
                found = True
                self.save_scores()
                await self.highrise.chat(f"🔄 @{data['username']} skorunu sıfırladım!")
                break
        
        if not found:
            await self.highrise.chat(f"❌ {username} kullanıcısı bulunamadı!")

    async def reset_all_scores(self):
        """Tüm skorları sıfırla"""
        for user_data in self.user_scores.values():
            user_data["score"] = 0
        self.save_scores()
        await self.highrise.chat("🔄 TÜM SKORLAR SIFIRLANDI!")
        await self.show_leaderboard()

    async def start_word_game(self):
        if self.game_active:
            await self.highrise.chat("⚠️ Oyun zaten devam ediyor!")
            return

        if not self.words_database:
            await self.highrise.chat("❌ Sorular yüklenemedi!")
            return

        self.game_active = True
        await self.highrise.chat("🎮 ✨ YENİ OYUN BAŞLIYOR ✨")
        await asyncio.sleep(0.5)
        await self.highrise.chat("🚀 Hazır mısınız? 3...")
        await asyncio.sleep(0.5)
        await self.highrise.chat("🔥 2...")
        await asyncio.sleep(0.5)
        await self.highrise.chat("⚡ 1...")
        await asyncio.sleep(0.5)
        await self.start_new_round()

    async def start_new_round(self):
        if not self.game_active:
            self.game_active = True

        if not self.words_database:
            await self.highrise.chat("❌ Sorular bulunamadı!")
            return

        # Sıralı soru seçimi
        if self.current_question_index >= len(self.words_database):
            # Tüm sorular bittiyse başa dön
            self.current_question_index = 0
            await self.highrise.chat("🔄 Tüm sorular tamamlandı! Başa dönülüyor...")
            await asyncio.sleep(2)

        word_data = self.words_database[self.current_question_index]
        self.current_word = word_data["kelime"]
        self.current_hint = word_data["ipucu"]
        self.revealed_letters = []
        
        # Bir sonraki soru için index'i artır
        self.current_question_index += 1

        # Başlangıç gösterimi
        word_display = "_" * len(self.current_word)

        await self.highrise.chat(f"📝 Soru {self.current_question_index}/{len(self.words_database)}")
        await asyncio.sleep(0.5)
        await self.highrise.chat(f"💡 İpucu: {self.current_hint}")
        await asyncio.sleep(0.5)
        await self.highrise.chat(f"🔤 Kelime: {' '.join(word_display)} ({len(self.current_word)} harf)")

        # İpucu sistemini başlat
        if self.hint_task:
            self.hint_task.cancel()
        self.hint_task = asyncio.create_task(self.give_hints())

    async def give_hints(self):
        try:
            hint_count = 0
            # Sadece 1 harf gizli kalana kadar devam et
            max_hints = len(self.current_word) - 1
            
            while hint_count < max_hints and self.game_active:
                await asyncio.sleep(6)

                if not self.game_active:
                    break

                # Açılacak harf pozisyonu seç
                available_positions = [i for i in range(len(self.current_word)) 
                                     if i not in self.revealed_letters]

                if available_positions:
                    pos = random.choice(available_positions)
                    self.revealed_letters.append(pos)

                    # Kelime görünümünü oluştur
                    word_display = ""
                    for i, letter in enumerate(self.current_word):
                        if i in self.revealed_letters:
                            word_display += letter
                        else:
                            word_display += "_"

                    await self.highrise.chat(f"💡 İpucu {hint_count + 1}: {' '.join(word_display)}")
                    hint_count += 1

            # Son 1 harf kaldığında kimse bilemezse sonraki soruya geç
            if self.game_active:
                await asyncio.sleep(8)
                if self.game_active:
                    correct_word = self.current_word.upper()
                    self.game_active = False  # Oyunu durdur
                    
                    # Oyun değişkenlerini temizle
                    self.current_word = ""
                    self.current_hint = ""
                    self.revealed_letters = []
                    
                    await self.highrise.chat(f"❌ Kimse bulamadı! ✅ Cevap: {correct_word}")
                    await asyncio.sleep(8)
                    await self.start_new_round()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ İpucu sisteminde hata: {e}")

    async def stop_word_game(self):
        self.game_active = False
        if self.hint_task:
            self.hint_task.cancel()
            self.hint_task = None
        await self.highrise.chat("🛑 Oyun durduruldu!")
        await asyncio.sleep(0.5)
        await self.show_leaderboard()

    async def show_leaderboard(self):
        if not self.user_scores:
            await self.highrise.chat("📊 Henüz kimse puan kazanmadı!")
            return

        # Skorlara göre sırala
        sorted_users = sorted(self.user_scores.items(), 
                            key=lambda x: x[1]["score"], reverse=True)

        # İlk 5'i göster
        rank_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        
        leaderboard_text = "🏆 ═══ SKOR TABLOSU ═══ 🏆\n"
        
        for i, (user_id, data) in enumerate(sorted_users[:5]):
            emoji = rank_emojis[i] if i < 5 else f"{i+1}️⃣"
            star_count = data["score"] // 100  # Her 100 puan için bir yıldız
            stars = f" {star_count}X ⭐" if star_count > 0 else ""
            leaderboard_text += f"{emoji} @{data['username']}: {data['score']} puan{stars}\n"
        
        total_players = len([s for s in self.user_scores.values() if s["score"] > 0])
        leaderboard_text += f"👥 Toplam {total_players} oyuncu yarışıyor!"
        
        await self.highrise.chat(leaderboard_text)

    async def on_whisper(self, user: User, message: str) -> None:
        # Whisper özelliği kaldırıldı (mesajları tekrarlıyordu)
        pass

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
            return "🎮 Gelişmiş Kelime Oyunu Botu Aktif! 🎮"

    def run(self) -> None:
        self.app.run(host='0.0.0.0', port=8080)

    def keep_alive(self):
        t = Thread(target=self.run)
        t.start()

class RunBot():
    room_id = "685fe9208ab075915779c70e"
    bot_token = "1604c7f069901b0b24d5756cd67b6be77611988fe219731182a0a5e69c176482"
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
