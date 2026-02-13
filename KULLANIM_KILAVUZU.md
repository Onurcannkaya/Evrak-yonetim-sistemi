# Sivas Belediyesi Akıllı Evrak Yönetim Sistemi
## Kurulum ve Kullanım Kılavuzu

---

## 📋 Sistem Gereksinimleri

### Donanım
- **İşlemci**: 4 core veya üzeri (OCR işlemleri için)
- **RAM**: Minimum 8GB (16GB önerilir)
- **Disk**: 100GB+ (arşiv için + ~1GB OCR modelleri)

### Yazılım
- **İşletim Sistemi**: Ubuntu 20.04+ / Windows 10+ / macOS 11+ / CentOS 8+
- **Python**: 3.8 veya üzeri
- **Internet**: İlk kurulum için (EasyOCR modellerini indirmek üzere)

**ÖNEMLİ**: Bu sistem **TAM BAĞIMSIZDIR**. Tesseract OCR gibi harici yazılım gerektirmez!

---

## 🚀 Kurulum Adımları

### 1. Sistem Bağımlılıklarının Kurulumu

#### Ubuntu/Debian:
```bash
# Sistem paketlerini güncelle
sudo apt-get update

# Sadece görüntü işleme kütüphaneleri gerekli
sudo apt-get install -y libopencv-dev libgl1-mesa-glx libglib2.0-0

# PDF dönüştürme araçları (opsiyonel)
sudo apt-get install -y poppler-utils

# Python geliştirme araçları
sudo apt-get install -y python3-dev python3-pip
```

#### CentOS/RHEL:
```bash
sudo yum install -y opencv mesa-libGL glib2
sudo yum install -y poppler-utils
```

#### Windows:
Windows'ta hiçbir ek yazılım kurmanıza gerek yok! Python ve pip yeterli.

#### macOS:
```bash
brew install opencv
```

### 2. Python Sanal Ortam Oluşturma

```bash
# Proje dizinine gidin
cd /path/to/akilli-evrak-sistemi

# Sanal ortam oluştur
python3 -m venv venv

# Sanal ortamı aktifleştir
# Linux/Mac:
source venv/bin/activate

# Windows:
venv\Scripts\activate
```

### 3. Python Paketlerinin Kurulumu

```bash
# Gerekli paketleri yükle
pip install --upgrade pip
pip install -r requirements.txt
```

**İlk Çalıştırmada:**
EasyOCR ilk kez çalıştırıldığında Türkçe ve İngilizce dil modellerini (~100-150MB) otomatik olarak indirecektir. Bu sadece bir kez olur ve internet bağlantısı gerektirir.

```bash
# Modelleri önceden indirmek için (opsiyonel):
python -c "import easyocr; reader = easyocr.Reader(['tr', 'en'], gpu=False)"
```

Model dosyaları şu konuma kaydedilir:
- **Linux/macOS**: `~/.EasyOCR/model/`
- **Windows**: `C:\Users\KullaniciAdi\.EasyOCR\model\`

---

## 🎯 Kullanım Örnekleri

### 1. Tek Belge İşleme (Komut Satırı)

```python
from document_processor import DocumentProcessor

# İşlemciyi başlat
processor = DocumentProcessor(archive_directory="./evrak_arsiv")

# Belgeyi işle
result = processor.process_document(
    image_path="./belgeler/encumen_karar_001.jpg",
    doc_type="ENCUMEN",
    save_enhanced=True
)

# Sonuçları göster
if result['success']:
    print(f"✓ Belge başarıyla işlendi!")
    print(f"Dosya yolu: {result['file_path']}")
    print(f"Ada: {result['data']['ada']}")
    print(f"Parsel: {result['data']['parsel']}")
    print(f"Mahalle: {result['data']['mahalle']}")
else:
    print(f"✗ Hata: {result['error']}")
```

### 2. Toplu Belge İşleme

```python
from pathlib import Path
from document_processor import DocumentProcessor

processor = DocumentProcessor()

# Belgeler klasöründeki tüm görüntüleri işle
belgeler_dizini = Path("./belgeler")

for image_file in belgeler_dizini.glob("*.jpg"):
    print(f"İşleniyor: {image_file.name}")
    
    result = processor.process_document(
        image_path=str(image_file),
        doc_type="ENCUMEN"
    )
    
    if result['success']:
        print(f"  ✓ Tamamlandı: {result['data']['ada']}/{result['data']['parsel']}")
    else:
        print(f"  ✗ Hata: {result['error']}")
```

### 3. API Sunucusunu Başlatma

```bash
# Geliştirme modunda
python api_server.py

# Production modunda (Uvicorn ile)
uvicorn api_server:app --host 0.0.0.0 --port 8080 --workers 4

# Systemd ile servis olarak (Ubuntu)
sudo nano /etc/systemd/system/evrak-api.service
```

**Systemd servis dosyası örneği:**
```ini
[Unit]
Description=Sivas Belediyesi Evrak API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/akilli-evrak-sistemi
Environment="PATH=/opt/akilli-evrak-sistemi/venv/bin"
ExecStart=/opt/akilli-evrak-sistemi/venv/bin/uvicorn api_server:app --host 0.0.0.0 --port 8080
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Servisi etkinleştir ve başlat
sudo systemctl enable evrak-api
sudo systemctl start evrak-api
sudo systemctl status evrak-api
```

---

## 🌐 API Kullanımı (GIS Entegrasyonu)

### Kent Rehberi'nden Ada/Parsel Sorgulama

**Endpoint:** `GET /api/document/by-parsel`

```bash
# Örnek cURL komutu
curl -X GET "http://localhost:8080/api/document/by-parsel?ada=32&parsel=2&mahalle=Kandemir"
```

**JavaScript örneği (GIS frontend):**
```javascript
async function getParselDocument(ada, parsel, mahalle) {
    const response = await fetch(
        `http://evrak-api.sivas.bel.tr:8080/api/document/by-parsel?` +
        `ada=${ada}&parsel=${parsel}&mahalle=${mahalle}`
    );
    
    if (response.ok) {
        // PDF olarak indir
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        window.open(url);
    } else {
        const error = await response.json();
        console.error('Belge bulunamadı:', error.detail);
    }
}

// Kullanım
getParselDocument('32', '2', 'Kandemir');
```

### Yeni Belge Yükleme

**Endpoint:** `POST /api/upload`

```bash
# cURL ile
curl -X POST "http://localhost:8080/api/upload?doc_type=ENCUMEN" \
  -F "file=@belge.jpg"
```

**Python örneği:**
```python
import requests

with open('encumen_karar.jpg', 'rb') as f:
    files = {'file': f}
    response = requests.post(
        'http://localhost:8080/api/upload',
        files=files,
        params={'doc_type': 'ENCUMEN'}
    )

result = response.json()
print(f"Ada: {result['data']['ada']}")
print(f"Parsel: {result['data']['parsel']}")
```

### Belge Arama

**Endpoint:** `POST /api/search`

```python
import requests

search_params = {
    "ada": "32",
    "parsel": "2",
    "mahalle": "Kandemir"
}

response = requests.post(
    'http://localhost:8080/api/search',
    json=search_params
)

results = response.json()
print(f"Bulunan belge sayısı: {results['count']}")

for doc in results['documents']:
    print(f"  - {doc['pdf_path']}")
```

---

## 📁 Klasör Yapısı

```
evrak_arsiv/
├── KANDEMIR/
│   ├── ADA_32/
│   │   ├── 32_2_ENCUMEN_20230312.pdf
│   │   ├── 32_2_ENCUMEN_20230312.json
│   │   ├── 32_5_ENCUMEN_20230315.pdf
│   │   └── 32_5_ENCUMEN_20230315.json
│   └── ADA_45/
│       └── ...
├── GULTEPE/
│   └── ADA_10/
│       └── ...
└── ...
```

**JSON Metadata örneği:**
```json
{
  "mahalle": "KANDEMIR",
  "ada": "32",
  "parsel": "2",
  "karar_no": "2023/156",
  "tarih": "12/03/2023",
  "doc_type": "ENCUMEN",
  "ocr_confidence": 87.5,
  "processed_date": "2024-02-01T14:30:00",
  "ham_metin": "SIVAS BELEDİYESİ ENCÜMENİ..."
}
```

---

## 🔧 Yapılandırma

### Görüntü İyileştirme Parametreleri

`document_processor.py` dosyasında `ImagePreprocessor` sınıfı:

```python
# Adaptive Threshold parametreleri
blockSize=11,  # Komşuluk boyutu (tek sayı olmalı)
C=2            # Eşik değerinden çıkarılacak sabit

# CLAHE parametreleri
clipLimit=2.0,           # Kontrast limiti
tileGridSize=(8, 8)      # Grid boyutu
```

### OCR Parametreleri

```python
# EasyOCR reader yapılandırması
languages=['tr', 'en']  # Türkçe ve İngilizce
gpu=False               # CPU kullan (GPU varsa True yapılabilir)
download_enabled=True   # Model indirmeye izin ver

# Okuma parametreleri
detail=1                # 0: Sadece metin, 1: Koordinat+metin+güven skoru
paragraph=True          # Paragraf olarak grupla
```

**Dil Kodları:**
- `tr` - Türkçe
- `en` - İngilizce
- `ar` - Arapça
- `fr` - Fransızca
- `de` - Almanca
- [Tam liste için EasyOCR dokümantasyonu](https://www.jaided.ai/easyocr/)

**Not:** Her ek dil için model dosyası (~50-100MB) indirilir.

---

## 🐛 Sorun Giderme

### Problem: EasyOCR modelleri indirilemiyor

**Çözüm:**
```bash
# Manuel model indirme
mkdir -p ~/.EasyOCR/model
cd ~/.EasyOCR/model

# Türkçe model
wget https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/turkish_g2.zip
unzip turkish_g2.zip

# İngilizce model
wget https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip
unzip english_g2.zip
```

### Problem: "CUDA not available" uyarısı

**Çözüm:**
Bu uyarı normal ve sorun değildir. EasyOCR GPU bulamadığı için CPU kullanır. Kod zaten `gpu=False` olarak ayarlanmıştır.

### Problem: OCR Türkçe karakterleri yanlış okuyor

**Çözüm:**
1. Tarama çözünürlüğünü artırın (minimum 300 DPI)
2. `ImagePreprocessor` parametrelerini ayarlayın
3. Görüntü kalitesini kontrol edin
4. EasyOCR modellerini yeniden indirin:
```bash
rm -rf ~/.EasyOCR/model/turkish*
python -c "import easyocr; reader = easyocr.Reader(['tr'], gpu=False)"
```

### Problem: Görüntü kalitesi düşük, OCR başarısız

**Çözüm:**
1. Tarama çözünürlüğünü artırın (minimum 300 DPI)
2. `ImagePreprocessor` parametrelerini ayarlayın
3. `enhance_image` fonksiyonunda `blockSize` değerini artırın (13, 15, 17...)

### Problem: API'ye erişilemiyor

**Çözüm:**
```bash
# Port dinleniyor mu kontrol et
sudo netstat -tulpn | grep 8080

# Firewall kuralları (Ubuntu)
sudo ufw allow 8080/tcp

# Servis durumu
sudo systemctl status evrak-api

# Log kontrolü
sudo journalctl -u evrak-api -f
```

---

## 🔒 Güvenlik Notları

### Belediye İntranet Güvenliği

1. **CORS Ayarları**: Production'da sadece GIS sunucusu IP'sini ekleyin
```python
allow_origins=["http://gis.sivas.bel.tr", "http://10.0.0.50"]
```

2. **Rate Limiting**: Çok sayıda istekte DoS önlemi
```python
from slowapi import Limiter
limiter = Limiter(key_func=lambda: request.client.host)

@app.post("/api/upload")
@limiter.limit("10/minute")
async def upload_document(...):
    ...
```

3. **Dosya Boyutu Limiti**:
```python
from fastapi import File, UploadFile

@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(..., max_length=10_000_000)  # 10MB
):
    ...
```

4. **Güvenli Dosya İsimleri**:
```python
import secrets
import hashlib

secure_filename = hashlib.sha256(
    f"{file.filename}{secrets.token_hex(8)}".encode()
).hexdigest()
```

---

## 📊 Performans İyileştirmeleri

### 1. Paralel İşleme

```python
from concurrent.futures import ThreadPoolExecutor

def process_batch(image_files):
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = executor.map(processor.process_document, image_files)
    return list(results)
```

### 2. Önbellekleme

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_metadata(file_path):
    with open(file_path, 'r') as f:
        return json.load(f)
```

### 3. Veritabanı Entegrasyonu (İleri Seviye)

SQLite veya PostgreSQL ile metadata'yı veritabanında saklayın:

```python
import sqlite3

def create_database():
    conn = sqlite3.connect('evrak.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS belgeler (
            id INTEGER PRIMARY KEY,
            mahalle TEXT,
            ada TEXT,
            parsel TEXT,
            karar_no TEXT,
            tarih TEXT,
            pdf_path TEXT,
            processed_date TEXT
        )
    ''')
    conn.commit()
    conn.close()
```

---

## 📝 Lisans ve Destek

**Sivas Belediyesi İç Kullanım**

Teknik destek için:
- E-posta: bilgiislem@sivas.bel.tr
- Dahili: 2100

---

## 🎓 Ek Kaynaklar

- Tesseract OCR: https://github.com/tesseract-ocr/tesseract
- OpenCV Türkçe: https://opencv-python-tutroals.readthedocs.io/
- FastAPI Dokümantasyon: https://fastapi.tiangolo.com/
- Pytesseract: https://pypi.org/project/pytesseract/
