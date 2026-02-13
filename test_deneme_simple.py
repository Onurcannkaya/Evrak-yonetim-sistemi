"""
deneme.jpg OCR Test
"""
from document_processor import DocumentProcessor

print("=" * 60)
print("DENEME.JPG OCR TESTİ")
print("=" * 60)

processor = DocumentProcessor()
result = processor.process_document('deneme.jpg')

if result['success']:
    data = result['data']
    print("\n" + "=" * 60)
    print("SONUÇLAR")
    print("=" * 60)
    print(f"Ada     : {data.get('ada')}")
    print(f"Parsel  : {data.get('parsel')}")
    print(f"Mahalle : {data.get('mahalle')}")
    print(f"Tarih   : {data.get('tarih')}")
    
    ocr_details = data.get('ocr_details', {})
    easy_conf = ocr_details.get('easyocr_conf', 0) * 100
    tess_conf = ocr_details.get('tesseract_conf', 0) * 100
    max_conf = max(easy_conf, tess_conf)
    
    print(f"Güven   : {max_conf:.1f}%")
    print(f"Motor   : {ocr_details.get('engine_used')}")
    print("\n" + "=" * 60)
    print("İLK 500 KARAKTER")
    print("=" * 60)
    print(data.get('corrected_text', '')[:500])
    print("=" * 60)
else:
    print(f"❌ Hata: {result['message']}")
