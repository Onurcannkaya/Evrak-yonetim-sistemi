"""
ROI-based OCR Test Script
Test ROI metodu ile hybrid OCR sonuçlarını karşılaştır
"""

from document_processor import DocumentProcessor
import cv2

# Processor oluştur
processor = DocumentProcessor()

# Görüntüyü yükle
image = cv2.imread('test_belge.jpeg')

print("=" * 60)
print("ROI-BASED OCR TESTİ")
print("=" * 60)

# ULTRA restorasyon uygula (en iyi sonuç)
print("\n1) ULTRA restorasyon uygulanıyor...")
restored_ultra = processor.restore_image_ultra(image)

# ROI-based OCR uygula
print("\n2) ROI-based OCR uygulanıyor...")
roi_result = processor._ocr_with_roi(restored_ultra, 'ultra')

print("\n" + "=" * 60)
print("ROI-BASED OCR SONUÇLARI")
print("=" * 60)
print(f"Orta Bölge Güven: {roi_result['confidence']:.2%}")
print(f"Ada            : {roi_result['ada']}")
print(f"Parsel         : {roi_result['parsel']}")
print(f"Mahalle        : {roi_result['mahalle']}")
print("\n" + "=" * 60)
print("ORTA BÖLGE METNİ (İLK 500 KARAKTER)")
print("=" * 60)
print(roi_result['middle_text'][:500])
print("=" * 60)
