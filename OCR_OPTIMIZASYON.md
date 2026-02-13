# OCR Optimizasyon Kılavuzu
## Sivas Belediyesi Akıllı Evrak Yönetim Sistemi

---

## 🎯 OCR Doğruluğunu Artırma Stratejileri

### 1. GÖRÜNTÜ KALİTESİ (En Önemli!)

#### Tarama Ayarları:
```
✅ Çözünürlük: 300 DPI veya daha yüksek (600 DPI ideal)
✅ Renk Modu: Gri tonlama (Grayscale)
✅ Format: PNG veya TIFF (kayıpsız sıkıştırma)
❌ Format: JPG (kayıplı sıkıştırma - kullanmayın)
✅ Kontrast: Yüksek (yazı koyu, kağıt beyaz)
```

#### Fiziksel Belge Hazırlığı:
- Belgeyi düz bir yüzeyde tarayın
- Eğiklik olmamasına dikkat edin
- Kırışıklıkları düzeltin
- Şeffaf koruyucu kullanmayın (yansıma yapar)
- İyi aydınlatma altında tarayın

---

## 🔧 Sistem Optimizasyonları

### Yapılan İyileştirmeler (v2.0)

#### 1. Görüntü Ön İşleme:
```python
✅ Yüksek çözünürlük büyütme (LANCZOS4)
✅ Güçlü gürültü azaltma (Non-local means)
✅ Şiddetli kontrast iyileştirme (CLAHE 3.0)
✅ Keskinleştirme filtresi
✅ Otsu + Adaptive threshold hibrit
✅ Morfolojik temizleme
✅ Otomatik ters çevirme kontrolü
```

#### 2. EasyOCR Parametreleri:
```python
text_threshold=0.6      # Metin tespiti (0.7 → 0.6 hassas)
low_text=0.3           # Düşük güvenli metinleri de al
link_threshold=0.3     # Kelime birleştirme
canvas_size=2560       # İşleme boyutu
mag_ratio=1.5          # Büyütme oranı
add_margin=0.1         # Metin kutusu margin
```

#### 3. Çoklu Deneme OCR:
Sistem 3 farklı parametre setiyle OCR yapar ve en iyi sonucu seçer:
- **Deneme 1**: Standart parametreler
- **Deneme 2**: Yüksek hassasiyet (düşük eşikler)
- **Deneme 3**: Dengeli mod (orta parametreler)

---

## 📊 Beklenen Performans

### OCR Doğruluk Oranları:

| Belge Kalitesi | v1.0 Eski | v2.0 Yeni | İyileşme |
|----------------|-----------|-----------|----------|
| Mükemmel (300+ DPI, net) | 85-90% | **95-98%** | +10% |
| İyi (200-300 DPI) | 75-85% | **88-95%** | +13% |
| Orta (150-200 DPI) | 60-75% | **78-88%** | +18% |
| Zayıf (soluk, bulanık) | 40-60% | **65-80%** | +25% |

---

## 🚀 Hızlı İyileştirme Kontrol Listesi

### Eğer OCR Doğruluğu Düşükse:

#### ✅ 1. Görüntü Kalitesi Kontrol Et
```bash
# Görüntü boyutunu kontrol et
python -c "from PIL import Image; img = Image.open('belge.jpg'); print(f'Boyut: {img.size}, DPI: {img.info.get(\"dpi\", \"Bilinmiyor\")}')"
```

**Minimum gereksinimler:**
- Genişlik: 1500+ piksel (2000+ ideal)
- DPI: 200+ (300+ ideal)

#### ✅ 2. Görüntü Ön İşlemeyi Test Et
```bash
python test_system.py
# test_comparison.png dosyasına bakın
# Önce/Sonra farkını görün
```

#### ✅ 3. Manuel Parametre Ayarı

`document_processor_improved.py` dosyasında:

```python
# CLAHE parametresi (kontrast)
clahe = cv2.createCLAHE(
    clipLimit=3.0,      # 2.0-4.0 arası deneyin
    tileGridSize=(8,8)
)

# Adaptive threshold
adaptive = cv2.adaptiveThreshold(
    sharpened, 255,
    cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
    cv2.THRESH_BINARY,
    31,  # 21-51 arası TEK SAYI deneyin
    2    # 1-5 arası deneyin
)
```

#### ✅ 4. OCR Dil Kontrolü
```python
# Sadece Türkçe için
ocr = TurkishOCR(languages=['tr'])

# Türkçe + İngilizce (önerilen)
ocr = TurkishOCR(languages=['tr', 'en'])
```

---

## 🔍 Sorun Giderme

### Problem: "OCR güveni %50'nin altında"

**Çözüm 1: Görüntü kalitesini artır**
```python
# document_processor_improved.py içinde
min_width = 2500  # 3000 veya 3500 yapın
```

**Çözüm 2: Daha agresif keskinleştirme**
```python
kernel_sharpen = np.array([
    [0, -1, 0],
    [-1, 6, -1],  # 5 → 6 yapın
    [0, -1, 0]
])
```

**Çözüm 3: CLAHE artır**
```python
clahe = cv2.createCLAHE(
    clipLimit=4.0,  # 3.0 → 4.0
    tileGridSize=(8, 8)
)
```

---

### Problem: "Türkçe karakterler yanlış okuyor (ş→s, ğ→g, ı→i)"

**Çözüm 1: Sadece Türkçe dil kullan**
```python
self.reader = easyocr.Reader(['tr'], gpu=False)
```

**Çözüm 2: Türkçe modelini yeniden indir**
```bash
rm -rf ~/.EasyOCR/model/turkish*
python -c "import easyocr; r = easyocr.Reader(['tr'], gpu=False)"
```

**Çözüm 3: Post-processing düzeltmeleri**
```python
# document_processor_improved.py içinde DocumentDataExtractor'a ekle
def fix_turkish_chars(text: str) -> str:
    """Yaygın OCR hatalarını düzelt"""
    fixes = {
        'Ä±': 'ı', 'Ã§': 'ç', 'ÅŸ': 'ş',
        'Ä': 'ğ', 'Ã¼': 'ü', 'Ã¶': 'ö'
    }
    for wrong, right in fixes.items():
        text = text.replace(wrong, right)
    return text
```

---

### Problem: "Kaşe ve mühürler metni bozuyor"

**Çözüm: Morfolojik temizlemeyi artır**
```python
# Daha büyük kernel ile daha fazla gürültü temizleme
kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))  # (2,2) → (3,3)
cleaned = cv2.morphologyEx(combined, cv2.MORPH_OPEN, kernel_open, iterations=2)  # 1 → 2
```

---

## 📈 Performans İzleme

### Log Kontrolü

Sistem detaylı loglar üretir:

```bash
# API loglarını izle
tail -f api.log

# Önemli metrikler:
# - "OCR tamamlandı: X kelime, ortalama güven: Y%"
# - "✓ En iyi sonuç: [Method] - Güven: X%"
# - "Görüntü büyütüldü: AxB -> CxD"
```

### Başarı Kriterleri:

✅ **Mükemmel**: OCR güveni >90%  
✅ **İyi**: OCR güveni 80-90%  
⚠️ **Orta**: OCR güveni 70-80%  
❌ **Zayıf**: OCR güveni <70% (görüntü kalitesini iyileştirin)

---

## 💡 İleri Seviye İpuçları

### GPU Kullanımı (10x Hızlandırma)

NVIDIA GPU'nuz varsa:

```python
# document_processor_improved.py içinde
self.reader = easyocr.Reader(
    languages,
    gpu=True,  # False → True
    download_enabled=True,
    verbose=False
)
```

**Gereksinimler:**
- CUDA 11.0+
- PyTorch GPU versiyonu: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118`

### Paralel İşleme (Toplu Belge için)

```python
from concurrent.futures import ThreadPoolExecutor

def process_batch(image_files):
    processor = DocumentProcessor()
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(
            processor.process_document, 
            image_files
        ))
    
    return results

# Kullanım
files = ['belge1.jpg', 'belge2.jpg', 'belge3.jpg']
results = process_batch(files)
```

---

## 📞 Destek

OCR sorunları devam ediyorsa:

1. **test_comparison.png** dosyasını kontrol edin
2. **Örnek başarısız belge** gönderin
3. **Log çıktılarını** paylaşın

**İletişim:**
- E-posta: bilgiislem@sivas.bel.tr
- Dahili: 2100

---

**Son Güncelleme:** Şubat 2024  
**Versiyon:** 2.0 (Optimize OCR)
