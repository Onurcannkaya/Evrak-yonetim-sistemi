# Manuel Kaydetme Kullanım Kılavuzu

## Hızlı Başlangıç

```python
from document_processor import DocumentProcessor

# 1. Processor'ı başlat
processor = DocumentProcessor()

# 2. Belgeyi işle
result = processor.process_document('belge.jpg')

# 3. Arşive kaydet
save_result = processor.save_to_archive('belge.jpg', result)

if save_result['success']:
    print(f"✅ Kaydedildi: {save_result['saved_path']}")
```

## Klasör Yapısı

Belgeler otomatik olarak şu yapıda organize edilir:

```
./evrak_arsiv/
  └── MAHALLE_ADI/
      └── ADA_XX/
          ├── belge_20260211_161613.jpeg  (orijinal görüntü)
          └── belge_20260211_161613.json  (metadata)
```

## Kaydedilen Metadata (JSON)

```json
{
  "doc_type": "ENCUMEN",
  "ada": "153",
  "parsel": "93",
  "mahalle": "ECE",
  "tarih": "13.03.1396",
  "belge_no": "4134-135",
  "ocr_details": {
    "easyocr_conf": 0.5288,
    "tesseract_conf": 0.5222,
    "engine_used": "hybrid_merge",
    "restoration_level": "extreme"
  },
  "raw_text": "...",
  "corrected_text": "..."
}
```

## Toplu İşlem Örneği

```python
from document_processor import DocumentProcessor
from pathlib import Path

processor = DocumentProcessor()

# Tüm belgeleri işle ve kaydet
for belge in Path('.').glob('*.jpg'):
    result = processor.process_document(str(belge))
    if result['success']:
        save_result = processor.save_to_archive(str(belge), result)
        print(f"✅ {belge.name} → {save_result['message']}")
```

## Örnek Çıktı

```
Belge işleniyor...
EXTREME restorasyon kullanıldı — Yeni güven: 52.88%
✅ İşlem tamamlandı — Ada: 153, Parsel: 93, Mahalle: ECE

ARŞİVE KAYDEDİLİYOR...
📁 Kaydedildi: evrak_arsiv\ECE\ADA_153\belge_20260211_161613.jpeg
✅ Belge arşive kaydedildi: ECE/ADA_153/
```

## Dosyalar

- [`manuel_kaydet_ornek.py`](file:///C:/Users/okaya/Desktop/Evrak%20Y%C3%B6netim%20Sistemii/manuel_kaydet_ornek.py) - Tam çalışan örnek
- [`document_processor.py`](file:///C:/Users/okaya/Desktop/Evrak%20Y%C3%B6netim%20Sistemii/document_processor.py) - Ana kod
