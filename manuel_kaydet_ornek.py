"""
Manuel Kaydetme Örneği
"""
from document_processor import DocumentProcessor

# 1. Processor'ı başlat
processor = DocumentProcessor()

# 2. Belgeyi işle
print("Belge işleniyor...")
result = processor.process_document('test_belge.jpeg')

# 3. Sonuçları göster
print("\n" + "=" * 80)
print("İŞLEM SONUÇLARI")
print("=" * 80)
print(f"Ada     : {result['data']['ada']}")
print(f"Parsel  : {result['data']['parsel']}")
print(f"Mahalle : {result['data']['mahalle']}")
print(f"Tarih   : {result['data']['tarih']}")
print(f"Güven   : {result['data']['ocr_details']['easyocr_conf']*100:.1f}%")

# 4. Arşive kaydet
print("\n" + "=" * 80)
print("ARŞİVE KAYDEDİLİYOR...")
print("=" * 80)
save_result = processor.save_to_archive('test_belge.jpeg', result)

if save_result['success']:
    print(f"✅ {save_result['message']}")
    print(f"📁 Dosya: {save_result['saved_path']}")
else:
    print(f"❌ {save_result['message']}")

print("=" * 80)
