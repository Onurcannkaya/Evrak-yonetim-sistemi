import os
import glob
from pathlib import Path
from typing import Dict, List
import logging
# from tqdm import tqdm

from document_processor import DocumentProcessor
from database_manager import DatabaseManager

# Loglama
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("BatchProcessor")

class BatchProcessor:
    """
    Toplu belge işleme motoru.
    Klasörleri tarar, belgeleri işler ve veritabanına kaydeder.
    """
    
    def __init__(self, db_path: str = "evrak_yonetim.db"):
        self.processor = DocumentProcessor()
        self.db_manager = DatabaseManager(db_path)
        
    def scan_folder(self, folder_path: str, extensions: List[str] = None) -> List[str]:
        """Klasördeki işlenecek dosyaları bulur."""
        if extensions is None:
            extensions = ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff']
            
        files = []
        for ext in extensions:
            # Recursive arama
            found = glob.glob(os.path.join(folder_path, '**', ext), recursive=True)
            files.extend(found)
            
        return sorted(list(set(files)))  # Duplicate'leri temizle ve sırala

    def run_batch(self, folder_path: str):
        """Toplu işlemi başlatır."""
        print(f"\n🚀 TOPLU İŞLEM BAŞLATILIYOR: {folder_path}")
        print("=" * 60)
        
        # 1. Dosyaları Bul
        files = self.scan_folder(folder_path)
        total_files = len(files)
        
        if total_files == 0:
            print("❌ Klasörde uygun dosya bulunamadı!")
            return
            
        print(f"📄 Toplam Dosya: {total_files}")
        
        # 2. İstatistikler
        stats = {
            'success': 0,
            'failed': 0,
            'skipped': 0,
            'approved': 0,  # Otomatik onay (>%80)
            'review': 0     # İnceleme gerekli (%50-%80)
        }
        
        # 3. İşlem Döngüsü
        print("\nİşleniyor...")
        for i, file_path in enumerate(files, 1):
            print(f"[{i}/{total_files}] İşleniyor: {Path(file_path).name}")
            try:
                # Veritabanında var mı kontrol et (Opsiyonel)
                # ...
                
                # İşle
                result = self.processor.process_document(file_path, doc_type="AUTO")
                
                if result['success']:
                    stats['success'] += 1
                    data = result['data']
                    
                    # Veritabanına kaydet
                    self.db_manager.add_document(data)
                    
                    # İstatistik güncelle
                    ocr_details = data.get('ocr_details', {})
                    conf = max(
                        ocr_details.get('easyocr_conf', 0),
                        ocr_details.get('tesseract_conf', 0)
                    )
                    
                    if conf >= 0.80:
                        stats['approved'] += 1
                    elif conf >= 0.50:
                        stats['review'] += 1
                    else:
                        stats['failed'] += 1 # Düşük güven başarısız sayılabilir veya review
                        
                else:
                    stats['failed'] += 1
                    logger.error(f"Hata ({Path(file_path).name}): {result['message']}")
                    
            except Exception as e:
                stats['failed'] += 1
                logger.error(f"Kritik Hata ({Path(file_path).name}): {e}")
                
        # 4. Rapor
        print("\n" + "=" * 60)
        print("İŞLEM TAMAMLANDI - ÖZET RAPOR")
        print("=" * 60)
        print(f"✅ Toplam Başarılı : {stats['success']}")
        print(f"🤖 Otomatik Onay  : {stats['approved']} (Güven > %80)")
        print(f"👀 İnceleme Gerekli: {stats['review']} (Güven %50-%80)")
        print(f"❌ Başarısız/Düşük : {stats['failed']}")
        print("=" * 60)
        print(f"Veritabanı: {self.db_manager.db_path}")

if __name__ == "__main__":
    import sys
    
    # Hedef klasör (Varsayılan: mevcut klasör)
    target_folder = sys.argv[1] if len(sys.argv) > 1 else "."
    
    batch_processor = BatchProcessor()
    batch_processor.run_batch(target_folder)
