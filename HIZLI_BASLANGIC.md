# Hızlı Başlangıç Kılavuzu
## Sivas Belediyesi Akıllı Evrak Yönetim Sistemi

---

## ⚡ 3 Adımda Kurulum

### Adım 1: Python Paketlerini Yükle

```bash
pip install -r requirements.txt
```

**Bu kadar!** Başka hiçbir yazılım kurmanıza gerek yok.

### Adım 2: Modelleri İndir (İlk Kez)

```bash
python -c "import easyocr; reader = easyocr.Reader(['tr', 'en'], gpu=False)"
```

Bu komut Türkçe ve İngilizce OCR modellerini (~150MB) indirir. **Sadece bir kez yapılır.**

### Adım 3: Sistemi Başlat

```bash
python api_server.py
```

API `http://localhost:8080` adresinde çalışmaya başlar.

---

## 🧪 İlk Test

### Test Belgesi Oluştur ve İşle

```bash
python test_system.py
```

Bu komut:
1. ✅ Örnek bir encümen kararı oluşturur
2. ✅ Görüntü iyileştirme yapar
3. ✅ OCR ile metni okur
4. ✅ Ada, parsel, mahalle bilgilerini çıkarır
5. ✅ Dosyayı arşive kaydeder

---

## 📱 API Kullanımı

### Belge Yükle

```bash
curl -X POST "http://localhost:8080/api/upload?doc_type=ENCUMEN" \
  -F "file=@belge.jpg"
```

**Yanıt:**
```json
{
  "success": true,
  "message": "Belge başarıyla işlendi",
  "file_path": "./evrak_arsiv/KANDEMIR/ADA_32/32_2_ENCUMEN_20230312.pdf",
  "data": {
    "mahalle": "KANDEMIR",
    "ada": "32",
    "parsel": "2",
    "karar_no": "2023/156",
    "tarih": "12/03/2023",
    "ocr_confidence": 92.5
  }
}
```

### Ada/Parsel Sorgula

```bash
curl "http://localhost:8080/api/document/by-parsel?ada=32&parsel=2&mahalle=Kandemir"
```

PDF dosyasını döndürür.

---

## 🎯 Python ile Kullanım

```python
from document_processor import DocumentProcessor

# İşlemciyi başlat
processor = DocumentProcessor()

# Belgeyi işle
result = processor.process_document(
    image_path="encumen_karar.jpg",
    doc_type="ENCUMEN"
)

# Sonuçları göster
print(f"Ada: {result['data']['ada']}")
print(f"Parsel: {result['data']['parsel']}")
print(f"Mahalle: {result['data']['mahalle']}")
```

---

## 🐳 Docker ile Çalıştır

```bash
# Container'ı başlat
docker-compose up -d

# Logları izle
docker-compose logs -f

# API'yi test et
curl http://localhost:8080/api/health
```

---

## ❓ Sık Sorulan Sorular

### Tesseract OCR kurmam gerekiyor mu?
**Hayır!** Bu sistem tamamen bağımsızdır. EasyOCR kullanır.

### İlk çalıştırma neden uzun sürüyor?
İlk çalıştırmada EasyOCR dil modellerini (~150MB) indirir. Bu sadece bir kez olur.

### GPU olmadan yavaş mı çalışır?
CPU'da belge başına ~3-5 saniye sürer. GPU'da ~1 saniye. Çoğu kullanım için CPU yeterlidir.

### Hangi görüntü formatlarını destekler?
PNG, JPG, JPEG, TIFF, BMP

### Minimum Python versiyonu?
Python 3.8+

### İnternet bağlantısı gerekli mi?
Sadece ilk kurulumda modelleri indirmek için. Sonra offline çalışır.

---

## 📞 Destek

**Teknik Destek:**
- E-posta: bilgiislem@sivas.bel.tr
- Dahili: 2100

**Dokümantasyon:**
- Detaylı kılavuz: `KULLANIM_KILAVUZU.md`
- README: `README.md`

---

## ✨ Öne Çıkan Özellikler

✅ **Tam Bağımsız** - Tesseract gibi harici yazılım gerektirmez  
✅ **Yüksek Doğruluk** - EasyOCR ile %92-97 doğruluk  
✅ **Türkçe Desteği** - Tam Türkçe karakter desteği  
✅ **Kolay Kurulum** - 3 adımda çalışır  
✅ **REST API** - GIS entegrasyonu hazır  
✅ **Docker Desteği** - Konteyner olarak çalıştırma  
✅ **Modüler Kod** - Kolay özelleştirme  

---

**Başarılar!** 🎉
