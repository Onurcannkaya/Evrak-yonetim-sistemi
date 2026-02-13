"""
Gelişmiş OCR Tanı Aracı - Ham metin gösterimi
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')

from document_processor import DocumentProcessor
import json

processor = DocumentProcessor()
result = processor.process_document('test_belge.jpeg')

print("=" * 80)
print("OCR TANI RAPORU")
print("=" * 80)

if result['success']:
    data = result['data']
    
    print("\nCIKARILAN VERILER:")
    print("-" * 80)
    print(f"Ada     : {data.get('ada')}")
    print(f"Parsel  : {data.get('parsel')}")
    print(f"Mahalle : {data.get('mahalle')}")
    
    print("\n\nOCR MOTOR DETAYLARI:")
    print("-" * 80)
    ocr_details = data.get('ocr_details', {})
    print(f"Motor           : {ocr_details.get('engine_used')}")
    print(f"EasyOCR Guven   : {ocr_details.get('easyocr_conf')}")
    print(f"Tesseract Guven : {ocr_details.get('tesseract_conf')}")
    
    print("\n\nHAM METIN (ilk 1000 karakter):")
    print("=" * 80)
    raw_text = data.get('raw_text', '')
    print(raw_text[:1000] if raw_text else "METIN YOK")
    
    print("\n\nDUZELTILMIS METIN (ilk 1000 karakter):")
    print("=" * 80)
    corrected = data.get('corrected_text', '')
    print(corrected[:1000] if corrected else "METIN YOK")
    
    # Kandemir arama
    print("\n\nKANDEMIR ARAMA:")
    print("-" * 80)
    if 'kandemir' in raw_text.lower():
        print("BULUNDU - Ham metinde 'Kandemir' var!")
    else:
        print("BULUNAMADI - Ham metinde 'Kandemir' yok")
        
    # Ada/Parsel arama
    print("\n\nADA/PARSEL ARAMA:")
    print("-" * 80)
    if 'ada' in raw_text.lower():
        print(f"'ada' kelimesi bulundu")
    if 'parsel' in raw_text.lower():
        print(f"'parsel' kelimesi bulundu")
    
else:
    print(f"\nHATA: {result.get('message')}")

print("\n" + "=" * 80)
