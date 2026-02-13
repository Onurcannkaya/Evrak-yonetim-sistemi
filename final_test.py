from document_processor import DocumentProcessor

processor = DocumentProcessor()
result = processor.process_document('test_belge.jpeg')

print("=" * 80)
print("FINAL TEST SONUÇLARI")
print("=" * 80)
print(f"Ada     : {result['data']['ada']}")
print(f"Parsel  : {result['data']['parsel']}")
print(f"Mahalle : {result['data']['mahalle']}")
print(f"Tarih   : {result['data']['tarih']}")
print(f"Belge No: {result['data']['belge_no']}")
print(f"\nOCR Güven: {result['data']['ocr_details']['easyocr_conf']*100:.1f}%")
print(f"Restorasyon: {result['data']['ocr_details']['restoration_level']}")
print("\nHam Metin (ilk 300 karakter):")
print(result['data']['raw_text'][:300])
print("=" * 80)
