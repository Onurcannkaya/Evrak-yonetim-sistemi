# Sivas Belediyesi Belge İşleyici - Kurulum Kılavuzu

## Gerekli Kütüphaneler

Aşağıdaki komutu PowerShell veya Command Prompt'ta çalıştırın:

```bash
pip install opencv-python-headless numpy pytesseract easyocr Pillow
```

### Kütüphane Detayları

- **opencv-python-headless**: Görüntü işleme (2x upscale, denoising, adaptive threshold)
- **numpy**: Matris işlemleri
- **pytesseract**: Tesseract OCR Python wrapper
- **easyocr**: Deep learning tabanlı OCR motoru
- **Pillow**: Görüntü formatları desteği

## Tesseract OCR Kurulumu

1. Tesseract zaten kurulu: `C:\Users\okaya\AppData\Local\Programs\Tesseract-OCR\tesseract.exe`
2. Türkçe dil paketi (tur.traineddata) tessdata klasöründe olmalı
3. Kod otomatik olarak bu yolu kullanacak şekilde yapılandırılmış

## Kullanım

```python
from document_processor import DocumentProcessor

# İşleyiciyi başlat
processor = DocumentProcessor(archive_directory="./evrak_arsiv")

# Tek belge işle
result = processor.process_document("belge.jpg")

if result["success"]:
    print(f"Ada: {result['data']['ada']}")
    print(f"Parsel: {result['data']['parsel']}")
    print(f"Mahalle: {result['data']['mahalle']}")
else:
    print(f"Hata: {result['message']}")

# Toplu işlem
files = processor.get_archive_files()
batch_result = processor.process_batch(files)
```

## Mimari Katmanlar

1. **Görüntü Restorasyonu**: 2x upscale + fastNlMeansDenoising + adaptiveThreshold
2. **Hibrit OCR**: PyTesseract + EasyOCR birleşimi
3. **Sivas Beyni**: Semantik düzeltme sözlüğü + fuzzy mahalle eşleştirme
4. **Uzamsal Çıkarım**: Ada/Parsel yakınlık algoritması
5. **Hata Yönetimi**: Garanti edilmiş `{"success": bool, "message": str, "data": dict}` formatı

## Test

```bash
python document_processor.py
```

Bu komut arşivdeki dosyaları listeleyecek ve ilk dosyayı işleyecektir.
