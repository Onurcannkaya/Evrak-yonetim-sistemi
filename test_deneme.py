"""
PDF'i görüntüye çevir ve OCR test et
"""
import fitz  # PyMuPDF
from document_processor import DocumentProcessor
import cv2
import numpy as np

# PDF'i aç
pdf_path = 'deneme.pdf'
doc = fitz.open(pdf_path)

# İlk sayfayı al
page = doc[0]

# Yüksek çözünürlükte görüntüye çevir (300 DPI)
mat = fitz.Matrix(300/72, 300/72)  # 72 DPI'dan 300 DPI'a
pix = page.get_pixmap(matrix=mat)

# NumPy array'e çevir
img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)

# RGB'den BGR'ye çevir (OpenCV için)
if pix.n == 4:  # RGBA
    img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
else:  # RGB
    img_bgr = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

# Görüntüyü kaydet
cv2.imwrite('deneme.jpeg', img_bgr)
print(f"✅ PDF converted: {pix.width}x{pix.height} pixels")

doc.close()

# OCR test et
print("\n" + "=" * 60)
print("DENEME.PDF OCR TESTİ")
print("=" * 60)

processor = DocumentProcessor()
result = processor.process_document('deneme.jpeg')

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
    print("\n" + "=" * 60)
    print("İLK 500 KARAKTER")
    print("=" * 60)
    print(data.get('corrected_text', '')[:500])
    print("=" * 60)
else:
    print(f"❌ Hata: {result['message']}")
