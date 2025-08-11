# --- YENİ SLASH KOMUTLU, DÖNGÜLÜ, EMBED TASARIMLI MÜZİK BOTU ---
import discord
from discord.ext import commands
from discord import app_commands, PCMVolumeTransformer
import os
import asyncio

from yt_dlp import YoutubeDL
from youtubesearchpython import VideosSearch
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv

load_dotenv("spot.env")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
sp = None
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    sp = Spotify(auth_manager=SpotifyClientCredentials())

intents = discord.Intents.default()
intents.message_content = True


class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents)
    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()
music_volumes = {}  # guild_id: float (0.0-2.0)

def get_volume(guild_id):
    return music_volumes.get(guild_id, 1.0)

def set_volume(guild_id, value):
    music_volumes[guild_id] = value

import re
# Slash komut: /ses
@bot.tree.command(name="ses", description="Çalan müziğin ses seviyesini ayarla (1-200 arası).")
@app_commands.describe(seviye="Ses seviyesi (varsayılan 100, 1-200 arası)")
async def ses(interaction: discord.Interaction, seviye: int):
    voice_client = interaction.guild.voice_client
    if not voice_client or not voice_client.is_playing():
        embed = discord.Embed(title="Ses Ayarlanamadı", description="Şu anda çalan bir müzik yok.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    if seviye < 1 or seviye > 200:
        embed = discord.Embed(title="Geçersiz Değer", description="Ses seviyesi 1 ile 200 arasında olmalı.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    source = voice_client.source
    if hasattr(source, 'volume'):
        source.volume = seviye / 100
        set_volume(interaction.guild.id, seviye / 100)
        embed = discord.Embed(title="Ses Seviyesi Değişti", description=f"Yeni ses seviyesi: **{seviye}**", color=discord.Color.green())
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Ses Ayarlanamadı", description="Ses kaynağı değiştirilemedi.", color=discord.Color.red())
        await interaction.response.send_message(embed=embed, ephemeral=True)

music_queues = {}
music_loops = {}
original_playlists = {}  # guild_id: [şarkı dict listesi]
now_playing = {}  # guild_id: şarkı dict

def get_queue(guild_id):
    if guild_id not in music_queues:
        music_queues[guild_id] = []
    if guild_id not in original_playlists:
        original_playlists[guild_id] = []
    return music_queues[guild_id]

def is_looping(guild_id):
    return music_loops.get(guild_id, False)

async def play_next(interaction, voice_client, retry=False):
    queue = get_queue(interaction.guild.id)
    guild_id = interaction.guild.id
    global now_playing
    if queue:
        info = queue.pop(0)
        url2 = info['url']
        title = info['title']
        ekleyen = info.get('ekleyen')
        def after_playing(error=None):
            if is_looping(guild_id):
                if not queue and original_playlists.get(guild_id):
                    music_queues[guild_id] = original_playlists[guild_id].copy()
            fut = asyncio.run_coroutine_threadsafe(play_next(interaction, voice_client), bot.loop)
        try:
            audio = discord.FFmpegPCMAudio(url2, options='-vn')
            volume = get_volume(guild_id)
            source = PCMVolumeTransformer(audio, volume=volume)
            voice_client.play(source, after=after_playing)
            now_playing[guild_id] = info
            embed = discord.Embed(title="Açılan Şarkı", description=f'**{title}** (Ekleyen: {ekleyen})', color=discord.Color.green())
            asyncio.run_coroutine_threadsafe(interaction.channel.send(embed=embed), bot.loop)
        except Exception as e:
            err_str = str(e)
            if 'SABR' in err_str or 'missing a url' in err_str or 'DRM' in err_str:
                embed = discord.Embed(title="Korumalı Şarkı Atlandı", description=f'**{title}** YouTube tarafından korumalı (SABR/DRM) olduğu için oynatılamıyor. Endişelenme, sıradaki şarkıya geçiyorum! 🎵', color=discord.Color.orange())
                asyncio.run_coroutine_threadsafe(interaction.channel.send(embed=embed), bot.loop)
                asyncio.run_coroutine_threadsafe(play_next(interaction, voice_client), bot.loop)
                return
            if not retry:
                asyncio.run_coroutine_threadsafe(play_next(interaction, voice_client, retry=True), bot.loop)
            else:
                embed = discord.Embed(title="Şarkı Atlandı", description=f'**{title}** oynatılamıyor, sıradaki şarkıya geçiliyor.\nHata: {e}', color=discord.Color.orange())
                asyncio.run_coroutine_threadsafe(interaction.channel.send(embed=embed), bot.loop)
                asyncio.run_coroutine_threadsafe(play_next(interaction, voice_client), bot.loop)
    else:
        now_playing[guild_id] = None
        embed = discord.Embed(title="Kuyrukta başka şarkı yok", color=discord.Color.red())
        asyncio.run_coroutine_threadsafe(interaction.channel.send(embed=embed), bot.loop)

@bot.event
async def on_ready():
    activity = discord.Activity(type=discord.ActivityType.listening, name="🎶 Müziğin akışı, Lyrica’nın dokunuşuyla sunucunuzda.")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(f'Bot {bot.user} olarak giriş yapıldı!')

@bot.tree.command(name="ping", description="Botun yanıt verip vermediğini test eder.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong!", ephemeral=True)


def parse_spotify_url(url):
    """Spotify linkinden (track, playlist, album) tip ve ID döndürür."""
    m = re.match(r"https?://open\.spotify\.com/(track|playlist|album)/([a-zA-Z0-9]+)", url)
    if m:
        return m.group(1), m.group(2)
    return None, None

@bot.tree.command(name="mp", description="Müzik çal veya sıraya ekle. Şarkı adı, YouTube/Spotify video veya playlist linki yazabilirsin.")
@app_commands.describe(query="Şarkı adı, YouTube/Spotify video veya playlist linki")
async def mp(interaction: discord.Interaction, query: str):
    await interaction.response.defer()
    if not interaction.user.voice or not interaction.user.voice.channel:
        embed = discord.Embed(title="Ses Kanalı Gerekli", description=f'{interaction.user.mention} önce bir ses kanalına katılmalısın!', color=discord.Color.red())
        await interaction.followup.send(embed=embed, ephemeral=True)
        return
    channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client
    if not voice_client:
        voice_client = await channel.connect()
    elif voice_client.channel != channel:
        await voice_client.move_to(channel)


    # Spotify linki kontrolü (her varyasyon için)
    if sp:
        sp_type, sp_id = parse_spotify_url(query.strip())
        if sp_type and sp_id:
            embed = discord.Embed(title="Spotify Listesi Ekleniyor", description="Spotify içeriği işleniyor, lütfen bekleyin...", color=discord.Color.blurple())
            await interaction.followup.send(embed=embed)
            tracks = []
            try:
                if sp_type == "track":
                    track = sp.track(sp_id)
                    tracks = [track]
                elif sp_type == "playlist":
                    playlist = sp.playlist(sp_id)
                    tracks = [item["track"] for item in playlist["tracks"]["items"] if item.get("track")]
                elif sp_type == "album":
                    album = sp.album(sp_id)
                    tracks = album["tracks"]["items"]
            except Exception as e:
                embed = discord.Embed(title="Spotify Hatası", description=f"Spotify içeriği alınamadı: {e}", color=discord.Color.red())
                await interaction.edit_original_response(embed=embed)
                return
            queue = get_queue(interaction.guild.id)
            eklenen = 0
            for track in tracks:
                name = track.get("name")
                artists = ", ".join([a["name"] for a in track.get("artists", [])])
                search_query = f"{name} {artists} audio"
                search = VideosSearch(search_query, limit=3)
                result = search.result()
                found = False
                for video in result["result"]:
                    url = video["link"]
                    title = video["title"]
                    # DRM hatası olup olmadığını test etmek için yt-dlp ile info çekmeye çalış
                    ydl_opts = {'format': 'bestaudio/best', 'quiet': True, 'skip_download': True, 'noplaylist': True}
                    try:
                        with YoutubeDL(ydl_opts) as ydl:
                            ydl.extract_info(url, download=False)
                        song = {"url": url, "title": title, "ekleyen": interaction.user.mention}
                        queue.append(song)
                        eklenen += 1
                        found = True
                        break
                    except Exception:
                        continue
                # Hiçbir uygun video bulunamazsa şarkıyı atla
            if eklenen == 0:
                embed = discord.Embed(title="Spotify Hatası", description="Hiçbir şarkı eklenemedi.", color=discord.Color.red())
                await interaction.edit_original_response(embed=embed)
                return
            desc = f"{eklenen} Spotify şarkısı sıraya eklendi!"
            embed = discord.Embed(title="Spotify Sıraya Eklendi", description=desc, color=discord.Color.green())
            await interaction.edit_original_response(embed=embed)
            if not voice_client.is_playing():
                await play_next(interaction, voice_client)
            return

    # --- YouTube playlist ekleme ---
    if 'playlist' in query or 'list=' in query:
        embed = discord.Embed(title="Playlist Ekleniyor", description="Oynatma listesi işleniyor, lütfen bekleyin...", color=discord.Color.blurple())
        await interaction.followup.send(embed=embed)
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'skip_download': True,
        }
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get('entries', [])
        queue = get_queue(interaction.guild.id)
        eklenen = 0
        atlanan = 0
        for entry in entries:
            if entry.get('ie_key') == 'Youtube' and entry.get('id'):
                video_url = f'https://www.youtube.com/watch?v={entry["id"]}'
                # Oynatılabilir mi kontrolü
                try:
                    with YoutubeDL({'format': 'bestaudio/best', 'quiet': True, 'skip_download': True, 'noplaylist': True}) as ydl:
                        ydl.extract_info(video_url, download=False)
                    song = {'url': video_url, 'title': entry.get('title', 'Bilinmeyen'), 'ekleyen': interaction.user.mention}
                    queue.append(song)
                    eklenen += 1
                except Exception:
                    atlanan += 1
        if eklenen == 0:
            embed = discord.Embed(title="Playlist Hatası", description="Oynatma listesinden şarkı bulunamadı veya eklenemedi.", color=discord.Color.red())
            await interaction.edit_original_response(embed=embed)
            return
        desc = f"{eklenen} şarkı sıraya eklendi!"
        if atlanan > 0:
            desc += f"\n{atlanan} şarkı atlandı (oynatılamıyor, telifli veya kısıtlı olabilir)."
        embed = discord.Embed(title="Playlist Sıraya Eklendi", description=desc, color=discord.Color.green())
        await interaction.edit_original_response(embed=embed)
        if len(queue) > 0:
            original_playlists[interaction.guild.id] = queue.copy()
        if not voice_client.is_playing():
            await play_next(interaction, voice_client)
        return

    # --- Tekli şarkı ekleme (YouTube arama) ---
    if not (query.startswith('http://') or query.startswith('https://')):
        await interaction.followup.send(embed=discord.Embed(title="Şarkı Aranıyor", description=f'"{query}" aranıyor...', color=discord.Color.blurple()))
        search = VideosSearch(query, limit=5)
        result = search.result()
        if not result['result']:
            embed = discord.Embed(title="Şarkı Bulunamadı", description=f'{interaction.user.mention} aradığın şarkı bulunamadı.', color=discord.Color.red())
            await interaction.followup.send(embed=embed)
            return
        found = False
        atlanan = 0
        for video in result['result']:
            url = video['link']
            title = video['title']
            ydl_opts = {
                'format': 'bestaudio/best',
                'quiet': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'outtmpl': 'song.%(ext)s',
                'noplaylist': True,
            }
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                song = {'url': info['url'], 'title': title, 'ekleyen': interaction.user.mention}
                queue = get_queue(interaction.guild.id)
                queue.append(song)
                if len(queue) > 0:
                    original_playlists[interaction.guild.id] = queue.copy()
                if not voice_client.is_playing():
                    await play_next(interaction, voice_client)
                    embed = discord.Embed(title="Şarkı Çalınıyor", description=f'{interaction.user.mention} tarafından eklenen şarkı çalınıyor: **{title}**', color=discord.Color.green())
                    await interaction.followup.send(embed=embed)
                else:
                    embed = discord.Embed(title="Sıraya Eklendi", description=f'{interaction.user.mention} tarafından sıraya eklendi: **{title}**', color=discord.Color.blurple())
                    await interaction.followup.send(embed=embed)
                found = True
                break
            except Exception:
                atlanan += 1
                continue
        if not found:
            embed = discord.Embed(title="Şarkı Eklenemedi", description=f'Hiçbir arama sonucu oynatılamıyor. {atlanan} sonuç atlandı. (Telifli veya kısıtlı olabilir)', color=discord.Color.red())
            await interaction.followup.send(embed=embed)
        elif atlanan > 0:
            embed = discord.Embed(title="Uyarı", description=f'{atlanan} arama sonucu atlandı (oynatılamıyor, telifli veya kısıtlı olabilir).', color=discord.Color.orange())
            await interaction.followup.send(embed=embed)
        return

    # --- YouTube linkiyle şarkı ekleme ---
    if query.startswith('http://') or query.startswith('https://'):
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'extractaudio': True,
            'audioformat': 'mp3',
            'outtmpl': 'song.%(ext)s',
            'noplaylist': True,
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(query, download=False)
            title = info.get('title', None)
            song = {'url': info['url'], 'title': title, 'ekleyen': interaction.user.mention}
            queue = get_queue(interaction.guild.id)
            queue.append(song)
            if len(queue) > 0:
                original_playlists[interaction.guild.id] = queue.copy()
            if not voice_client.is_playing():
                await play_next(interaction, voice_client)
                embed = discord.Embed(title="Şarkı Çalınıyor", description=f'{interaction.user.mention} tarafından eklenen şarkı çalınıyor: **{title}**', color=discord.Color.green())
            else:
                embed = discord.Embed(title="Sıraya Eklendi", description=f'{interaction.user.mention} tarafından sıraya eklendi: **{title}**', color=discord.Color.blurple())
            await interaction.followup.send(embed=embed)
        except Exception:
            # Oynatılamazsa, başlıkla arama yapıp ilk oynatılabilir sonucu dene
            try:
                with YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
                    info = ydl.extract_info(query, download=False)
                search_title = info.get('title', None)
            except Exception:
                search_title = None
            if search_title:
                search = VideosSearch(search_title, limit=5)
                result = search.result()
                found = False
                for video in result['result']:
                    url = video['link']
                    title = video['title']
                    try:
                        with YoutubeDL(ydl_opts) as ydl:
                            info2 = ydl.extract_info(url, download=False)
                        song = {'url': info2['url'], 'title': title, 'ekleyen': interaction.user.mention}
                        queue = get_queue(interaction.guild.id)
                        queue.append(song)
                        if len(queue) > 0:
                            original_playlists[interaction.guild.id] = queue.copy()
                        if not voice_client.is_playing():
                            await play_next(interaction, voice_client)
                            embed = discord.Embed(title="Alternatif Şarkı Çalınıyor", description=f'Asıl link oynatılamadı, arama ile bulunan şarkı çalınıyor: **{title}**', color=discord.Color.orange())
                        else:
                            embed = discord.Embed(title="Alternatif Sıraya Eklendi", description=f'Asıl link oynatılamadı, arama ile bulunan şarkı sıraya eklendi: **{title}**', color=discord.Color.orange())
                        await interaction.followup.send(embed=embed)
                        found = True
                        break
                    except Exception:
                        continue
                if not found:
                    embed = discord.Embed(title="Şarkı Eklenemedi", description="Verilen linkten ve arama ile hiçbir oynatılabilir şarkı bulunamadı.", color=discord.Color.red())
                    await interaction.followup.send(embed=embed)
            else:
                embed = discord.Embed(title="Şarkı Eklenemedi", description="Verilen linkten ve başlıkla arama ile hiçbir oynatılabilir şarkı bulunamadı.", color=discord.Color.red())
                await interaction.followup.send(embed=embed)
        return

@bot.tree.command(name="gec", description="Sonraki şarkıya geç.")
async def gec(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        embed = discord.Embed(title="Şarkı Geçildi", color=discord.Color.orange())
        embed.set_footer(text=f"Komut: /gec | Kullanıcı: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Çalan şarkı yok", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="duraklat", description="Çalan şarkıyı duraklat.")
async def duraklat(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        embed = discord.Embed(title="Şarkı Duraklatıldı", color=discord.Color.orange())
        embed.set_footer(text=f"Komut: /duraklat | Kullanıcı: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Çalan şarkı yok", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="devamet", description="Duraklatılan şarkıyı devam ettir.")
async def devamet(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        embed = discord.Embed(title="Şarkı Devam Ediyor", color=discord.Color.green())
        embed.set_footer(text=f"Komut: /devamet | Kullanıcı: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Duraklatılmış şarkı yok", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="durdur", description="Müziği ve kuyruğu tamamen durdur.")
async def durdur(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        queue = get_queue(interaction.guild.id)
        queue.clear()
        embed = discord.Embed(title="Müzik Durduruldu ve Kuyruk Temizlendi", color=discord.Color.red())
        embed.set_footer(text=f"Komut: /durdur | Kullanıcı: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(title="Çalan şarkı yok", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="kuyruk", description="Kuyruktaki şarkıları göster.")
async def kuyruk(interaction: discord.Interaction):
    queue = get_queue(interaction.guild.id)
    guild_id = interaction.guild.id
    loop_status = is_looping(guild_id)
    np = now_playing.get(guild_id)
    if not queue and not np:
        embed = discord.Embed(title="Kuyrukta şarkı yok", color=discord.Color.red())
        await interaction.response.send_message(embed=embed)
    else:
        msg = ""
        if np:
            msg += f'🎵 Şu an çalan: **{np["title"]}** (Ekleyen: {np.get("ekleyen","?")})\n\n'
        if queue:
            msg += "Sıradaki şarkılar:\n"
            msg += '\n'.join([f'{i+1}. {s["title"]} (Ekleyen: {s.get("ekleyen","?")})' for i, s in enumerate(queue)])
        else:
            msg += "Sırada başka şarkı yok."
        loop_text = " (LOOP AKTİF)" if loop_status else ""
        embed = discord.Embed(title=f"Kuyruktaki Şarkılar{loop_text}", description=msg, color=discord.Color.blue())
        await interaction.response.send_message(embed=embed)

@bot.tree.command(name="loop", description="Çalan şarkıyı döngüye alır veya döngüyü kapatır.")
async def loop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    music_loops[guild_id] = not music_loops.get(guild_id, False)
    durum = "aktif" if music_loops[guild_id] else "kapalı"
    embed = discord.Embed(title="Döngü Durumu", description=f"Şarkı döngüsü artık **{durum}**!", color=discord.Color.purple())
    await interaction.response.send_message(embed=embed)

if __name__ == '__main__':
    TOKEN = os.getenv('TokeNheRe') or 'TOKENHERE'
    bot.run(TOKEN)
