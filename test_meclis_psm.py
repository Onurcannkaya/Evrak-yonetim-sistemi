"""
Meclis Kararı PSM Testi
Sadece PSM 3 ve 6 ile test et (Layout korumak için)
"""
import pytesseract
import cv2
import re

image_path = '1993-48_meclis_karari.jpg'

pytesseract.pytesseract.tesseract_cmd = r"C:\Users\okaya\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"

print(f"📄 Analiz ediliyor (PSM 3 & 6): {image_path}")
image = cv2.imread(image_path)

psm_modes = [3, 6]

for psm in psm_modes:
    print(f"\n--- PSM {psm} TEST ---")
    try:
        custom_config = f'--oem 3 --psm {psm} -l tur'
        text = pytesseract.image_to_string(image, config=custom_config)
        
        print(f"METİN ÖZETİ (İLK 500 KARAKTER):")
        print(text[:500])
        print("-" * 60)
        
        # Karar No Ara
        karar_patterns = [r'(\d{4})[/-](\d+)', r'Karar\s*No\s*[:\.]?\s*(\d+[/-]\d+)']
        for p in karar_patterns:
            m = re.search(p, text)
            if m:
                print(f"✅ KARAR NO BULUNDU: {m.group(0)}")
                break
                
    except Exception as e:
        print(f"Hata: {e}")
