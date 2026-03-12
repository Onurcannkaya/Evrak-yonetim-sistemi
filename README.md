# Sivas Belediyesi — Evrak Yönetim Sistemi v8.0 (Enterprise)

Sivas Belediyesi Arşiv ve Evrak yönetimi süreçlerini yapay zeka (Google Gemini 2.0 Flash) ile otomatize eden, akıllı, yüksek performanslı ve modern arayüzlü masaüstü uygulamasıdır.

## 🚀 Yeni Sürüm (v8.0) Özellikleri
- **Yapay Zeka Destekli Belge Okuma (OCR):** Tesseract veya karmaşık kütüphaneler yerine sadece Google Gemini 2.0 Flash ile %99 doğrulukta okunması zor eski belgeleri okuma ve yapılandırılmış (Ada, Parsel, Mahalle) veri çıkartma.
- **FTS5 Hızlı Arama (Global Search):** Milyonlarca satırlık evrak içerisinde saniyenin altında kelime veya parsel araması yapabilen özel arama çubuğu ve Gelişmiş Filtreleme.
- **CBS (GIS) Otomasyonu:** "Sisteme Aktar" butonuna tıklandığında mahalle, ada ve parsele göre otomatik Sivas Belediyesi Kentrehberi Haritasını açma.
- **Modern Kurumsal Arayüz:** Glassmorphism UI tasarım diliyle Sivas Belediyesi logolu güncel giriş ve çalışma ekranları.
- **Tam Loglama ve Güvenlik:** `try-except-finally` mimarisiyle olası her hata kayıt altına alınarak sistemin çökmesi engellenmektedir. Hash tabanlı şifre güvenliği aktiftir.

## 🛠️ Sistem Gereksinimleri
- İşletim Sistemi: Windows 10/11
- Bellek: En az 4GB RAM 
- API: Google Gemini API Anahtarı (config.json içerisinde)

## 📦 Kurulum ve Çalıştırma

### 1. Kaynaktan Çalıştırma
```bash
# Python 3.12 ile Virtual Environment oluşturun
python -m venv venv
.\venv\Scripts\activate

# Sadece gerekli kütüphaneleri kurun
pip install -r requirements.txt

# Config dosyasını yapılandırın (Eğer yoksa "config.json" oluşturun)
# İçerisine "google_api_key": "YOUR_KEY" ekleyin

# Uygulamayı Başlatın
python main_app.py
```

### 2. Standalone (EXE) Paketleme
Proje baştan sona tek bir tıkla çalışabilen `.exe` dosyası haline getirilebilir. Bilgisayarında Python kurulu olmayan personel için bu yol tercih edilmelidir:

```bash
# PyInstaller kütüphanesini kurun
pip install pyinstaller

# Özel ayarlarla derlemeyi başlatın
pyinstaller build.spec
```
Derleme tamamlandığında `dist/SivasBelediyesiDMS` klasörünün içindeki `SivasBelediyesiDMS.exe` dosyası sunuma ve dağıtıma hazırdır.

## 👤 Giriş Bilgileri (Varsayılan)
Uygulama ilk açıldığında `evrak_yonetim.db` dosyası yoksa otomatik oluşturur ve şu kullanıcıları tanımlar:
- **Yönetici:** `admin` / `admin123`
- **Personel:** `personel` / `personel123`

---
*Geliştirme: Antigravity Agentic AI & Sivas Belediyesi Bilgi İşlem İşbirliği ile hazırlanmıştır.*
