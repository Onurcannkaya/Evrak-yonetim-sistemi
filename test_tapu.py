from document_processor import DocumentProcessor
import logging
import json

# Loglama
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-7s | %(message)s', datefmt='%H:%M:%S')

def test_document():
    image_path = "test_belge.jpeg"
    processor = DocumentProcessor()
    
    print(f"\n📄 Analiz ediliyor: {image_path}")
    print("-" * 60)
    
    # İşle
    result = processor.process_document(image_path, doc_type="AUTO")
    
    if not result['success']:
        print(f"❌ Hata: {result['message']}")
        return

    data = result['data']
    ocr_details = data.get('ocr_details', {})
    
    print("\n" + "=" * 60)
    print(f"ANALİZ SONUÇLARI (Tip: {data.get('doc_type')})")
    print("=" * 60)
    
    print(f"Tarih    : {data.get('tarih')}")
    print(f"Ada      : {data.get('ada')}")
    print(f"Parsel   : {data.get('parsel')}")
    print(f"Mahalle  : {data.get('mahalle')}")
    print(f"Güven    : {max(ocr_details.get('easyocr_conf', 0), ocr_details.get('tesseract_conf', 0)):.2%}")
    print(f"Motor    : {ocr_details.get('engine_used')}")
    
    print("\n" + "-" * 60)
    print("METİN İÇERİĞİ (İLK 500 KARAKTER)")
    print("-" * 60)
    print(data['corrected_text'][:500])
    print("=" * 60)

if __name__ == "__main__":
    test_document()
