# ⚡ Hızlı Sorun Giderme Kılavuzu
## Sivas Belediyesi Akıllı Evrak Yönetim Sistemi

---

## 🔴 SORUN: OCR Güveni Çok Düşük (%20-30 arası)

### ✅ ÇÖ ÇÖZÜM 1: Görüntü Kalitesini Kontrol Et

```bash
# Görüntü bilgilerini kontrol et
python -c "from PIL import Image; img = Image.open('belge.jpg'); print(f'Boyut: {img.size}'); print(f'Mod: {img.mode}')"
```

**Gereksinimler:**
- ✅ Minimum genişlik: 1500 piksel
- ✅ İdeal genişlik: 2000+ piksel
- ✅ Format: PNG, TIFF (JPG değil!)
- ✅ Mod: RGB veya L (Grayscale)

**Eğer görüntü küçükse:**
```python
from PIL import Image
img = Image.open('belge.jpg')
# 300 DPI eşdeğeri için büyüt
new_size = (int(img.width * 3), int(img.height * 3))
img_resized = img.resize(new_size, Image.LANCZOS)
img_resized.save('belge_buyuk.png', 'PNG')
```

---

### ✅ ÇÖZÜM 2: İyileştirilmiş Görüntüyü İncele

Sistem `temp_enhanced_*.png` dosyası oluşturur. Bu dosyayı açıp kontrol edin:

```
Dosya konumu: ./temp_enhanced_[dosya_adi].png
```

**Kontrol listesi:**
- ✅ Yazılar siyah, arka plan beyaz mı?
- ✅ Yazılar net ve keskin mi?
- ✅ Kaşe/mühürler metni kapatmıyor mu?
- ❌ Görüntü çok karanlık/aydınlık mı?

**İyileştirilmiş görüntü kötüyse:**
`document_processor.py` içinde parametreleri ayarlayın:

```python
# Satır ~45
clahe = cv2.createCLAHE(
    clipLimit=4.0,  # 3.0 → 4.0 (daha fazla kontrast)
    tileGridSize=(8, 8)
)

# Satır ~80
adaptive2 = cv2.adaptiveThreshold(
    sharpened, 255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,
    31,  # 21-51 arası TEK SAYI deneyin
    3    # 2 → 3 (daha agresif)
)
```

---

### ✅ ÇÖZÜM 3: OCR Parametrelerini Ayarla

`document_processor.py` dosyasında `extract_text_multi_attempt` fonksiyonunda:

```python
# Satır ~330 civarı - Deneme 2'de
result2 = self.reader.readtext(
    image, detail=1, paragraph=False,
    text_threshold=0.4,    # 0.5 → 0.4 (daha hassas)
    low_text=0.15,         # 0.2 → 0.15 (daha düşük eşik)
    canvas_size=3200,      # 2880 → 3200 (daha büyük)
    mag_ratio=2.5          # 2.0 → 2.5 (daha fazla büyütme)
)
```

---

## 🔴 SORUN: Parsel Numarası Bulunamıyor

### ✅ ÇÖZÜM: Log Çıktısına Bakın

Sistem artık okunan metni loglara yazıyor:

```
📄 Okunan metin (ilk 500 karakter):
--- METIN BAŞI ---
[okunan metin burada görünecek]
--- METIN SONU ---
```

**Manuel kontrol:**
1. Logda "81 ada" veya "4 parsel" gibi ifadeler var mı?
2. OCR yanlış okumuş mu? (örn: "parsel" → "ParseL")
3. Tamamen farklı bir format mı? (örn: "P:4")

**Regex desenlerini güncelle:**

`document_processor.py` içinde PATTERNS sözlüğüne yeni desen ekle:

```python
# Satır ~440 civarı
'parsel': [
    # ... mevcut desenler ...
    r'[Pp]:\s*(\d+)',  # P: 4 formatı için
    r'[Pp]arsel\s*sayısı\s*:?\s*(\d+)',  # Yeni format
    # Sizin belgedeki formatı buraya ekleyin
],
```

---

## 🔴 SORUN: "No such file or directory" Hatası

### ✅ ÇÖZÜM: Otomatik Düzeltildi

v3.0'da bu sorun çözüldü. `save_metadata` fonksiyonu artık klasörleri otomatik oluşturuyor:

```python
# Satır ~580'de
file_path.parent.mkdir(parents=True, exist_ok=True)
```

**Eğer hala hata alıyorsanız:**

```bash
# Manuel olarak klasör oluşturun
mkdir -p evrak_arsiv

# Yazma izni kontrolü (Linux/Mac)
ls -ld evrak_arsiv
# drwxr-xr-x olmalı

# İzin problemi varsa
chmod 755 evrak_arsiv
```

---

## 🔴 SORUN: API Yanıt Vermiyor / 500 Hatası

### ✅ ÇÖZÜM 1: Detaylı Log Kontrol

API loglarını canlı izleyin:

```bash
# Windows
python api_server.py

# Linux/Mac
python api_server.py 2>&1 | tee api.log
```

**Hatayı yakalayın:**
```
ERROR - Belge işleme hatası: [hata mesajı]
```

---

### ✅ ÇÖZÜM 2: EasyOCR Model Sorunu

**Semptom:** "Model not found" veya import hatası

```bash
# Modelleri yeniden indirin
rm -rf ~/.EasyOCR/model/
python -c "import easyocr; r = easyocr.Reader(['tr', 'en'], gpu=False)"
```

**Windows'ta:**
```cmd
rmdir /s /q %USERPROFILE%\.EasyOCR\model
python -c "import easyocr; r = easyocr.Reader(['tr', 'en'], gpu=False)"
```

---

## 🔴 SORUN: Çok Yavaş (1 dakikadan fazla)

### ✅ ÇÖZÜM 1: GPU Kullan (Varsa)

```python
# document_processor.py içinde
# Satır ~135
self.reader = easyocr.Reader(
    languages,
    gpu=True,  # False → True
    download_enabled=True,
    verbose=False
)
```

**GPU için gereksinimler:**
```bash
# CUDA yüklü mü kontrol et
nvidia-smi

# PyTorch GPU versiyonu
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

---

### ✅ ÇÖZÜM 2: Tek Deneme Modu

Çoklu deneme yerine tek deneme kullan (3x daha hızlı):

```python
# document_processor.py içinde
# Satır ~690 civarı

# Bu satırı bul:
# ocr_result = self.ocr.extract_text_multi_attempt(enhanced_image)

# Şununla değiştir:
ocr_result = self.ocr.extract_text_with_confidence(enhanced_image)
```

---

## 🔴 SORUN: Türkçe Karakterler Yanlış (ş→s, ğ→g)

### ✅ ÇÖZÜM: Sadece Türkçe Dil

```python
# document_processor.py içinde
# Satır ~135

# Bu satırı bul:
# self.reader = easyocr.Reader(['tr', 'en'], ...)

# Şununla değiştir:
self.reader = easyocr.Reader(['tr'], gpu=False, ...)
```

---

## 📊 Performans Beklentileri

| İşlem | Süre (CPU) | Süre (GPU) |
|-------|------------|------------|
| Görüntü ön işleme | 2-3 sn | 2-3 sn |
| OCR (tek deneme) | 8-12 sn | 1-2 sn |
| OCR (üç deneme) | 25-35 sn | 3-6 sn |
| Veri çıkarımı | <1 sn | <1 sn |
| **TOPLAM** | 30-40 sn | 6-10 sn |

---

## 🆘 Hala Çözülmedi mi?

### Test Scripti Çalıştırın

```bash
python test_system.py
```

Bu script:
1. ✅ Örnek belge oluşturur
2. ✅ Görüntü iyileştirme test eder
3. ✅ OCR'ı test eder
4. ✅ Regex'leri test eder

Çıktıya bakın:
```
✓ En iyi sonuç: [Method] - Güven: X%, Kelime: Y
```

**X < 80%** ise görüntü kalitesi sorunu var  
**Y < 50** ise OCR parametreleri ayarlanmalı

---

## 📞 Destek

**E-posta:** bilgiislem@sivas.bel.tr  
**Dahili:** 2100

**Gönderin:**
1. Log çıktısı (son 100 satır)
2. Örnek belge görüntüsü
3. temp_enhanced_*.png dosyası
4. Hangi alanların bulunamadığı

---

**Son Güncelleme:** 3 Şubat 2026  
**Versiyon:** 3.0 (Ultra Optimize)
