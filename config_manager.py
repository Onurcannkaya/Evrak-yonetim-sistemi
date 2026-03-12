
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any
from utils import get_base_dir

logger = logging.getLogger("ConfigManager")

class ConfigManager:
    """
    Uygulama ayarlarını yöneten sınıf.
    Ayarları 'config.json' dosyasından okur ve kaydeder.
    """
    
    DEFAULT_CONFIG = {
        "tesseract_cmd": r"C:\Program Files\Tesseract-OCR\tesseract.exe", # Standart Kurulum Yolu
        "google_api_key": "",  # Kullanıcı Ayarlar panelinden girer (Güvenlik)
        "city_guide_api_key": "",  # Gelecek için rezerv
        "theme": "Dark",
        # "ocr_engine" removed in v13.0
        "ocr_language": "tur",
        "gpu_acceleration": False
    }
    
    def __init__(self):
        self.CONFIG_FILE = os.path.join(get_base_dir(), "config.json")
        self.config = self.load_config()
        
    def load_config(self) -> Dict[str, Any]:
        """Ayarları diskten yükle, yoksa varsayılanları oluştur."""
        if not os.path.exists(self.CONFIG_FILE):
            logger.info("Ayarlar dosyası bulunamadı, varsayılanlar oluşturuluyor.")
            self.save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()
            
        try:
            with open(self.CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
                
            # Eksik anahtarları varsayılanlarla doldur (Migration)
            updated = False
            for key, val in self.DEFAULT_CONFIG.items():
                if key not in config:
                    config[key] = val
                    updated = True
            
            if updated:
                self.save_config(config)
                
            return config
        except Exception as e:
            logger.error(f"Ayarlar yüklenirken hata: {e}")
            return self.DEFAULT_CONFIG.copy()

    def save_config(self, config: Dict[str, Any]) -> bool:
        """Ayarları diske kaydet."""
        try:
            with open(self.CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            self.config = config
            logger.info("Ayarlar kaydedildi.")
            return True
        except Exception as e:
            logger.error(f"Ayarlar kaydedilemedi: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        val = self.config.get(key)
        if val is not None:
            return val
        return self.DEFAULT_CONFIG.get(key, default)

    def set(self, key: str, value: Any) -> bool:
        self.config[key] = value
        return self.save_config(self.config)
