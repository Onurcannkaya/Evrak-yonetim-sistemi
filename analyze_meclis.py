"""
Meclis Kararı Analiz Scripti
PDF'i görüntüye çevir ve OCR ile yapısal analiz yap
"""
import fitz  # PyMuPDF
from document_processor import DocumentProcessor
import cv2
import numpy as np
import re

pdf_path = '1993-48 Meclis Kararı.pdf'
image_path = '1993-48_meclis_karari.jpg'

print(f"📄 Analiz ediliyor: {pdf_path}")

# 1. PDF'i Görüntüye Çevir
try:
    doc = fitz.open(pdf_path)
    page = doc[0]  # İlk sayfa
    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))  # 300 DPI
    
    # Görüntüyü kaydet
    pix.save(image_path)
    print(f"✅ Görüntü oluşturuldu: {image_path}")
    
    # NumPy array'e çevir (OpenCV için)
    img_data = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        image = cv2.cvtColor(img_data, cv2.COLOR_RGBA2BGR)
    else:
        image = cv2.cvtColor(img_data, cv2.COLOR_RGB2BGR)

except Exception as e:
    print(f"❌ PDF çevirme hatası: {e}")
    exit(1)

# 2. OCR İşlemi
processor = DocumentProcessor()
print("\n🔍 OCR çalıştırılıyor (AUTO Mode)...")
# doc_type="AUTO" varsayılan, header'dan tespit edecek
result = processor.process_document(image_path)

if not result['success']:
    print(f"❌ OCR Hatası: {result['message']}")
    exit(1)

data = result['data']
text = data['corrected_text']

print("\n" + "=" * 60)
print(f"MECLİS KARARI ANALİZ SONUÇLARI (Tip: {data.get('doc_type')})")
print("=" * 60)

print(f"Karar No : {data.get('karar_no')}")
print(f"Tarih    : {data.get('tarih')}")
print(f"Konu     : {data.get('konu')}")
print(f"Ada      : {data.get('ada')}")
print(f"Parsel   : {data.get('parsel')}")
print(f"Mahalle  : {data.get('mahalle')}")
print("\n" + "-" * 60)
print("METİN ÖZETİ (İLK 1000 KARAKTER)")
print("-" * 60)
print(text[:1000])
print("=" * 60)
