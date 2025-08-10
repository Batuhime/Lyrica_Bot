# Discord Müzik Botu

Bu proje, Discord sunucularınızda gelişmiş müzik çalabilen bir bottur. YouTube ve Spotify desteği, kuyruk, döngü, ses seviyesi ve daha fazlasını içerir.

## Kurulum

1. Gerekli kütüphaneleri yükleyin:
   ```bash
   pip install -r requirements.txt
   ```
2. `spot.env.example` dosyasını kopyalayıp adını `spot.env` yapın ve kendi Spotify API anahtarlarınızı girin.
3. Discord bot tokenınızı `bot.py` içinde uygun yere ekleyin veya .env ile yönetin.

## Kullanım

Botu başlatmak için:
```bash
python bot.py
```

## Özellikler
- Slash komutları ile kolay kullanım
- YouTube ve Spotify desteği (şarkı/playlist)
- Playlist ve döngü (loop) desteği
- Sunucuya özel ses seviyesi ayarı
- Embed (zengin) yanıtlar
- Hata yönetimi

## Dosya Yapısı
```
DcBot/
├── bot.py                # Botun ana kodu
├── requirements.txt      # Gerekli Python paketleri listesi
├── spot.env.example      # Spotify API anahtarları için örnek .env dosyası
├── README.md             # Proje açıklaması ve kullanım talimatları
└── .gitignore            # Gereksiz dosyaları hariç tutmak için
```

## Lisans
MIT
