"""
OCR Diagnostic Test - Raw Output Analysis
"""
from document_processor import DocumentProcessor
import cv2

# Initialize processor
processor = DocumentProcessor()

# Load and process image
print("=" * 80)
print("OCR DIAGNOSTIC TEST")
print("=" * 80)

image = cv2.imread('test_belge.jpeg')
print("\n1. Running OCR...")
ocr_result = processor.hybrid_ocr(image)

print("\n2. RAW OCR OUTPUT:")
print("-" * 80)
print("EasyOCR Text:")
print(ocr_result['easyocr_text'][:500])
print(f"\nEasyOCR Confidence: {ocr_result['easyocr_conf']*100:.1f}%")
print("\nTesseract Text:")
print(ocr_result['tesseract_text'][:500])
print(f"\nTesseract Confidence: {ocr_result['tesseract_conf']*100:.1f}%")

print("\n3. MERGED TEXT:")
print("-" * 80)
print(ocr_result['merged_text'][:500])

print("\n4. SEMANTIC CORRECTION:")
print("-" * 80)
corrected = processor.apply_semantic_correction(ocr_result['merged_text'])
print(corrected[:500])

print("\n5. MAHALLE DETECTION:")
print("-" * 80)
mahalle = processor.find_best_neighborhood(corrected)
print(f"Detected Mahalle: {mahalle}")

print("\n6. SPATIAL DATA:")
print("-" * 80)
spatial = processor.extract_spatial_data(corrected)
print(f"Ada: {spatial['ada']}")
print(f"Parsel: {spatial['parsel']}")
print(f"Mahalle: {spatial['mahalle']}")

print("\n" + "=" * 80)
