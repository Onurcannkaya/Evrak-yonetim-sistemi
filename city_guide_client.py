"""
Sivas Kent Rehberi API İstemcisi
Ada/Parsel doğrulama ve mahalle eşleştirme için kullanılır.
"""

import requests
import urllib3
from typing import Optional, Dict, List
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)


class CityGuideClient:
    """Sivas Belediyesi Kent Rehberi API istemcisi."""
    
    BASE_URL = "https://kentrehberi.sivas.bel.tr"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{self.BASE_URL}/"
        })
        self._mahalle_cache = None
        
    def get_mahalle_list(self) -> List[Dict]:
        """
        Tüm mahalle listesini getirir.
        
        Returns:
            [{"no": "39778", "ad": "ABDULVAHABİGAZİ", ...}, ...]
        """
        if self._mahalle_cache:
            return self._mahalle_cache
            
        try:
            url = f"{self.BASE_URL}/api/abs/mahalle-listesi"
            response = self.session.get(url, verify=False, timeout=10)
            response.raise_for_status()
            
            self._mahalle_cache = response.json()
            logger.info(f"Mahalle listesi alındı: {len(self._mahalle_cache)} mahalle")
            return self._mahalle_cache
            
        except Exception as e:
            logger.error(f"Mahalle listesi alınamadı: {e}")
            return []
    
    def find_mahalle_by_name(self, name: str) -> Optional[Dict]:
        """
        İsme göre mahalle bulur (fuzzy matching ile).
        
        Args:
            name: Mahalle adı (örn: "Kandemir", "GÜLTEPE")
            
        Returns:
            {"no": "...", "ad": "...", ...} veya None
        """
        mahalleler = self.get_mahalle_list()
        name_upper = name.upper().strip()
        
        # Tam eşleşme
        for m in mahalleler:
            if m.get('ad', '').upper() == name_upper:
                return m
        
        # Kısmi eşleşme
        for m in mahalleler:
            ad = m.get('ad', '').upper()
            if name_upper in ad or ad in name_upper:
                logger.info(f"Fuzzy match: '{name}' -> '{m.get('ad')}'")
                return m
                
        logger.warning(f"Mahalle bulunamadı: {name}")
        return None
    
    def search_ada_parsel(self, ada: str, parsel: str, mahalle_id: Optional[str] = None) -> Optional[Dict]:
        """
        Ada/Parsel araması yapar.
        
        Args:
            ada: Ada numarası (string olarak, örn: "153")
            parsel: Parsel numarası (string olarak, örn: "93")
            mahalle_id: Mahalle ID (opsiyonel, örn: "39778")
            
        Returns:
            API'den dönen sonuç veya None
        """
        try:
            url = f"{self.BASE_URL}/api/abs/ada-parsel-ara"
            
            # API hata mesajı: "Ada ve Parsel No gereklidir"
            # Farklı payload yapılarını dene
            
            # Deneme 1: Root seviyede, Türkçe field isimleri
            payload = {
                "ada": str(ada),
                "parsel": str(parsel)
            }
            
            if mahalle_id:
                payload["mahalleId"] = str(mahalle_id)
            
            logger.info(f"Ada/Parsel arama (Deneme 1): {payload}")
            response = self.session.post(url, json=payload, verify=False, timeout=10)
            
            # Eğer başarısızsa, farklı field isimleriyle dene
            if response.status_code != 200:
                payload = {
                    "adaNo": str(ada),
                    "parselNo": str(parsel)
                }
                if mahalle_id:
                    payload["mahalleId"] = str(mahalle_id)
                    
                logger.info(f"Ada/Parsel arama (Deneme 2): {payload}")
                response = self.session.post(url, json=payload, verify=False, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Sonuç bulundu: {result}")
                return result
            else:
                logger.warning(f"❌ API Hatası ({response.status_code}): {response.text[:200]}")
                return None
                
        except Exception as e:
            logger.error(f"Ada/Parsel arama hatası: {e}")
            return None
    
    def validate_spatial_data(self, ada: str, parsel: str, mahalle: str) -> Dict[str, any]:
        """
        OCR'dan çıkan Ada/Parsel/Mahalle bilgisini Kent Rehberi ile doğrular.
        
        NOT: Mahalle doğrulaması YAPILMAZ çünkü:
        - Belgeler ilçe (Kandemir gibi) verilerini içerebilir
        - Eski mahalle isimleri güncellenmiş olabilir
        - Kent Rehberi sadece merkez Sivas mahallelerini içerir
        
        Args:
            ada: OCR'dan çıkan Ada (örn: "15" veya "153")
            parsel: OCR'dan çıkan Parsel (örn: "2" veya "93")
            mahalle: OCR'dan çıkan Mahalle (örn: "Kandemir") - Doğrulama yapılmaz, olduğu gibi kabul edilir
            
        Returns:
            {
                "is_valid": bool,  # Ada/Parsel Kent Rehberi'nde bulundu mu?
                "corrected_ada": str,
                "corrected_parsel": str,
                "corrected_mahalle": str,  # Değiştirilmez, OCR sonucu aynen kullanılır
                "confidence": str,  # "high", "medium", "low"
                "suggestions": [...],  # Alternatif Ada/Parsel önerileri
                "note": str  # Ek bilgi
            }
        """
        result = {
            "is_valid": False,
            "corrected_ada": ada,
            "corrected_parsel": parsel,
            "corrected_mahalle": mahalle,  # Mahalle OCR sonucu olduğu gibi kabul edilir
            "confidence": "low",
            "suggestions": [],
            "note": ""
        }
        
        # Mahalle doğrulaması YAPMA - Eski/İlçe isimleri olabilir
        # Direkt Ada/Parsel araması yap (tüm Sivas genelinde)
        
        logger.info(f"🔍 Ada/Parsel doğrulama: {mahalle} - Ada {ada} / Parsel {parsel}")
        
        # 1. Direkt arama (mahalle ID'si olmadan - tüm Sivas)
        search_result = self.search_ada_parsel(ada, parsel, mahalle_id=None)
        
        if search_result and len(search_result) > 0:
            result["is_valid"] = True
            result["confidence"] = "high"
            result["note"] = f"Kent Rehberi'nde {len(search_result)} kayıt bulundu"
            logger.info(f"✅ Doğrulama başarılı: Ada {ada} / Parsel {parsel} (Kayıt sayısı: {len(search_result)})")
            return result
        
        # 2. Bulunamadıysa, alternatif Ada numaraları dene
        # OCR hatası olabilir: "15" -> "150", "151", "152", "153", vb.
        logger.info("⚠️ Direkt eşleşme yok, alternatif Ada numaraları deneniyor...")
        
        suggestions = []
        
        # Ada'nın başına/sonuna rakam ekleyerek dene
        for prefix in ["", "1", "2"]:
            for suffix in ["", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]:
                alt_ada = f"{prefix}{ada}{suffix}"
                
                # Aynı sayıyı tekrar deneme, çok uzun sayıları deneme
                if alt_ada == ada or len(alt_ada) > 5:
                    continue
                
                alt_result = self.search_ada_parsel(alt_ada, parsel, mahalle_id=None)
                
                if alt_result and len(alt_result) > 0:
                    suggestions.append({
                        "ada": alt_ada,
                        "parsel": parsel,
                        "mahalle": mahalle,  # Mahalle değişmez
                        "count": len(alt_result)
                    })
                    
                    # İlk 5 öneriyle yetinelim (performans için)
                    if len(suggestions) >= 5:
                        break
            
            if len(suggestions) >= 5:
                break
        
        if suggestions:
            result["confidence"] = "medium"
            result["suggestions"] = suggestions
            result["corrected_ada"] = suggestions[0]["ada"]  # En olası düzeltme
            result["note"] = f"OCR hatası olabilir. {len(suggestions)} alternatif bulundu."
            logger.info(f"⚠️ Alternatif bulundu: Ada {suggestions[0]['ada']} ({suggestions[0]['count']} kayıt)")
        else:
            result["note"] = "Kent Rehberi'nde bulunamadı. İlçe/Belde kaydı olabilir."
            logger.warning(f"❌ Hiçbir eşleşme bulunamadı: Ada {ada} / Parsel {parsel}")
        
        return result

    @staticmethod
    def get_map_url(ada: str, parsel: str = None) -> str:
        """Kent Rehberi haritasında parseli gösteren URL oluşturur."""
        base = "https://kentrehberi.sivas.bel.tr"
        if parsel:
            return f"{base}/?ada={ada}&parsel={parsel}"
        return f"{base}/?ada={ada}"


# Test kodu
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
    
    client = CityGuideClient()
    
    # Test 1: Mahalle listesi
    print("\n=== MAHALLE LİSTESİ ===")
    mahalleler = client.get_mahalle_list()
    print(f"Toplam: {len(mahalleler)} mahalle")
    print("İlk 5:", [m['ad'] for m in mahalleler[:5]])
    
    # Test 2: Mahalle arama
    print("\n=== MAHALLE ARAMA ===")
    test_names = ["GÜLTEPE", "Kandemir", "FATIH"]
    for name in test_names:
        result = client.find_mahalle_by_name(name)
        if result:
            print(f"✓ {name} -> {result['ad']} (ID: {result['no']})")
        else:
            print(f"✗ {name} -> Bulunamadı")
    
    # Test 3: Ada/Parsel arama (Mahalle ID olmadan - tüm Sivas)
    print("\n=== ADA/PARSEL ARAMA (Tüm Sivas) ===")
    result = client.search_ada_parsel("100", "1", mahalle_id=None)
    print(f"Ada 100 / Parsel 1 Sonuç: {len(result) if result else 0} kayıt")
    
    # Test 4: Doğrulama (Kandemir - İlçe verisi)
    print("\n=== DOĞRULAMA TESTİ (İlçe Verisi) ===")
    validation = client.validate_spatial_data("15", "2", "Kandemir")
    print(f"Mahalle: {validation['corrected_mahalle']} (OCR sonucu olduğu gibi)")
    print(f"Geçerli: {validation['is_valid']}")
    print(f"Güven: {validation['confidence']}")
    print(f"Not: {validation['note']}")
    if validation['corrected_ada'] != "15":
        print(f"Önerilen Düzeltme: Ada {validation['corrected_ada']} / Parsel {validation['corrected_parsel']}")
    if validation['suggestions']:
        print(f"Alternatifler: {len(validation['suggestions'])} adet")
