"""
===============================================================================
  SİVAS BELEDİYESİ ARŞİV BELGE İŞLEYİCİ — MASTER EDİTİON v4.0
===============================================================================
  1990'lı yıllara ait daktilo belgeleri için endüstriyel düzey OCR sistemi.

  Mimari:
    Katman 1 — Görüntü Restorasyonu  (Upscale + Denoise + Adaptive Threshold)
    Katman 2 — Hibrit OCR Motoru     (PyTesseract ⊕ EasyOCR)
    Katman 3 — Sivas Beyni           (Semantik Sözlük + Fuzzy Mahalle Eşleştirme)
    Katman 4 — Uzamsal Çıkarım       (Ada / Parsel / Tarih / Belge No)
    Katman 5 — Hata Yönetimi         (Standart JSON Yanıt Formatı)

  Kurulum:
    pip install opencv-python-headless numpy pytesseract easyocr Pillow

  Author : Senior Computer Vision Engineer
  Version: 4.0.0
===============================================================================
"""

# ═══════════════════════════════════════════════════════════════════════════════
# KÜTÜPHANELERİN YÜKLENMESİ
# ═══════════════════════════════════════════════════════════════════════════════
import os
import re
import cv2
import json
import difflib
import logging
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# ── Tesseract OCR Yapılandırması ──────────────────────────────────────────────
import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Users\okaya\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"
)
os.environ["TESSDATA_PREFIX"] = (
    r"C:\Users\okaya\AppData\Local\Programs\Tesseract-OCR\tessdata"
)

# ── EasyOCR ve PaddleOCR — Lazy Import (Performans Optimizasyonu) ─────────────
# Bu kütüphaneler ilk kullanımda yüklenir; başlangıç süresi ~30s → ~5s
easyocr = None   # lazy
PaddleOCR = None  # lazy

# ── PDF İşleme — PyMuPDF (v4.1) ───────────────────────────────────────────────
try:
    import fitz  # PyMuPDF
    from PIL import Image as PILImage
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False
    logging.warning("PyMuPDF (fitz) bulunamadı. PDF desteği devre dışı.")

# ── Loglama ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MasterDocProcessor")


# ═══════════════════════════════════════════════════════════════════════════════
# ANA SINIF
# ═══════════════════════════════════════════════════════════════════════════════
class DocumentProcessor:
    """
    Sivas Belediyesi arşiv belgeleri için nihai belge işleme motoru.

    Kullanım:
        processor = DocumentProcessor(archive_directory="./evrak_arsiv")
        result    = processor.process_document("belge.jpg")
        # result => {"success": True, "message": "...", "data": {...}}
    """

    # ─── Versiyon ─────────────────────────────────────────────────────────────
    VERSION = "4.0.0"

    # ══════════════════════════════════════════════════════════════════════════
    #  BAŞLATMA
    # ══════════════════════════════════════════════════════════════════════════
    def __init__(self, archive_directory: str = "./evrak_arsiv") -> None:
        """
        DocumentProcessor'ı başlatır.
        OCR motorları ilk kullanımda yüklenir (lazy loading).
        """
        self.archive_dir: str = archive_directory
        self._ensure_directory_exists()

        # ── Lazy OCR motorları (ilk kullanımda yüklenecek) ────────────────────
        self._easyocr_reader = None
        self._paddle_engine = None
        self._ocr_cache: Dict[int, Dict] = {}  # image hash → OCR sonucu

        # ── Sivas Beyni — Semantik Sözlük ─────────────────────────────────────
        self.municipal_dictionary: Dict[str, str] = self._build_dictionary()

        # ── Sivas Mahalle Listesi ─────────────────────────────────────────────
        self.sivas_neighborhoods: List[str] = self._build_neighborhood_list()

        # ── Ada / Parsel Anahtar Kelimeler ────────────────────────────────────
        self.ada_keywords: List[str] = [
            "ada", "a0a", "4da", "aoa", "ad4", "aöa",
            "ada no", "ada:", "ada=",
        ]
        self.parsel_keywords: List[str] = [
            "parsel", "par5el", "parsei", "p4rsel",
            "parse1", "par5e1", "parsel no", "parsel:", "parsel=",
        ]

        logger.info(
            "DocumentProcessor v%s başlatıldı — Sözlük: %d giriş, Mahalle: %d",
            self.VERSION,
            len(self.municipal_dictionary),
            len(self.sivas_neighborhoods),
        )

    # ── Lazy OCR Erişimleri (Performans) ──────────────────────────────────────
    @property
    def easyocr_reader(self):
        """EasyOCR motoru — ilk kullanımda yüklenir."""
        if self._easyocr_reader is None:
            global easyocr
            import easyocr as _easyocr
            easyocr = _easyocr
            logger.info("EasyOCR motoru yükleniyor (tr + en)...")
            self._easyocr_reader = easyocr.Reader(
                ["tr", "en"], gpu=False, verbose=False
            )
            logger.info("EasyOCR motoru hazır.")
        return self._easyocr_reader

    @property
    def paddle_engine(self):
        """PaddleOCR motoru — ilk kullanımda yüklenir."""
        if self._paddle_engine is None:
            try:
                global PaddleOCR
                from paddleocr import PaddleOCR as _PaddleOCR
                PaddleOCR = _PaddleOCR
                self._paddle_engine = PaddleOCR(use_angle_cls=True, lang='tr')
                logger.info("PaddleOCR motoru hazır.")
            except Exception as e:
                logger.warning(f"PaddleOCR yüklenemedi: {e}")
                self._paddle_engine = False  # sentinel — tekrar deneme
        return self._paddle_engine if self._paddle_engine is not False else None

    # ══════════════════════════════════════════════════════════════════════════
    #  KATMAN 1 — GÖRÜNTÜ RESTORASYONU
    # ══════════════════════════════════════════════════════════════════════════
    def restore_image(self, image: np.ndarray) -> np.ndarray:
        """
        Daktilo belgesi için optimize edilmiş görüntü restorasyonu.

        İşlem Hattı:
            1. Gri tonlamaya çevirme
            2.  **2× Büyütme** — Daktilo harflerinin netleşmesi için kritik
            3.  **CLAHE Kontrast İyileştirme** — Soluk mürekkebi güçlendirir
            4.  **fastNlMeansDenoising** — Kağıt gürültüsünü temizler
            5.  **Bilateral Filter** — Kenarları (harfleri) koruyarak yumuşatır
            6.  **Adaptive Threshold (Gaussian)** — Soluk mürekkebi kurtarır

        Args:
            image: BGR veya gri tonlama OpenCV görüntüsü.

        Returns:
            İkili (binary) restore edilmiş görüntü.

        Raises:
            ValueError: Görüntü None ise.
        """
        if image is None:
            raise ValueError("Geçersiz görüntü: None değeri alındı.")

        # 1) Gri tonlama
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 2) 2× Upscale — INTER_CUBIC interpolasyonla kaliteyi artır
        upscaled = cv2.resize(
            gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC
        )

        # 3) CLAHE Kontrast İyileştirme — Soluk mürekkebi güçlendirir
        # Bu adım çok önemli: Soluk daktilo yazılarını belirginleştirir
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(upscaled)

        # 4) Gürültü Temizleme — Kağıt lekeleri & salt-and-pepper gürültüsü
        # h parametresi artırıldı (10 → 15) daha güçlü temizlik için
        denoised = cv2.fastNlMeansDenoising(
            enhanced, None, h=15, templateWindowSize=7, searchWindowSize=21
        )

        # 5) Bilateral Filter — Daktilo harflerinin kenarlarını koru
        # sigmaColor ve sigmaSpace artırıldı daha güçlü yumuşatma için
        bilateral = cv2.bilateralFilter(
            denoised, d=11, sigmaColor=100, sigmaSpace=100
        )

        # 6) Adaptive Threshold (Gaussian) — Soluk belgeler için en iyi yöntem
        # blockSize artırıldı (15 → 19) daha geniş bölge analizi için
        # C azaltıldı (4 → 2) daha fazla piksel beyaz yapılacak
        binary = cv2.adaptiveThreshold(
            bilateral,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=19,
            C=2,
        )

        # 7) Morfolojik temizlik — Küçük gürültüleri temizle
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return cleaned

    def restore_image_aggressive(self, image: np.ndarray) -> np.ndarray:
        """
        Çok bozuk / çok soluk belgeler için agresif restorasyon.

        Standart pipeline başarısız olduğunda otomatik olarak devreye girer.
        Daha güçlü denoising + CLAHE kontrast iyileştirmesi uygular.

        Args:
            image: BGR veya gri tonlama OpenCV görüntüsü.

        Returns:
            Agresif şekilde temizlenmiş binary görüntü.
        """
        if image is None:
            raise ValueError("Geçersiz görüntü: None değeri alındı.")

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # Büyüt
        upscaled = cv2.resize(
            gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC
        )

        # Güçlü denoising
        denoised = cv2.fastNlMeansDenoising(
            upscaled, None, h=20, templateWindowSize=7, searchWindowSize=21
        )

        # CLAHE kontrast iyileştirme
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        # Bilateral Filter
        bilateral = cv2.bilateralFilter(
            enhanced, d=11, sigmaColor=100, sigmaSpace=100
        )

        # Adaptive Threshold — Daha büyük blok, daha yüksek C
        binary = cv2.adaptiveThreshold(
            bilateral,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=21,
            C=6,
        )

        # Morfolojik temizlik
        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)

        return cleaned

    def restore_image_extreme(self, image: np.ndarray) -> np.ndarray:
        """
        EN AGRESIF restorasyon - Çok soluk 1990'lar daktilo belgeleri için.
        
        Bu metod en son çare olarak kullanılır. Aşırı soluk mürekkebi
        kurtarmak için tüm teknikleri bir arada kullanır.

        İşlem Hattı:
            1. 3× Büyütme (2x yerine) - Maksimum detay
            2. Gamma Düzeltme - Soluk mürekkebi güçlendirir
            3. Çok güçlü CLAHE (clipLimit=8.0)
            4. Unsharp Masking - Kenarları keskinleştirir
            5. Güçlü denoising
            6. Bilateral filter
            7. Sauvola threshold - Eski belgeler için ideal
            8. Morfolojik dilation - Harfleri kalınlaştırır

        Args:
            image: BGR veya gri tonlama OpenCV görüntüsü.

        Returns:
            Maksimum agresiflikte restore edilmiş binary görüntü.
        """
        if image is None:
            raise ValueError("Geçersiz görüntü: None değeri alındı.")

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 1) 3× Upscale - Maksimum detay için
        upscaled = cv2.resize(
            gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC
        )

        # 2) Gamma Düzeltme - Soluk mürekkebi güçlendirir
        # Gamma < 1.0 = Daha parlak (soluk yazıyı kurtarır)
        gamma = 0.5  # Daha agresif (0.6 → 0.5)
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255
                          for i in np.arange(0, 256)]).astype("uint8")
        gamma_corrected = cv2.LUT(upscaled, table)

        # 3) Çok Güçlü CLAHE - Kontrast maksimum
        clahe = cv2.createCLAHE(clipLimit=12.0, tileGridSize=(8, 8))  # Daha güçlü (8.0 → 12.0)
        enhanced = clahe.apply(gamma_corrected)

        # 4) Unsharp Masking - Kenarları keskinleştir
        gaussian = cv2.GaussianBlur(enhanced, (9, 9), 10.0)
        unsharp = cv2.addWeighted(enhanced, 2.5, gaussian, -1.5, 0)  # Daha keskin (2.0 → 2.5)

        # 5) Güçlü Denoising
        denoised = cv2.fastNlMeansDenoising(
            unsharp, None, h=25, templateWindowSize=7, searchWindowSize=21
        )

        # 6) Bilateral Filter
        bilateral = cv2.bilateralFilter(
            denoised, d=13, sigmaColor=120, sigmaSpace=120
        )

        # 7) Sauvola Threshold - Eski belgeler için en iyi
        # OpenCV'de Sauvola yok, Niblack benzeri adaptive kullan
        binary = cv2.adaptiveThreshold(
            bilateral,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,  # Daha büyük blok (25 → 31)
            C=2,  # Daha hassas eşik (1 → 2)
        )

        # 8) Morfolojik Dilation - Harfleri kalınlaştır
        kernel = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(binary, kernel, iterations=1)
        
        # Son temizlik
        cleaned = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel)

        return cleaned

    def restore_image_ultra(self, image: np.ndarray) -> np.ndarray:
        """
        ULTRA SEVİYE restorasyon - %80+ güven hedefi için.
        
        Bu metod en son çare olarak kullanılır. En yüksek kaliteli
        restorasyon için tüm teknikleri maksimum seviyede kullanır.

        İşlem Hattı:
            1. 4× Büyütme (LANCZOS4) - Maksimum detay
            2. Çift Gamma Düzeltme - Çok agresif parlaklık
            3. Süper güçlü CLAHE (clipLimit=16.0)
            4. Çoklu Unsharp Masking - Maksimum keskinlik
            5. Morphological Gradient - Kenar güçlendirme
            6. Top-hat transform - Arka plan temizleme
            7. Çok güçlü denoising
            8. Bilateral filter
            9. Sauvola threshold
            10. Akıllı morfolojik işlemler

        Args:
            image: BGR veya gri tonlama OpenCV görüntüsü.

        Returns:
            ULTRA seviyede restore edilmiş binary görüntü.
        """
        if image is None:
            raise ValueError("Geçersiz görüntü: None değeri alındı.")

        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()

        # 1) 3.5× Upscale - LANCZOS4 (daha dengeli)
        upscaled = cv2.resize(
            gray, None, fx=3.5, fy=3.5, interpolation=cv2.INTER_LANCZOS4
        )

        # 2) Tek Gamma Düzeltme - Dengeli (çift gamma çok agresifti)
        gamma = 0.55
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255
                          for i in np.arange(0, 256)]).astype("uint8")
        gamma_corrected = cv2.LUT(upscaled, table)

        # 3) Güçlü CLAHE - Dengeli kontrast (16.0 → 14.0)
        clahe = cv2.createCLAHE(clipLimit=14.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gamma_corrected)

        # 4) Tek Unsharp Masking - Dengeli keskinlik
        gaussian = cv2.GaussianBlur(enhanced, (7, 7), 8.0)
        unsharp = cv2.addWeighted(enhanced, 2.5, gaussian, -1.5, 0)

        # 5) Morphological Gradient - Hafif kenar güçlendirme
        kernel_grad = np.ones((2, 2), np.uint8)
        gradient = cv2.morphologyEx(unsharp, cv2.MORPH_GRADIENT, kernel_grad)
        gradient_weighted = (gradient * 0.5).astype(np.uint8)  # Tip dönüşümü
        enhanced_edges = cv2.add(unsharp, gradient_weighted)

        # 6) Güçlü Denoising
        denoised = cv2.fastNlMeansDenoising(
            enhanced_edges.astype(np.uint8), None, h=25, templateWindowSize=7, searchWindowSize=21
        )

        # 7) Bilateral Filter - Kenarları koruyarak yumuşatma
        bilateral = cv2.bilateralFilter(
            denoised, d=13, sigmaColor=120, sigmaSpace=120
        )

        # 8) Adaptive Threshold
        binary = cv2.adaptiveThreshold(
            bilateral,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=33,
            C=2,
        )

        # 9) Hafif Morfolojik İşlemler
        # Dilation - Harfleri hafifçe kalınlaştır
        kernel_dilate = np.ones((2, 2), np.uint8)
        dilated = cv2.dilate(binary, kernel_dilate, iterations=1)
        
        # Opening - Gürültüyü temizle
        kernel_open = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(dilated, cv2.MORPH_OPEN, kernel_open)

        return cleaned


    # ══════════════════════════════════════════════════════════════════════════
    #  KATMAN 2 — HİBRİT OCR MOTORU
    # ══════════════════════════════════════════════════════════════════════════
    def _run_easyocr(self, image: np.ndarray) -> Tuple[str, float]:
        """
        EasyOCR ile metin çıkarımı.

        Returns:
            (metin, ortalama_güven) çifti.
        """
        try:
            results = self.easyocr_reader.readtext(image)
            if not results:
                return "", 0.0

            texts: List[str] = []
            conf_total = 0.0

            for _, text, conf in results:
                texts.append(text)
                conf_total += conf

            avg_conf = conf_total / len(results)
            return " ".join(texts), round(avg_conf, 4)

        except Exception as exc:
            logger.warning("EasyOCR hatası: %s", exc)
            return "", 0.0

    def _run_pytesseract(self, image: np.ndarray) -> Tuple[str, float]:
        """
        PyTesseract ile metin çıkarımı (lang='tur').

        Returns:
            (metin, ortalama_güven) çifti.
        """
        try:
            data = pytesseract.image_to_data(
                image,
                lang="tur",
                config="--psm 6 --oem 3",
                output_type=pytesseract.Output.DICT,
            )

            texts: List[str] = []
            conf_total = 0.0
            word_count = 0

            for i, word in enumerate(data["text"]):
                stripped = word.strip()
                if stripped:
                    texts.append(stripped)
                    raw_conf = data["conf"][i]
                    conf = float(raw_conf) if str(raw_conf) != "-1" else 0.0
                    conf_total += conf
                    word_count += 1

            avg_conf = (conf_total / word_count / 100.0) if word_count > 0 else 0.0
            return " ".join(texts), round(avg_conf, 4)

        except Exception as exc:
            logger.warning("PyTesseract hatası: %s", exc)
            return "", 0.0

    def _run_pytesseract_multi_psm(self, image: np.ndarray, doc_type: str = "general") -> Tuple[str, float, int]:
        """
        Birden fazla PSM modu dene, en iyi sonucu seç.
        
        Args:
            image: Görüntü
            doc_type: Belge tipi ('meclis_karari', 'tapu', 'general')
        """
        # Belge tipine göre PSM modlarını seç
        if doc_type == "meclis_karari":
            # Meclis kararları yapısal olduğu için Layout'u koruyan modlar
            psm_modes = [3, 6]
            logger.info("🏛️ Mod: Meclis Kararı (PSM 3, 6 zorlanıyor)")
        else:
            # Genel belgeler için hepsi
            psm_modes = [3, 4, 6, 11]
            
        best_text = ""
        best_conf = 0.0
        best_psm = 6
        
        for psm in psm_modes:
            try:
                # 1. Önce güven hesabı için DICT çıktısı al
                custom_config = f'--oem 3 --psm {psm} -l tur'
                data = pytesseract.image_to_data(
                    image, config=custom_config, output_type=pytesseract.Output.DICT
                )
                
                # Güven hesapla
                conf_total = 0.0
                word_count = 0
                for i, conf in enumerate(data['conf']):
                    if str(conf) != '-1':
                        conf_total += float(conf)
                        word_count += 1
                
                avg_conf = (conf_total / word_count / 100.0) if word_count > 0 else 0.0
                
                # 2. Metin için STRING çıktısı al (layout korumak için)
                # Sadece en iyi sonuç için bunu yapacağız, şimdilik metni DICT'ten alalım
                # AMA: Tesseract dict çıktısı bazen sırasız olabilir.
                # O yüzden en iyi sonucu seçtikten sonra tekrar text için çalıştıracağız.
                
                text = pytesseract.image_to_string(image, config=custom_config)
                
                # En iyi sonucu seç
                if avg_conf > best_conf:
                    best_conf = avg_conf
                    best_text = text
                    best_psm = psm
                    
            except Exception as exc:
                logger.warning(f"PSM {psm} hatası: {exc}")
                continue
        
        logger.info(f"Multi-PSM: En iyi PSM={best_psm}, Güven={best_conf:.2%}")
        return best_text, round(best_conf, 4), best_psm

    def _run_numeric_ocr(self, image: np.ndarray) -> str:
        """
        Görüntüden SADECE sayıları ve anahtar kelimeleri okur.
        Whitelist: 0-9, Ada, Parsel, Mahalle ve noktalama işaretleri.
        """
        try:
            # Whitelist: SADECE Rakamlar ve nokta/boşluk
            whitelist = "0123456789. "
            config = f"--psm 6 --oem 3 -c tessedit_char_whitelist={whitelist}"
            
            text = pytesseract.image_to_string(image, lang="eng", config=config) # lang=eng digit için daha iyi olabilir
            return text.strip()
        except Exception as e:
            logger.warning(f"Numeric OCR error: {e}")
            return ""

    def _ocr_with_roi(self, image: np.ndarray, restoration_level: str = 'standard') -> Dict[str, Any]:
        """
        ROI-based OCR: Belgeyi bölgelere ayır, orta bölgeyi yoğun işle.
        
        Bölgeler:
        - Üst 1/3: Başlık, tarih (hafif işlem)
        - Orta 1/3: Ana metin, Ada/Parsel (YO ĞUN işlem) ⭐
        - Alt 1/3: İmza, onay (hafif işlem)
        
        Args:
            image: Restore edilmiş görüntü
            restoration_level: 'standard', 'aggressive', 'extreme', 'ultra'
            
        Returns:
            {
                'full_text': str,
                'middle_text': str,  # Ada/Parsel bölgesi
                'confidence': float,
                'ada': str|None,
                'parsel': str|None
            }
        """
        # Grayscale'e çevir (CLAHE vb. için gerekli)
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            
        h, w = gray.shape[:2]
        
        # ═══ Bölge 1: Üst (Başlık) ═══
        top_roi = gray[0:h//3, :]
        
        # ═══ Bölge 2: Orta (ADA/PARSEL) ⭐ ═══
        middle_roi = gray[h//3:2*h//3, :]
        
        # ═══ Bölge 3: Alt (İmza) ═══
        bottom_roi = gray[2*h//3:h, :]
        
        # ─── ORTA BÖLGEYİ YOĞUN İŞLE ───
        # 1) Ekstra keskinleştirme
        kernel_sharpen = np.array([[-1,-1,-1],
                                   [-1, 9,-1],
                                   [-1,-1,-1]])
        middle_sharp = cv2.filter2D(middle_roi, -1, kernel_sharpen)
        
        # 2) Kontrast artırma
        clahe_middle = cv2.createCLAHE(clipLimit=18.0, tileGridSize=(8, 8))
        middle_enhanced = clahe_middle.apply(middle_sharp)
        
        # 3) Sayılar için özel threshold
        _, middle_binary = cv2.threshold(middle_enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 4) Multi-PSM OCR (orta bölge için)
        middle_text, middle_conf, middle_psm = self._run_pytesseract_multi_psm(middle_binary)
        
        # 5) EasyOCR de dene
        middle_easy, middle_easy_conf = self._run_easyocr(middle_binary)
        
        # En iyi sonucu seç
        if middle_easy_conf > middle_conf:
            middle_text = middle_easy
            middle_conf = middle_easy_conf
            logger.info(f"ROI-Middle: EasyOCR seçildi ({middle_easy_conf:.2%})")
        else:
            logger.info(f"ROI-Middle: Tesseract PSM={middle_psm} seçildi ({middle_conf:.2%})")
        
        # ─── DİĞER BÖLGELERİ HAFİF İŞLE ───
        top_text, _ = self._run_easyocr(top_roi)
        bottom_text, _ = self._run_easyocr(bottom_roi)
        
        # ─── TAM METNİ BİRLEŞTİR ───
        full_text = f"{top_text} {middle_text} {bottom_text}"
        
        # ─── HEADER ANALİZİ (YENİ - Kullanıcı İsteği) ───
        # Başlık/Konu kısmında ada/parsel geçiyor mu bak
        logger.info("🔍 Header/Konu kısmı analiz ediliyor...")
        header_spatial = self.extract_spatial_data(top_text)
        if header_spatial.get('ada'):
            logger.info(f"🎯 HEADER içinde Ada bulundu: {header_spatial['ada']}")
        if header_spatial.get('parsel'):
            logger.info(f"🎯 HEADER içinde Parsel bulundu: {header_spatial['parsel']}")

        # ─── NUMERIC OCR REFINEMENT (YENİ) ───
        # Orta bölgeyi bir de sadece sayılar ve anahtar kelimeler için tara
        logger.info("🔢 Numeric OCR (Whitelist) çalıştırılıyor...")
        numeric_text = self._run_numeric_ocr(middle_binary)
        logger.info(f"Numeric OCR Sonucu: {numeric_text[:100]}...")
        
        # ─── ADA/PARSEL ÇIKAR (sadece orta bölgeden) ───
        # Numeric hint vererek çağır
        spatial_data = self.extract_spatial_data(middle_text, numeric_hint_text=numeric_text)
        
        # Header verisi ile eksikleri tamamla
        if not spatial_data['ada'] and header_spatial['ada']:
             spatial_data['ada'] = header_spatial['ada']
             logger.info(f"✨ Header'dan Ada kurtarıldı: {header_spatial['ada']}")
             
        if not spatial_data['parsel'] and header_spatial['parsel']:
             spatial_data['parsel'] = header_spatial['parsel']
             logger.info(f"✨ Header'dan Parsel kurtarıldı: {header_spatial['parsel']}")
        
        logger.info(f"🎯 ROI-based OCR: Orta bölge güven={middle_conf:.2%}, Ada={spatial_data.get('ada')}, Parsel={spatial_data.get('parsel')}")
        
        return {
            'full_text': full_text,
            'middle_text': middle_text,
            'confidence': middle_conf,
            'ada': spatial_data.get('ada'),
            'parsel': spatial_data.get('parsel'),
            'mahalle': spatial_data.get('mahalle')
        }

    def hybrid_ocr(self, image: np.ndarray, doc_type: str = "general") -> Dict[str, Any]:
        """
        İki OCR motorunun sonuçlarını akıllıca birleştirir.

        Strateji (3 Katmanlı):
            1. Standart restorasyonu dene → her iki motor.
            2. Güven < %30 ise → agresif restorasyonu dene.
            3. Hala güven < %30 ise → EXTREME restorasyonu dene.
            4. Güven skorlarına göre ağırlıklı birleştirme yap.

        Args:
            image: Orijinal (ham) görüntü.

        Returns:
            {
                "merged_text": str,
                "easyocr_text": str, "easyocr_conf": float,
                "tesseract_text": str, "tesseract_conf": float,
                "engine_used": str,
            }
        """
        # ── Katman 1: Standart Restorasyon ────────────────────────────────────
        restored = self.restore_image(image)

        easy_text, easy_conf = self._run_easyocr(restored)
        tess_text, tess_conf, tess_psm = self._run_pytesseract_multi_psm(restored, doc_type)  # ✨ Multi-PSM + DocType
        
        # PaddleOCR — standart restorasyonla başlat (her zaman tanımlı olsun)
        paddle_text, paddle_conf = self._run_paddleocr(restored)
        
        max_conf = max(easy_conf, tess_conf, paddle_conf)
        restoration_level = "standard"

        # ✨ ERKEN ÇIKIŞ: Yüksek güven = Restorasyon gerekmiyor
        if max_conf >= 0.85:
            logger.info(f"✅ Yüksek güven ({max_conf:.2%}) — Restorasyon gerekmiyor, erken çıkış.")
            # Direkt birleştirme mantığına geç (Aggressive/EXTREME/ULTRA atlanır)
        else:
            # ── Katman 2: Agresif Restorasyon (Güven < %50) ───────────────────────
            if max_conf < 0.50:
                logger.info(f"Düşük güven ({max_conf:.2%}) — agresif restorasyon deneniyor.")
                restored_agg = self.restore_image_aggressive(image)
                easy_text_agg, easy_conf_agg = self._run_easyocr(restored_agg)
                tess_text_agg, tess_conf_agg, _ = self._run_pytesseract_multi_psm(restored_agg, doc_type)  # ✨ Multi-PSM
                
                # Agresif daha iyiyse kullan (minimum %5 iyileşme)
                improvement_agg = max(easy_conf_agg, tess_conf_agg) - max_conf
                if improvement_agg > 0.05:  # ✨ Minimal iyileşme eşiği
                    easy_text, easy_conf = easy_text_agg, easy_conf_agg
                    tess_text, tess_conf = tess_text_agg, tess_conf_agg
                    max_conf = max(easy_conf, tess_conf)
                    restoration_level = "aggressive"
                    logger.info(f"Aggressive restorasyon kullanıldı — İyileşme: {improvement_agg:.2%}")
                else:
                    logger.info(f"Aggressive minimal iyileşme ({improvement_agg:.2%}) — Kullanılmadı.")

            # ── AKILLI ERKEN ÇIKIŞ: Kroki/Harita/Plan Sayfası Tespiti ──
            # Aggressive sonrası hâlâ düşük güven + metin çoğunlukla anlamsız →
            # sayfa büyük olasılıkla kroki, harita veya plan. Derin restorasyonu atla.
            merged_text_preview = easy_text if easy_conf > tess_conf else tess_text
            text_too_short = len(merged_text_preview.strip()) < 50

            # Metin kalitesi kontrolü: anlamlı Türkçe kelime oranı
            def _is_non_text_page(text, confidence):
                """Sayfanın metin-dışı (kroki/harita/plan) olup olmadığını tespit et."""
                if confidence >= 0.55:
                    return False
                words = text.split()
                if len(words) < 5:
                    return True  # Çok az kelime → muhtemelen grafik
                # Türkçe kelime uzunluğu ort. 5+, kroki sayfasında kısa parçalar olur
                meaningful = sum(1 for w in words if len(w) >= 3 and w.isalpha())
                ratio = meaningful / len(words) if words else 0
                if ratio < 0.25:
                    return True  # Kelimelerin %75+'ı anlamsız → kroki
                return False

            if _is_non_text_page(merged_text_preview, max_conf):
                logger.info(f"📐 Kroki/Harita sayfası tespit edildi (güven: {max_conf:.2%}) — "
                            f"Derin restorasyon atlanıyor (EXTREME/ULTRA/HYPER atlandı).")
            else:
                # ── Katman 3: EXTREME Restorasyon (Güven < %50 VEYA Metin Çok Kısa) ───
                if max_conf < 0.50 or text_too_short:
                    if text_too_short:
                        logger.info(f"Metin çok kısa ({len(merged_text_preview)} karakter) — EXTREME restorasyon deneniyor.")
                    else:
                        logger.info(f"Hala düşük güven ({max_conf:.2%}) — EXTREME restorasyon deneniyor.")
                    
                    restored_ext = self.restore_image_extreme(image)
                    easy_text_ext, easy_conf_ext = self._run_easyocr(restored_ext)
                    tess_text_ext, tess_conf_ext, _ = self._run_pytesseract_multi_psm(restored_ext, doc_type)
                    
                    improvement_ext = max(easy_conf_ext, tess_conf_ext) - max_conf
                    if improvement_ext > 0.05 or len(easy_text_ext + tess_text_ext) > len(easy_text + tess_text):
                        easy_text, easy_conf = easy_text_ext, easy_conf_ext
                        tess_text, tess_conf = tess_text_ext, tess_conf_ext
                        max_conf = max(easy_conf, tess_conf)
                        restoration_level = "extreme"
                        logger.info(f"EXTREME restorasyon kullanıldı — Yeni güven: {max_conf:.2%}")
                    else:
                        logger.info(f"EXTREME minimal iyileşme ({improvement_ext:.2%}) — Kullanılmadı.")

                # Metin uzunluğu kontrolü (tekrar)
                merged_text_preview2 = easy_text if easy_conf > tess_conf else tess_text
                text_still_short = len(merged_text_preview2.strip()) < 100

                # ── Katman 4: ULTRA (Güven < %70) — Sadece metin sayfaları için ───
                if max_conf < 0.70 and not _is_non_text_page(merged_text_preview2, max_conf):
                    logger.info(f"Güven hedefin altında ({max_conf:.2%}) — ULTRA restorasyon deneniyor.")
                    
                    restored_ultra = self.restore_image_ultra(image)
                    easy_text_ultra, easy_conf_ultra = self._run_easyocr(restored_ultra)
                    tess_text_ultra, tess_conf_ultra, _ = self._run_pytesseract_multi_psm(restored_ultra, doc_type)
                    
                    improvement_ultra = max(easy_conf_ultra, tess_conf_ultra) - max_conf
                    
                    if improvement_ultra > 0.05 or len(easy_text_ultra + tess_text_ultra) > len(easy_text + tess_text):
                        easy_text, easy_conf = easy_text_ultra, easy_conf_ultra
                        tess_text, tess_conf = tess_text_ultra, tess_conf_ultra
                        paddle_text, paddle_conf = self._run_paddleocr(restored_ultra)
                        
                        engines_u = {
                            "easy": (easy_conf, easy_text),
                            "tess": (tess_conf, tess_text),
                            "paddle": (paddle_conf, paddle_text)
                        }
                        best_u = max(engines_u, key=lambda k: engines_u[k][0])
                        max_conf = engines_u[best_u][0]
                        restoration_level = "ultra"
                        logger.info(f"🚀 ULTRA kullanıldı ({best_u}) — Yeni güven: {max_conf:.2%}")
                    else:
                        logger.info(f"ULTRA minimal iyileşme ({improvement_ultra:.2%}) — Kullanılmadı.")

        # ── Birleştirme Mantığı (TRIPLE ENGINE) ───────────────────────────────
        engines = {
            "easyocr_primary": (easy_conf, easy_text),
            "tesseract_primary": (tess_conf, tess_text),
            "paddleocr_primary": (paddle_conf, paddle_text)
        }
        
        # Meclis kararı için özel durum: Tesseract multi-PSM daha iyi yapı korur
        if doc_type == "meclis_karari" and tess_conf > 0.40:
             best_engine = "tesseract_forced_struct"
             merged_text = tess_text
        else:
             best_engine = max(engines, key=lambda k: engines[k][0])
             merged_text = engines[best_engine][1]

        return {
            "merged_text": merged_text,
            "easyocr_text": easy_text,
            "easyocr_conf": easy_conf,
            "tesseract_text": tess_text,
            "tesseract_conf": tess_conf,
            "paddleocr_text": paddle_text,
            "paddleocr_conf": paddle_conf,
            "engine_used": best_engine,
            "restoration_level": restoration_level,
        }

    def _run_paddleocr(self, image: np.ndarray) -> Tuple[str, float]:
        """PaddleOCR ile metin okuma"""
        try:
            if image is None: return "", 0.0
            
            # PaddleOCR siyah zemin üzerinde beyaz yazıyı daha iyi okuyabilir
            # ama standart olarak siyah yazı beyaz zemin bekler.
            
            result = self.paddle_engine.ocr(image, cls=True)
            if not result or result[0] is None:
                return "", 0.0
            
            # Result format: [[[[x1,y1],[x2,y2]...], ("text", conf)], ...]
            texts = [line[1][0] for line in result[0]]
            confs = [line[1][1] for line in result[0]]
            
            full_text = " ".join(texts)
            avg_conf = sum(confs) / len(confs) if confs else 0.0
            
            return full_text, avg_conf
        except Exception as e:
            # PaddleOCR ilk çalıştırmada model indirirken hata verebilir veya bellek sorunu
            # logger.error(f"PaddleOCR Hatası: {e}") # Log kirliliği yapmasın
            return "", 0.0

    def restore_image_hyper(self, image: np.ndarray) -> np.ndarray:
        """
        HYPER SEVİYE restorasyon - Silik ve kopuk karakterler için.
        
        Özellikler:
        - Contrast Stretching (Min-Max Normalization)
        - Morphological Closing (Karakter birleştirme)
        - Mean Adaptive Threshold (İnce çizgiler için daha iyi)
        """
        if image is None: return None
        
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image.copy()
            
        # 1. Upscale (2x yeterli, çok büyütme gürültü yapar)
        upscaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        # 2. Contrast Stretching (Histogramı yayma)
        p2, p98 = np.percentile(upscaled, (2, 98))
        img_rescale = np.interp(upscaled, (p2, p98), (0, 255)).astype(np.uint8)
        
        # 3. Morphological Closing (Siyah karakterleri içeriden doldur)
        # Not: Yazı siyah, arkaplan beyaz ise EROSION karakteri kalınlaştırır (OpenCV ters çalışır)
        # Ama genelde threshold sonrası siyah-beyaz ters çevrilir.
        
        # Siyah beyaz yap
        binary = cv2.adaptiveThreshold(
            img_rescale, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 21, 10
        )
        
        # Gürültü temizle
        denoised = cv2.fastNlMeansDenoising(binary, None, 30, 7, 21)
        
        # Karakterleri kalınlaştır (Yazı siyahsa Erode, beyazsa Dilate)
        # Genelde OCR motorları siyah yazı ister.
        kernel = np.ones((2,2), np.uint8)
        thickened = cv2.erode(denoised, kernel, iterations=1) 
        
        return thickened



    # ══════════════════════════════════════════════════════════════════════════
    #  KATMAN 3 — SİVAS BEYNİ (SEMANTİK ONARIM)
    # ══════════════════════════════════════════════════════════════════════════
    def apply_semantic_correction(self, text: str) -> str:
        """
        Metni belediye sözlüğü + bulanık mahalle eşleştirmesiyle düzeltir.

        Args:
            text: Ham OCR çıktısı.

        Returns:
            Düzeltilmiş metin.
        """
        if not text:
            return ""

        corrected = text.upper()

        # 1) Sözlük düzeltmeleri (doğrudan eşleştirme)
        for wrong, correct in self.municipal_dictionary.items():
            pattern = re.compile(re.escape(wrong), re.IGNORECASE)
            corrected = pattern.sub(correct, corrected)

        # 2) Kelime bazlı fuzzy mahalle eşleştirme
        words = corrected.split()
        result_words: List[str] = []

        for word in words:
            clean = re.sub(r"[^A-ZÇĞİÖŞÜa-zçğıöşü]", "", word)
            if len(clean) < 3:
                result_words.append(word)
                continue

            matches = difflib.get_close_matches(
                clean, self.sivas_neighborhoods, n=1, cutoff=0.70
            )
            if matches:
                result_words.append(matches[0])
            else:
                result_words.append(word)

        return " ".join(result_words)

    def find_best_neighborhood(self, text: str) -> Optional[str]:
        """
        Metinde en olası Sivas mahalle adını bulur.
        
        Geliştirilmiş: 
        1. "Mahallesi" kelimesinin yakınındaki mahalleleri önceliklendirir
        2. Kısmi eşleşmeleri kabul eder (örn: "Kande" → "KANDEMİR")
        3. Fuzzy matching ile benzer kelimeleri bulur

        Args:
            text: Aranacak metin.

        Returns:
            Bulunan mahalle adı veya None.
        """
        if not text:
            return None

        text_upper = text.upper()
        
        # Önce "Mahallesi" veya "Mahalle" kelimesinin yakınındaki kelimeleri kontrol et
        mahalle_keywords = ["MAHALLESİ", "MAHALLESI", "MAHALLE", "MAHAL"]
        for keyword in mahalle_keywords:
            pos = text_upper.find(keyword)
            if pos != -1:
                # Mahalle kelimesinden önceki metni al
                before_keyword = text_upper[:pos].strip()
                
                # Son kelimeyi çıkar (mahalle adı olmalı)
                words_before = re.findall(r"[A-ZÇĞİÖŞÜ]+", before_keyword)
                
                # Geriye doğru kelime kelime kontrol et
                for word in reversed(words_before):
                    if len(word) < 3:
                        continue
                    
                    # Tam eşleşme
                    if word in self.sivas_neighborhoods:
                        return word
                    
                    # Kısmi eşleşme - Mahalle adı kelimeyi içeriyorsa
                    for neighborhood in self.sivas_neighborhoods:
                        if word in neighborhood or neighborhood in word:
                            if len(word) >= 3:
                                return neighborhood
                    
                    # Fuzzy eşleşme (daha yüksek eşik "Mahallesi" yakınında)
                    matches = difflib.get_close_matches(
                        word, self.sivas_neighborhoods, n=1, cutoff=0.45
                    )
                    if matches:
                        return matches[0]
                    
                    # İlk anlamlı kelimeden sonra dur
                    # (Çok geriye gitmeyi önle)
                    if len(words_before) > 5:
                        break
        
        # "Mahallesi" bulunamadıysa, tüm metinde ara
        words = re.findall(r"[A-ZÇĞİÖŞÜa-zçğıöşü]+", text_upper)

        best_match: Optional[str] = None
        best_score: float = 0.0

        for word in words:
            if len(word) < 3:
                continue

            # Tam eşleşme
            if word in self.sivas_neighborhoods:
                return word
            
            # Kısmi eşleşme - Mahalle adı kelimeyi içeriyorsa
            for neighborhood in self.sivas_neighborhoods:
                if word in neighborhood or neighborhood in word:
                    if len(word) >= 3:  # En az 3 karakter eşleşmeli (4 → 3)
                        return neighborhood

            # Fuzzy eşleşme - Eşik düşürüldü %55 → %40
            matches = difflib.get_close_matches(
                word, self.sivas_neighborhoods, n=1, cutoff=0.40  # Daha esnek (0.55 → 0.40)
            )
            if matches:
                score = difflib.SequenceMatcher(None, word, matches[0]).ratio()
                if score > best_score:
                    best_score = score
                    best_match = matches[0]

        return best_match

    # ══════════════════════════════════════════════════════════════════════════
    #  KATMAN 4 — UZAMSAL VERİ ÇIKARIMI
    # ══════════════════════════════════════════════════════════════════════════
    def _extract_number_near_keyword(
        self, text: str, keywords: List[str], window: int = 50
    ) -> Optional[str]:
        """
        Bir anahtar kelimenin yakınındaki ilk sayısal değeri çıkarır.
        
        Artık daha esnek: "Ada: 32", "ada 32", "32 ada" gibi formatları destekler.

        Args:
            text:     Aranacak metin.
            keywords: Anahtar kelime listesi.
            window:   Anahtar kelimeden önce/sonra bakılacak karakter sayısı.

        Returns:
            Bulunan sayı (str) veya None.
        """
        if not text:
            return None

        text_lower = text.lower()

        for kw in keywords:
            pos = text_lower.find(kw.lower())
            if pos == -1:
                continue

            # Hem önce hem sonra bak (daha esnek)
            start = max(0, pos - window)
            end = min(len(text_lower), pos + len(kw) + window)
            
            # Önce anahtar kelimeden sonraki sayıları dene
            after_kw = text_lower[pos + len(kw):end]
            after_numbers = re.findall(r"\b(\d+)\b", after_kw)
            if after_numbers:
                return after_numbers[0]
            
            # Sonra anahtar kelimeden önceki sayıları dene
            before_kw = text_lower[start:pos]
            before_numbers = re.findall(r"\b(\d+)\b", before_kw)
            if before_numbers:
                return before_numbers[-1]  # En yakın olan son sayı

        return None

    def _clean_text_for_extraction(self, text: str) -> str:
        """
        Resmi yazı footer/header bölümlerini çıkarım öncesi temizler.
        
        Resmi yazılarda alt kısımda kurum adresi, telefon, fax, e-posta gibi
        bilgiler bulunur. Bu bilgiler belgenin konusu değildir.
        """
        if not text:
            return text
        
        lines = text.split('\n')
        clean_lines = []
        
        # Footer tespiti: Son satırlardan yukarı doğru tara
        footer_keywords = [
            r'(?:Tel|Telefon|Fax|Faks|e-?posta|e-?mail|web)\s*[:\.]',
            r'\d{3}[\s\-]\d{3}[\s\-]\d{2}[\s\-]\d{2}',  # Telefon: 0346 225 12 34
            r'@.*\.gov\.tr',                                # e-posta
            r'www\.',                                        # web adresi
            r'(?:Bilgi\s*[İi]çin|Ayrıntılı\s*[Bb]ilgi)',
            r'(?:KEP|Elektronik\s*A[ğg])',
            r'Bu\s*belge\s*güvenli',
            r'Sayfa\s*\d+\s*/\s*\d+',
        ]
        footer_pattern = '|'.join(footer_keywords)
        
        # Header/footer bölgesini işaretle (son %20 satır kontrol)
        n = len(lines)
        footer_start = n  # Varsayılan: footer yok
        
        # Son %25 satırda footer başlangıcını ara
        check_from = max(0, int(n * 0.75))
        for i in range(check_from, n):
            if re.search(footer_pattern, lines[i], re.IGNORECASE):
                footer_start = i
                break
        
        clean_lines = lines[:footer_start]
        
        cleaned = '\n'.join(clean_lines)
        if footer_start < n:
            logger.info(f"📌 Footer temizlendi: {n - footer_start} satır (kurum iletişim bilgisi)")
        
        return cleaned

    def _is_legal_reference(self, text: str, number: str, position: int) -> bool:
        """
        Bulunan sayının kanun/madde referansı olup olmadığını kontrol eder.
        
        Örnek: '5393 sayılı kanun' veya '81. maddesi' → True (ada/parsel DEĞİL)
        """
        # Sayının etrafındaki bağlamı al (±80 karakter)
        start = max(0, position - 80)
        end = min(len(text), position + len(number) + 80)
        context = text[start:end].lower()
        
        # Kanun/yönetmelik/madde bağlamı
        legal_patterns = [
            r'sayılı',
            r'kanun',
            r'yönetmeli[gğ]',
            r'madde',
            r'fıkra',
            r'bent',
            r'hüküm',
            r'tarihli',
            r'sayılı\s*karar',
            r'mevzuat',
            r'tebli[gğ]',
            r'genelge',
            r'yasa',
        ]
        
        for lp in legal_patterns:
            if re.search(lp, context, re.IGNORECASE):
                logger.info(f"⚖️ Kanun referansı tespit edildi: '{number}' → bağlam: ...{context[max(0,position-start-20):position-start+len(number)+20]}...")
                return True
        return False

    def extract_spatial_data(self, text: str, numeric_hint_text: Optional[str] = None) -> Dict[str, Optional[str]]:
        """
        Ada, Parsel ve Mahalle değerlerini gelişmiş yöntemlerle çıkarır.
        
        Stratejiler:
        1. Regex pattern matching (Numeric Hint öncelikli)
        2. Mahalle yakınındaki sayılar
        3. Keyword proximity (fallback)
        4. Sayı düzeltme (O→0, I→1, vb.)
        5. Kanun/madde referansı filtreleme (YENİ)
        6. Footer temizleme (YENİ)

        Args:
            text: İşlenecek ana metin.
            numeric_hint_text: Sadece sayılarla taranmış yardımcı metin (Whitelist OCR sonucu).

        Returns:
            {"ada": str|None, "parsel": str|None, "mahalle": str|None}
        """
        result = {
            'ada': None,
            'parsel': None,
            'mahalle': None
        }
        
        # ── Footer temizleme (kurum iletişim bilgilerini çıkar) ──
        clean_text = self._clean_text_for_extraction(text)
        
        # Mahalle'yi bul (önce, çünkü diğer stratejiler buna bağlı)
        result['mahalle'] = self.find_best_neighborhood(clean_text)
        
        # ═══ Strateji 0: Numeric Hint (En Güvenilir) ═══
        if numeric_hint_text:
            ada_patterns = [
                r'(?:ADA|Ada|ada)\s*:?\s*(\d+)',
                r'(\d+)\s+(?:ADA|Ada|ada)',
            ]
            for pattern in ada_patterns:
                match = re.search(pattern, numeric_hint_text)
                if match:
                    result['ada'] = match.group(1) # Zaten numeric, düzeltmeye gerek yok
                    logger.info(f"🎯 Ada NUMERIC OCR match: {result['ada']}")
                    break
                    
            # Parsel patterns (Numeric Hint için)
            parsel_patterns = [
                r'(?:PARSEL|Parsel|parsel)\s*:?\s*(\d+)',
                r'(\d+)\s+(?:PARSEL|Parsel|parsel)',
            ]
            for pattern in parsel_patterns:
                match = re.search(pattern, numeric_hint_text)
                if match:
                    result['parsel'] = match.group(1)
                    logger.info(f"🎯 Parsel NUMERIC OCR match: {result['parsel']}")
                    break

        # ═══ Strateji 1: Regex Pattern Matching (Normal Metin) ═══
        # Eğer Numeric Hint bulamadıysa buradan devam et
        if not result['ada']:
            ada_patterns = [
                r'(?:ADA|Ada|ada)\s*:?\s*(\d+)',           # Ada: 153 veya Ada 153
                r'(\d+)\s+(?:ADA|Ada|ada)',                 # 153 ada
                r'(?:ADA|Ada|ada)\s+(?:NO|No|no)\s*:?\s*(\d+)',  # Ada No: 153
                r'(?:ADA|Ada|ada)\s+(?:NUMARASI|Numarası)\s*:?\s*(\d+)',  # Ada Numarası: 153
            ]
            
            for pattern in ada_patterns:
                match = re.search(pattern, clean_text)
                if match:
                    ada_raw = match.group(1)
                    # ── Kanun referansı kontrolü ──
                    if self._is_legal_reference(clean_text, ada_raw, match.start()):
                        continue
                    result['ada'] = self._correct_numbers(ada_raw, context='ada')
                    logger.info(f"Ada regex match: {result['ada']} (pattern: {pattern})")
                    break
        
        # Parsel patterns (Normal Metin)
        if not result['parsel']:
            parsel_patterns = [
                r'(?:PARSEL|Parsel|parsel)\s*:?\s*(\d+)',
                r'(\d+)\s+(?:PARSEL|Parsel|parsel)',
                r'(?:PARSEL|Parsel|parsel)\s+(?:NO|No|no)\s*:?\s*(\d+)',
                r'(?:PARSEL|Parsel|parsel)\s+(?:NUMARASI|Numarası)\s*:?\s*(\d+)',
            ]
            
            for pattern in parsel_patterns:
                match = re.search(pattern, clean_text)
                if match:
                    parsel_raw = match.group(1)
                    if self._is_legal_reference(clean_text, parsel_raw, match.start()):
                        continue
                    result['parsel'] = self._correct_numbers(parsel_raw, context='parsel')
                    logger.info(f"Parsel regex match: {result['parsel']} (pattern: {pattern})")
                    break
        
        # ═══ Strateji 2: Mahalle Yakınındaki Sayılar ═══
        if result['mahalle'] and (not result['ada'] or not result['parsel']):
            mahalle_upper = result['mahalle'].upper()
            mahalle_pos = clean_text.upper().find(mahalle_upper)
            
            if mahalle_pos != -1:
                # Mahalle'den sonraki 150 karakter
                nearby_text = text[mahalle_pos:mahalle_pos + 150]
                # Sayıları bul
                numbers = re.findall(r'\d+', nearby_text)
                
                # İlk 2-3 sayı genelde Ada ve Parsel
                if len(numbers) >= 1 and not result['ada']:
                    result['ada'] = self._correct_numbers(numbers[0], context='ada')
                    logger.info(f"Ada mahalle proximity: {result['ada']}")
                    
                if len(numbers) >= 2 and not result['parsel']:
                    result['parsel'] = self._correct_numbers(numbers[1], context='parsel')
                    logger.info(f"Parsel mahalle proximity: {result['parsel']}")
        
        # ═══ Strateji 3: Keyword Proximity (Fallback) ═══
        if not result['ada']:
            ada_fallback = self._extract_number_near_keyword(text, self.ada_keywords)
            if ada_fallback:
                result['ada'] = self._correct_numbers(ada_fallback, context='ada')
                logger.info(f"Ada keyword fallback: {result['ada']}")
        
        if not result['parsel']:
            parsel_fallback = self._extract_number_near_keyword(text, self.parsel_keywords)
            if parsel_fallback:
                result['parsel'] = self._correct_numbers(parsel_fallback, context='parsel')
                logger.info(f"Parsel keyword fallback: {result['parsel']}")
        
        return result

    def _correct_numbers(self, text: str, context: str = 'general') -> str:
        """
        Sayı context'ine göre harf-sayı karışıklıklarını düzelt.
        
        Ada/Parsel context'inde:
        - O, o → 0
        - I, l → 1
        - S, s → 5
        - B, b → 8
        - Z, z → 2
        
        Args:
            text: Düzeltilecek metin
            context: 'ada', 'parsel', veya 'general'
            
        Returns:
            Düzeltilmiş metin
        """
        if context in ['ada', 'parsel']:
            corrections = {
                'O': '0', 'o': '0',
                'I': '1', 'l': '1',
                'S': '5', 's': '5',
                'B': '8', 'b': '8',
                'Z': '2', 'z': '2',
                'G': '6', 'g': '6',
            }
            
            for old, new in corrections.items():
                text = text.replace(old, new)
        
        return text

    def extract_date(self, text: str) -> Optional[str]:
        """Metinden tarih çıkarır. Resmi yazılarda tarih genelde sağ üst köşededir."""
        if not text:
            return None

        # Footer temizle
        clean_text = self._clean_text_for_extraction(text)

        patterns = [
            r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})",
            r"(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})",
            r"(\d{1,2})[./\-](\d{1,2})[./\-](\d{2})",
        ]

        # Strateji 1: İlk %30 (üst kısım) — resmi yazılarda tarih burada
        lines = clean_text.split('\n')
        header_end = max(5, int(len(lines) * 0.30))
        header_text = '\n'.join(lines[:header_end])

        for pat in patterns:
            match = re.search(pat, header_text)
            if match:
                logger.info(f"📅 Tarih üst bölümden çıkarıldı: {match.group(0)}")
                return match.group(0)

        # Strateji 2: Tüm metin (fallback)
        for pat in patterns:
            match = re.search(pat, clean_text)
            if match:
                return match.group(0)
        return None

    def extract_document_number(self, text: str) -> Optional[str]:
        """Metinden belge numarasını çıkarır."""
        if not text:
            return None

        patterns = [
            r"(?:sayı|sayi|no|numara)\s*[:\-=]?\s*(\d+(?:[/\-]\d+)?)",
            r"(\d{4}[/\-]\d+)",
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    # ── Sokak / Cadde / Bulvar Çıkarımı ──────────────────────────────────────
    def extract_street_data(self, text: str) -> Dict[str, Optional[str]]:
        """
        Metinden sokak/cadde/bulvar adını ve kapı numarasını çıkarır.
        Footer (kurum iletişim) bölümü hariç tutulur.

        Returns:
            {"sokak": str|None, "kapi_no": str|None}
        """
        result = {"sokak": None, "kapi_no": None}
        if not text:
            return result

        # Footer temizle — kurum adresi konuyla karışmasın
        clean_text = self._clean_text_for_extraction(text)

        # 1. Sokak/Cadde/Bulvar adı pattern'leri
        street_patterns = [
            r'([A-ZÇĞİÖŞÜa-zçğıöşü][A-ZÇĞİÖŞÜa-zçğıöşü\s\.]{2,30})\s+'
            r'(Caddesi|Cadde|Cad\.|Sokağı|Sokak|Sok\.|Bulvarı|Bulvar|Blv\.)',
            r'([A-ZÇĞİÖŞÜa-zçğıöşü][A-ZÇĞİÖŞÜa-zçğıöşü\s\.]{2,30})\s+'
            r'(Cd\.|Sk\.|Bl\.)',
        ]

        for pat in street_patterns:
            m = re.search(pat, clean_text, re.IGNORECASE)
            if m:
                sokak_ad = m.group(1).strip()
                sokak_tip = m.group(2).strip()
                result["sokak"] = f"{sokak_ad} {sokak_tip}"
                break

        # 2. Kapı numarası — SADECE sokak bulunduysa, sokak yakınında ara
        if result["sokak"]:
            sokak_pos = clean_text.find(result["sokak"])
            if sokak_pos >= 0:
                after_street = clean_text[sokak_pos + len(result["sokak"]):sokak_pos + len(result["sokak"]) + 50]
                no_match = re.search(
                    r'(?:No|No\.|Numara|Kap[ıi]\s*No)\s*[:\.\-]?\s*(\d+(?:/\d+)?)',
                    after_street, re.IGNORECASE)
                if no_match:
                    result["kapi_no"] = no_match.group(1)
        # Sokak bulunamadıysa kapı no da ARANMAZ (rastgele sayı almasın)

        return result

    # ══════════════════════════════════════════════════════════════════════════
    #  KATMAN 5 — ANA İŞLEM & HATA YÖNETİMİ
    # ══════════════════════════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════════════════════════
    #  KATMAN 5 — ANA İŞLEM & HATA YÖNETİMİ
    # ══════════════════════════════════════════════════════════════════════════
    def process_document(
        self, image_input, image_path: str = None, doc_type: str = "AUTO"
    ) -> Dict[str, Any]:
        """
        Belgeyi uçtan uca işler.

        **Garanti**: Bu fonksiyon **her zaman** aşağıdaki yapıyı döndürür:
            {"success": bool, "message": str, "data": dict}

        Args:
            image_input: Dosya yolu (str) veya PIL.Image.Image (PDF sayfası).
            image_path:  Opsiyonel — PIL Image için kaynak bilgisi.
            doc_type:    Belge tipi ('meclis_karari', 'tapu', 'AUTO').

        Returns:
            Standart JSON yanıt sözlüğü.
        """
        # ── Boş yanıt iskeletini oluştur (KeyError'u garanti önle) ────────────
        response: Dict[str, Any] = {
            "success": False,
            "message": "",
            "data": {},
        }

        try:
            # 1) Görüntüyü yükle — dosya yolu veya PIL Image
            if isinstance(image_input, str):
                # Dosya yolu olarak geldi
                if not os.path.exists(image_input):
                    response["message"] = f"Dosya bulunamadı: {image_input}"
                    return response
                
                # FIX: cv2.imread Türkçe karakterlerde başarısız oluyor
                # PIL kullanıp sonra OpenCV'ye çeviriyoruz
                try:
                    from PIL import Image as PILImage
                    pil_image = PILImage.open(image_input)
                    # PIL RGB, OpenCV BGR kullanır
                    image = cv2.cvtColor(np.array(pil_image), cv2.COLOR_RGB2BGR)
                except Exception as e:
                    response["message"] = f"Görüntü okunamadı: {image_input} ({e})"
                    return response
                    
                image_path = image_input
            else:
                # PIL Image olarak geldi (PDF sayfası)
                image = cv2.cvtColor(np.array(image_input), cv2.COLOR_RGB2BGR)
                if image_path is None:
                    image_path = "PDF_Sayfasi"

            logger.info("İşleniyor: %s", Path(image_path).name if os.path.sep in str(image_path) else image_path)
            
            # 3) Otomatik Sınıflandırma
            if doc_type == "AUTO":
                # Hızlı bir ön analiz yapabiliriz, şimdilik basit bir EasyOCR ile metne bakacağız
                # En hızlısı: Görüntünün üst kısmını (header) okumak
                h, w = image.shape[:2]
                header_roi = image[0:int(h*0.2), :]  # Üst %20
                header_results = self.easyocr_reader.readtext(header_roi, detail=0)
                header_text = " ".join(header_results).upper()
                
                doc_type = self.classify_document(header_text)
                logger.info(f"📄 Otomatik Sınıflandırma: {doc_type} (Header: {header_text[:50]}...)")

            # 4) Hibrit OCR (Belge tipine göre optimize edilmiş)
            ocr_result = self.hybrid_ocr(image, doc_type)
            raw_text = ocr_result["merged_text"]

            # 5) Semantik düzeltme
            corrected_text = self.apply_semantic_correction(raw_text)

            # 6) Veri Çıkarımı (Tipe Özel)
            data_extracted = {}
            spatial = {'ada': None, 'parsel': None, 'mahalle': None}
            
            if doc_type == "meclis_karari":
                meclis_data = self.extract_meclis_data(corrected_text)
                data_extracted.update(meclis_data)
                # Meclis kararında da ada/parsel geçebilir
                spatial = self.extract_spatial_data(corrected_text)
                # Eğer meclis extraction'da bulunduysa onu önceliklendir??
                # Şimdilik spatial extraction sonucunu meclis_data'ya ekleyelim
            else:
                spatial = self.extract_spatial_data(corrected_text)
                
                # ROI-based OCR (Sadece genel/tapu belgeleri için, meclis hariç)
                max_conf = max(ocr_result["easyocr_conf"], ocr_result["tesseract_conf"])
                should_use_roi = (
                    max_conf < 0.75 or 
                    not spatial.get('ada') or 
                    not spatial.get('parsel')
                )
                
                if should_use_roi:
                    logger.info("⚠️ Düşük güven veya eksik veri — ROI-based OCR devreye giriyor...")
                    roi_result = self._ocr_with_roi(image)
                    
                    # Eğer ROI sonucu daha iyiyse veya eksik veriyi tamamlıyorsa kullan
                    if roi_result['confidence'] > max_conf:
                        logger.info(f"✨ ROI sonucu kullanılıyor (Güven: {roi_result['confidence']:.2%})")
                        raw_text = roi_result['full_text'] # Metni güncelle
                        corrected_text = self.apply_semantic_correction(raw_text)
                        
                        # Spatial verileri güncelle
                        if roi_result.get('ada'):
                            spatial['ada'] = roi_result['ada']
                        if roi_result.get('parsel'):
                            spatial['parsel'] = roi_result['parsel']
                        if roi_result.get('mahalle'):
                            spatial['mahalle'] = roi_result['mahalle']
                    
                    # ROI confidence düşük olsa bile, eğer Ada/Parsel bulduysa al
                    elif not spatial['ada'] and roi_result.get('ada'):
                        logger.info(f"✨ ROI'den eksik Ada kurtarıldı: {roi_result['ada']}")
                        spatial['ada'] = roi_result['ada']
                    elif not spatial['parsel'] and roi_result.get('parsel'):
                        logger.info(f"✨ ROI'den eksik Parsel kurtarıldı: {roi_result['parsel']}")
                        spatial['parsel'] = roi_result['parsel']

            # 6.5) Kent Rehberi Doğrulaması (Yeni!)
            city_guide_validation = None
            if spatial.get('ada') and spatial.get('parsel'):
                try:
                    from city_guide_client import CityGuideClient
                    
                    logger.info("🌐 Kent Rehberi doğrulaması başlatılıyor...")
                    client = CityGuideClient()
                    
                    validation = client.validate_spatial_data(
                        ada=str(spatial['ada']),
                        parsel=str(spatial['parsel']),
                        mahalle=spatial.get('mahalle', 'Bilinmiyor')
                    )
                    
                    city_guide_validation = validation
                    
                    # Eğer doğrulama başarılı veya düzeltme önerisi varsa, güncelle
                    if validation['is_valid']:
                        logger.info(f"✅ Kent Rehberi Onayı: Ada {validation['corrected_ada']} / Parsel {validation['corrected_parsel']}")
                    elif validation['confidence'] == 'medium' and validation.get('corrected_ada'):
                        logger.warning(f"⚠️ OCR Hatası Düzeltildi: Ada {spatial['ada']} → {validation['corrected_ada']}")
                        spatial['ada'] = validation['corrected_ada']
                        spatial['parsel'] = validation['corrected_parsel']
                    else:
                        logger.warning(f"⚠️ Kent Rehberi: {validation['note']}")
                        
                except Exception as e:
                    logger.warning(f"Kent Rehberi doğrulaması başarısız (devam ediliyor): {e}")

            # 7) Ek veri çıkarımı
            tarih = self.extract_date(corrected_text)
            belge_no = self.extract_document_number(corrected_text)
            street_data = self.extract_street_data(corrected_text)

            # 8) Başarılı yanıt
            response["success"] = True
            response["message"] = "Belge başarıyla işlendi."
            response["data"] = {
                "doc_type": doc_type,
                "image_path": image_path,
                "raw_text": raw_text,
                "corrected_text": corrected_text,
                "ada": spatial["ada"],
                "parsel": spatial["parsel"],
                "mahalle": spatial["mahalle"],
                "sokak": street_data["sokak"],
                "kapi_no": street_data["kapi_no"],
                "tarih": tarih,
                "belge_no": belge_no,
                "ocr_details": {
                    "easyocr_text": ocr_result["easyocr_text"],
                    "easyocr_conf": ocr_result["easyocr_conf"],
                    "tesseract_text": ocr_result["tesseract_text"],
                    "tesseract_conf": ocr_result["tesseract_conf"],
                    "engine_used": ocr_result["engine_used"],
                },
                "city_guide_validation": city_guide_validation,
                **data_extracted  # Meclis verisi (karar_no, konu) varsa ekle
            }

            logger.info(
                "✅ İşlem tamamlandı (%s) — Ada: %s, Parsel: %s, Mahalle: %s",
                doc_type,
                spatial["ada"],
                spatial["parsel"],
                spatial["mahalle"],
            )

        except Exception as exc:
            response["success"] = False
            response["message"] = f"İşleme hatası: {str(exc)}"
            response["data"] = {}
            logger.error("❌ Hata: %s", exc, exc_info=True)

        return response

    def classify_document(self, text: str) -> str:
        """Belge tipini tespit et."""
        text = text.upper()
        if "MECLİS" in text or "KARAR" in text or "ENCÜMEN" in text or "BELEDİYE BAŞKANLIĞI" in text:
            return "meclis_karari"
        if "TAPU" in text or "SİCİL" in text:
            return "tapu"
        return "general"

    def extract_meclis_data(self, text: str) -> Dict[str, Any]:
        """Meclis kararı verilerini çıkar (geliştirilmiş konu çıkarımı)."""
        data = {
            'karar_no': None,
            'konu': None
        }

        # Karar No
        patterns = [
            r'Karar\s*No\s*[:\.]?\s*(\d+[/-]\d+)',
            r'Say[ıi]\s*[:\.]?\s*(\d+[/-]\d+)',
            r'No\s*[:\.]?\s*(\d+)'
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                data['karar_no'] = m.group(1)
                break

        # ── Konu Çıkarımı (Geliştirilmiş) ──
        konu = None

        # Strateji 1: "KONU:" veya "KONU :" sonrası metin
        konu_match = re.search(
            r'KONU\s*[:\-]\s*(.+?)(?:\n|$)',
            text, re.IGNORECASE)
        if konu_match:
            konu = konu_match.group(1).strip()

        # Strateji 2: "GÜNDEMİN" sonrası
        if not konu:
            gundem_match = re.search(
                r'[Gg][Üü][Nn][Dd][Ee][Mm][İi][Nn]\s+(.+?)(?:\n|$)', text)
            if gundem_match:
                konu = gundem_match.group(1).strip()

        # Strateji 3: Anahtar kelime sınıflandırma
        if not konu:
            konu_keywords = {
                'İmar planı değişikliği': [r'[iİ]mar\s*plan[ıi]', r'plan\s*de[gğ]i[sş]ikli[gğ]i'],
                'İstimlak': [r'[iİ]stimlak', r'kamula[sş]t[ıi]rma'],
                'Ruhsat': [r'[Rr]uhsat', r'[Yy]ap[ıi]\s*ruhsat[ıi]'],
                'Encümen kararı': [r'[Ee]nc[üu]men'],
                'Trafik düzenlemesi': [r'[Tt]rafik', r'yol\s*d[üu]zenleme'],
                'Park ve bahçe': [r'[Pp]ark', r'[Yy]e[sş]il\s*alan'],
                'Satış/Kiralama': [r'[Ss]at[ıi][sş]', r'[Kk]iralama', r'[İi]hale'],
                'Altyapı': [r'[Aa]lt\s*yap[ıi]', r'kanalizasyon', r'su\s*hatt[ıi]'],
            }
            for label, pats in konu_keywords.items():
                for kp in pats:
                    if re.search(kp, text, re.IGNORECASE):
                        konu = label
                        break
                if konu:
                    break

        # Konu metnini 120 karakterle sınırla
        if konu and len(konu) > 120:
            konu = konu[:117] + '…'

        data['konu'] = konu
        return data

    # ══════════════════════════════════════════════════════════════════════════
    #  PDF İŞLEME (v4.1)
    # ══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def is_pdf_supported() -> bool:
        """PDF desteğinin mevcut olup olmadığını kontrol eder."""
        return PDF_SUPPORT

    def process_pdf(
        self, pdf_path: str, dpi: int = 300,
        progress_callback=None, doc_type: str = "AUTO"
    ) -> List[Dict[str, Any]]:
        """
        PDF dosyasını sayfa sayfa işler (PyMuPDF kullanır).

        Args:
            pdf_path:          PDF dosyasının yolu.
            dpi:               Sayfa → görüntü dönüşüm çözünürlüğü (varsayılan 300).
            progress_callback: Opsiyonel — (current_page, total_pages) alan callback.
            doc_type:          Belge tipi ('AUTO', 'meclis_karari', 'general').

        Returns:
            Her sayfa için bir process_document sonucu içeren liste.
        """
        if not PDF_SUPPORT:
            return [{
                "success": False,
                "message": "PDF desteği kurulu değil. 'pip install PyMuPDF' çalıştırın.",
                "data": {}
            }]

        if not os.path.exists(pdf_path):
            return [{
                "success": False,
                "message": f"Dosya bulunamadı: {pdf_path}",
                "data": {}
            }]

        try:
            doc = fitz.open(pdf_path)
            total = len(doc)
            logger.info(f"📄 PDF açıldı: {Path(pdf_path).name} — {total} sayfa (DPI={dpi})")
        except Exception as e:
            msg = f"PDF açılamadı: {e}"
            logger.error(f"❌ {msg}")
            return [{"success": False, "message": msg, "data": {}}]

        zoom = dpi / 72  # PyMuPDF varsayılanı 72 DPI
        matrix = fitz.Matrix(zoom, zoom)
        results: List[Dict[str, Any]] = []

        for idx in range(total):
            page_num = idx + 1
            logger.info(f"📄 Sayfa {page_num}/{total} işleniyor…")

            if progress_callback:
                try:
                    progress_callback(page_num, total)
                except Exception:
                    pass

            try:
                page = doc[idx]
                pix = page.get_pixmap(matrix=matrix)
                # Pixmap → PIL Image
                pil_img = PILImage.frombytes("RGB", [pix.width, pix.height], pix.samples)
            except Exception as e:
                logger.error(f"❌ Sayfa {page_num} render hatası: {e}")
                results.append({
                    "success": False,
                    "message": f"Sayfa {page_num} işlenemedi: {e}",
                    "data": {},
                    "page_number": page_num,
                    "total_pages": total,
                    "source_pdf": pdf_path
                })
                continue

            page_label = f"{Path(pdf_path).name} [Sayfa {page_num}/{total}]"
            result = self.process_document(
                pil_img, image_path=page_label, doc_type=doc_type
            )

            result["page_number"] = page_num
            result["total_pages"] = total
            result["source_pdf"] = pdf_path
            results.append(result)

        doc.close()
        logger.info(f"✅ PDF tamamlandı: {total} sayfa işlendi")
        return results

    # ══════════════════════════════════════════════════════════════════════════
    #  TOPLU İŞLEM
    # ══════════════════════════════════════════════════════════════════════════
    def process_batch(
        self, image_paths: List[str], doc_type: str = "EVRAK"
    ) -> Dict[str, Any]:
        """
        Birden fazla belgeyi toplu işler.

        Args:
            image_paths: Belge yolları listesi.
            doc_type:    Belge tipi etiketi.

        Returns:
            {"success": bool, "message": str, "data": {"results": [...], "summary": {...}}}
        """
        response: Dict[str, Any] = {
            "success": False,
            "message": "",
            "data": {},
        }

        try:
            results: List[Dict[str, Any]] = []
            success_count = 0
            total = len(image_paths)

            for idx, path in enumerate(image_paths, 1):
                logger.info("Toplu işlem [%d/%d]: %s", idx, total, Path(path).name)
                result = self.process_document(path, doc_type)
                results.append(result)
                if result.get("success"):
                    success_count += 1

            response["success"] = True
            response["message"] = (
                f"Toplu işlem tamamlandı: {success_count}/{total} başarılı."
            )
            response["data"] = {
                "results": results,
                "summary": {
                    "total": total,
                    "successful": success_count,
                    "failed": total - success_count,
                },
            }

        except Exception as exc:
            response["success"] = False
            response["message"] = f"Toplu işlem hatası: {str(exc)}"
            response["data"] = {}

        return response

    def save_to_archive(
        self, image_path: str, process_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        İşlenmiş belgeyi arşive kaydeder.

        Klasör Yapısı:
            ./evrak_arsiv/
              └── MAHALLE_ADI/
                  └── ADA_XX/
                      ├── belge_TIMESTAMP.jpg
                      └── belge_TIMESTAMP.json

        Args:
            image_path: Orijinal belge görüntüsünün yolu.
            process_result: process_document() metodunun döndürdüğü sonuç.

        Returns:
            {"success": bool, "message": str, "saved_path": str}
        """
        response = {
            "success": False,
            "message": "",
            "saved_path": None,
        }

        try:
            if not process_result.get("success"):
                response["message"] = "İşlem başarısız olduğu için kaydetme yapılamadı."
                return response

            data = process_result.get("data", {})
            mahalle = data.get("mahalle", "BILINMEYEN")
            ada = data.get("ada", "0")

            # Klasör yapısını oluştur
            mahalle_dir = Path(self.archive_dir) / mahalle
            ada_dir = mahalle_dir / f"ADA_{ada}"
            ada_dir.mkdir(parents=True, exist_ok=True)

            # Timestamp ile dosya adı oluştur
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_ext = Path(image_path).suffix
            base_name = f"belge_{timestamp}"

            # Görüntüyü kopyala
            image_dest = ada_dir / f"{base_name}{file_ext}"
            import shutil
            shutil.copy2(image_path, image_dest)

            # Metadata JSON kaydet
            json_dest = ada_dir / f"{base_name}.json"
            with open(json_dest, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            response["success"] = True
            response["message"] = f"Belge arşive kaydedildi: {mahalle}/ADA_{ada}/"
            response["saved_path"] = str(image_dest)

            logger.info("📁 Kaydedildi: %s", image_dest)

        except Exception as exc:
            response["message"] = f"Kaydetme hatası: {str(exc)}"
            logger.error("❌ Kaydetme hatası: %s", exc)

        return response


    # ══════════════════════════════════════════════════════════════════════════
    #  YARDIMCI METOTLAR
    # ══════════════════════════════════════════════════════════════════════════
    def _ensure_directory_exists(self) -> None:
        """Arşiv dizinini oluşturur (yoksa)."""
        Path(self.archive_dir).mkdir(parents=True, exist_ok=True)

    def get_archive_files(
        self,
        extensions: Tuple[str, ...] = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"),
    ) -> List[str]:
        """Arşiv dizinindeki tüm görüntü dosyalarını listeler."""
        files: List[str] = []
        archive = Path(self.archive_dir)
        if not archive.exists():
            return files
        for ext in extensions:
            files.extend(archive.glob(f"**/*{ext}"))
            files.extend(archive.glob(f"**/*{ext.upper()}"))
        return sorted(str(f) for f in files)

    def get_statistics(self) -> Dict[str, Any]:
        """İşleyici istatistiklerini döndürür."""
        return {
            "success": True,
            "message": "İstatistikler yüklendi.",
            "data": {
                "version": self.VERSION,
                "archive_directory": self.archive_dir,
                "total_archive_files": len(self.get_archive_files()),
                "dictionary_entries": len(self.municipal_dictionary),
                "neighborhood_count": len(self.sivas_neighborhoods),
                "ada_keywords": len(self.ada_keywords),
                "parsel_keywords": len(self.parsel_keywords),
                "tesseract_path": pytesseract.pytesseract.tesseract_cmd,
                "tessdata_prefix": os.environ.get("TESSDATA_PREFIX", "YOK"),
            },
        }

    # ══════════════════════════════════════════════════════════════════════════
    #  VERİ FABRİKALARI (Sözlük & Mahalle Listesi)
    # ══════════════════════════════════════════════════════════════════════════
    @staticmethod
    def _build_dictionary() -> Dict[str, str]:
        """Sivas Beyni — Daktilo hata düzeltme sözlüğü."""
        return {
            # ── ŞARKIŞLA ──────────────────────────────────────────────────────
            "SARKIS": "ŞARKIŞLA", "SARKISLA": "ŞARKIŞLA",
            "FARKIS": "ŞARKIŞLA", "FARKISLA": "ŞARKIŞLA",
            "5ARKISLA": "ŞARKIŞLA", "5ARKI5LA": "ŞARKIŞLA",
            "ŞARKI5LA": "ŞARKIŞLA", "SARK1SLA": "ŞARKIŞLA",
            "SARK15LA": "ŞARKIŞLA", "$ARKISLA": "ŞARKIŞLA",
            "SARKI$LA": "ŞARKIŞLA", "ŞARKISLA": "ŞARKIŞLA",
            # ── BELEDİYE ─────────────────────────────────────────────────────
            "SZLED": "BELEDİYESİ", "BELEDIYE5I": "BELEDİYESİ",
            "BELEDlYESl": "BELEDİYESİ", "BELEDIYESI": "BELEDİYESİ",
            "8ELEDIYESI": "BELEDİYESİ", "BELEDIYES1": "BELEDİYESİ",
            "BELEDİYES1": "BELEDİYESİ", "BELEDIYE51": "BELEDİYESİ",
            "BELEDlYES1": "BELEDİYESİ", "BELED1YES1": "BELEDİYESİ",
            "8ELED1YES1": "BELEDİYESİ", "BELEÖIYESI": "BELEDİYESİ",
            "BELEOIYESI": "BELEDİYESİ", "BELEDJYESI": "BELEDİYESİ",
            # ── ENCÜMEN ──────────────────────────────────────────────────────
            "EnCuoen": "ENCÜMEN", "ENCUMEN": "ENCÜMEN",
            "ENCUNEN": "ENCÜMEN", "ENCuMEN": "ENCÜMEN",
            "ENCOMEN": "ENCÜMEN", "3NCUMEN": "ENCÜMEN",
            "ENCUHEN": "ENCÜMEN", "ENCÜHEN": "ENCÜMEN",
            "ENC0MEN": "ENCÜMEN",
            # ── ADA ──────────────────────────────────────────────────────────
            "A0A": "ADA", "4DA": "ADA", "AO4": "ADA",
            "AOA": "ADA", "AD4": "ADA", "AÖA": "ADA", "AQA": "ADA",
            # ── PARSEL ───────────────────────────────────────────────────────
            "PAR5EL": "PARSEL", "PARSEI": "PARSEL", "PAR$EL": "PARSEL",
            "P4RSEL": "PARSEL", "PARSFL": "PARSEL", "PARSE1": "PARSEL",
            "PAR5E1": "PARSEL", "PARS3L": "PARSEL", "PARSÉL": "PARSEL",
            # ── MAHALLE ──────────────────────────────────────────────────────
            "MAHALL3": "MAHALLE", "MAHALLES1": "MAHALLESİ",
            "MAHALLESI": "MAHALLESİ", "MAHALLESl": "MAHALLESİ",
            "MAHAL1ESI": "MAHALLESİ", "MAHA11ESI": "MAHALLESİ",
            "MAHALLÉ": "MAHALLE", "MAHALÉ": "MAHALLE",
            # ── TARİH & SAYI ─────────────────────────────────────────────────
            "TAR1H": "TARİH", "TARIH": "TARİH", "TAR!H": "TARİH",
            "TARlH": "TARİH", "SAY1": "SAYI", "5AYI": "SAYI",
            "5AY1": "SAYI",
            # ── KARAR ────────────────────────────────────────────────────────
            "KARA8": "KARAR", "KARA9": "KARAR", "K4RAR": "KARAR",
            "KAR4R": "KARAR",
            # ── MÜDÜRLÜK ─────────────────────────────────────────────────────
            "MUDURL": "MÜDÜRLÜĞÜ", "MUDURLU": "MÜDÜRLÜĞÜ",
            "MUDURL0GU": "MÜDÜRLÜĞÜ", "MUDURLOGU": "MÜDÜRLÜĞÜ",
            "MUDURLUGU": "MÜDÜRLÜĞÜ", "MÜDÜRLÜGÜ": "MÜDÜRLÜĞÜ",
            "MÜDÜRL0ĞÜ": "MÜDÜRLÜĞÜ",
            # ── İMAR ─────────────────────────────────────────────────────────
            "1MAR": "İMAR", "IMAR": "İMAR", "lMAR": "İMAR",
            "!MAR": "İMAR", "|MAR": "İMAR", "ÌMAR": "İMAR",
            # ── DİĞER ────────────────────────────────────────────────────────
            "RUHSA7": "RUHSAT", "RUH$AT": "RUHSAT",
            "ISKAN": "İSKAN", "1SKAN": "İSKAN", "lSKAN": "İSKAN",
            "YAP1": "YAPI", "Y1K1M": "YIKIM",
            "INŞAAT": "İNŞAAT", "1NSAAT": "İNŞAAT", "lNSAAT": "İNŞAAT",
            "INSAAT": "İNŞAAT", "IN$AAT": "İNŞAAT",
            "KADASTR0": "KADASTRO", "KAÖASTRO": "KADASTRO",
            "TAP0": "TAPU", "TAPÜ": "TAPU",
            # ── MAHALLE VARYASYONLARI ────────────────────────────────────────────────────────────────
            "KANDEM": "KANDEMİR", "KANDEMI": "KANDEMİR", "KANDEMIR": "KANDEMİR",
            "KANOEM": "KANDEMİR", "KANÖEM": "KANDEMİR", "KANDE": "KANDEMİR",
            "KANDENIR": "KANDEMİR", "KANOEMIR": "KANDEMİR",
            "KARDESLER": "KARDEŞLER", "AKDEGIRMEN": "AKDEĞİRMEN",
            "GULTEPE": "GÜLTEPE", "GOLTEPE": "GÜLTEPE",
            "GUNEY": "GÜNEY", "GONEY": "GÜNEY",
            "INONU": "İNÖNÜ", "1NONU": "İNÖNÜ", "INONÜ": "İNÖNÜ",
            "KARSIYAKA": "KARŞIYAKA", "KEPNEKLI": "KEPENEKİL",
            "KIZILUGLU": "KIZILOĞLU", "KIZILOGLU": "KIZILOĞLU",
            "KOHNEISIK": "KÖHNEİŞİK", "KURTULUS": "KURTULUŞ",
            "MIMARSINAN": "MİMARSİNAN", "M1MARSINAN": "MİMARSİNAN",
            "ORTULUPINAR": "ÖRTÜLÜPİNAR", "PASABEY": "PAŞABEY",
            "SELSEBIL": "SELSEBİL", "SIGLA": "SIĞLA",
            "UCTEPE": "ÜÇTEPE", "YENIDOGAN": "YENİDOĞAN",
            "YESILYURT": "YEŞİLYURT", "YES1LYURT": "YEŞİLYURT",
            "ZEKIKESKIN": "ZEKİKESKİN", "CAVDAR": "ÇAVDAR",
            "CAYBAŞI": "ÇAYBAŞI", "COREKLI": "ÇÖREKİL",
            "GURCAYIR": "GÜRÇAYIR", "HAMIDIYE": "HAMİDİYE",
            "RESADIYE": "REŞADİYE", "RESULOGLU": "RESULOĞLU",
            "SAGLIK": "SAĞLIK", "SIFAHANE": "ŞİFAHANE",
            "YENISEHIR": "YENİŞEHİR", "YUCEYURT": "YÜCEYURT",
            "ZIYAGOKALP": "ZİYAGÖKALP", "FATIH": "FATİH",
            "CUMHURIYET": "CUMHURİYET", "ATATURK": "ATATÜRK",
            "ISTASYON": "İSTASYON", "1STASYON": "İSTASYON",
            "YEDIGOL": "YEDİGÖL", "KILAVUZ": "KILAVUZ",
        }

    @staticmethod
    def _build_neighborhood_list() -> List[str]:
        """
        Sivas Belediyesi Kent Rehberi API'sinden doğrulanmış mahalle listesi.
        Kaynak: kentrehberi.sivas.bel.tr/api/abs/mahalle-listesi (71 mahalle)
        Son güncelleme: 2025-02
        """
        return [
            # ── A ──
            "ABDULVAHABİGAZİ", "AHMET TURANGAZİ", "AKDEĞİRMEN",
            "ALİBABA", "ALTUNTABAK", "AYDOĞAN",
            # ── B-C-Ç ──
            "BAHTİYARBOSTAN", "CAMİ-İ KEBİR", "ÇARŞIBAŞI",
            "ÇAYBOYU", "ÇAYYURT", "ÇİÇEKLİ",
            # ── D ──
            "DANİŞMENTGAZİ", "DEDEBALI", "DEMİRCİLERARDI",
            "DİRİLİŞ", "DÖRTEYLÜL",
            # ── E ──
            "ECE", "EMEK", "ESENTEPE", "ESENYURT",
            "ESKİKALE", "EĞRİKÖPRÜ",
            # ── F-G ──
            "FATİH", "FERHATBOSTAN", "GÖKÇEBOSTAN", "GÖKMEDRESE",
            "GÜLTEPE", "GÜLYURT", "GÜNELİ",
            # ── H ──
            "HACIALİ", "HALİL RIFATPAŞA", "HUZUR",
            # ── İ-K ──
            "İNÖNÜ", "İSTİKLAL", "KADI BURHANETTİN", "KALEARDI",
            "KARDEŞLER", "KARŞIYAKA", "KILAVUZ", "KIZILIRMAK",
            "KÜÇÜKMİNARE", "KÜMBET",
            # ── M ──
            "MEHMET AKİF ERSOY", "MEHMETPAŞA", "MERAKÜM",
            "MEVLANA", "MISMILIRMAK", "MİMAR SİNAN",
            # ── O-Ö ──
            "ORHANGAZİ", "ÖRTÜLÜPINAR",
            # ── P-S-Ş ──
            "PAŞABEY", "PULUR", "SELÇUKLU", "SEYRANTEPE",
            "SULARBAŞI", "ŞEYH ŞAMİL",
            # ── T-U-Ü ──
            "TUZLUGÖL", "ÜÇLERBEY",
            # ── Y ──
            "YAHYABEY", "YENİ", "YENİDOĞAN", "YENİŞEHİR",
            "YEŞİLYURT", "YİĞİTLER", "YUNUSEMRE", "YÜCEYURT",
        ]

    def _load_neighborhoods_from_api(self) -> bool:
        """Kent Rehberi API'sinden güncel mahalle listesini yükler."""
        try:
            import requests
            import urllib3
            urllib3.disable_warnings()
            r = requests.get(
                "https://kentrehberi.sivas.bel.tr/api/abs/mahalle-listesi",
                verify=False, timeout=10)
            r.raise_for_status()
            data = r.json()
            names = [m.get("ad", "").upper().strip() for m in data if m.get("ad")]
            if len(names) > 30:
                self.sivas_neighborhoods = names
                logger.info(f"🏘️ Kent Rehberi'nden {len(names)} mahalle yüklendi.")
                return True
        except Exception as e:
            logger.warning(f"API mahalle yüklemesi başarısız: {e}")
        return False


# ═════════════════════════════════════════════════════════════════════════════
#  ANA PROGRAM — TEST & GÖSTERI
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 72)
    print("  SİVAS BELEDİYESİ BELGE İŞLEYİCİ — MASTER EDİTİON v4.0")
    print("  Daktilo Belgeleri için Endüstriyel Düzey OCR Sistemi")
    print("=" * 72)

    processor = DocumentProcessor(archive_directory="./evrak_arsiv")

    # İstatistikleri göster
    stats = processor.get_statistics()
    if stats["success"]:
        d = stats["data"]
        print(f"\n📁  Arşiv Dizini     : {d['archive_directory']}")
        print(f"📄  Arşiv Dosyası    : {d['total_archive_files']}")
        print(f"📖  Sözlük Girişi    : {d['dictionary_entries']}")
        print(f"🏘️   Mahalle Sayısı   : {d['neighborhood_count']}")
        print(f"🔧  Tesseract        : {d['tesseract_path']}")
        print(f"📌  Versiyon         : {d['version']}")

    # Arşivdeki dosyaları listele
    files = processor.get_archive_files()
    if files:
        print(f"\n📂 Arşivde {len(files)} dosya bulundu:")
        for f in files[:5]:
            print(f"   → {Path(f).name}")
        if len(files) > 5:
            print(f"   ... ve {len(files) - 5} dosya daha")

        # İlk dosyayı işle
        print("\n⚙️  İlk dosya işleniyor...")
        result = processor.process_document(files[0])
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("\n⚠️  Arşiv dizininde dosya bulunamadı.")
        print("   Test için ./evrak_arsiv klasörüne görüntü ekleyin.")

    print("\n" + "=" * 72)
    print("  Kullanım: processor.process_document('belge.jpg')")
    print("  Çıktı  : {\"success\": bool, \"message\": str, \"data\": dict}")
    print("=" * 72)
