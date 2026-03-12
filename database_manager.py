import sqlite3
import json
import logging
import hashlib
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from utils import get_base_dir

# Loglama
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DBManager")


class DatabaseManager:
    """
    Evrak Yönetim Sistemi Veritabanı Yöneticisi (SQLite) — v5.0

    Şema:
    - documents: İşlenen belgeler (sokak, kapi_no, file_hash dahil)
    - parcels: Tespit edilen parseller
    - document_parcels: Belge-Parsel ilişkileri (M2M)
    - streets: Sokak/Cadde/Bulvar kayıtları
    - document_streets: Belge-Sokak ilişkileri (M2M)
    """

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = os.path.join(get_base_dir(), "evrak_yonetim.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Veritabanı tablolarını oluştur + migration."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Performans optimizasyonları
        cursor.execute("PRAGMA journal_mode=WAL")      # Eşzamanlı okuma/yazma
        cursor.execute("PRAGMA synchronous=NORMAL")    # Hızlı yazma
        cursor.execute("PRAGMA cache_size=10000")       # ~40MB önbellek
        cursor.execute("PRAGMA mmap_size=268435456")    # 256MB memory-mapped IO

        # 1. Belgeler Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT,
                file_hash TEXT,             -- MD5 hash (duplikasyon kontrolü)
                page_number INTEGER DEFAULT 1,  -- PDF sayfa numarası
                doc_type TEXT,              -- 'tapu', 'meclis_karari', 'general'
                processed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ocr_confidence REAL,
                status TEXT,                -- 'approved', 'needs_review', 'failed'
                extracted_date TEXT,
                document_number TEXT,        -- Karar No veya Belge No
                subject TEXT,               -- Konu (Meclis kararı için)
                sokak TEXT,                 -- Sokak/Cadde adı
                kapi_no TEXT,               -- Kapı numarası
                raw_text TEXT,
                corrected_text TEXT,
                metadata JSON               -- Ek veriler
            )
        ''')

        # 2. Parseller Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS parcels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mahalle TEXT,
                ada TEXT,
                parsel TEXT,
                UNIQUE(mahalle, ada, parsel)
            )
        ''')

        # 3. İlişki Tablosu (Belge-Parsel)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_parcels (
                doc_id INTEGER,
                parcel_id INTEGER,
                FOREIGN KEY (doc_id) REFERENCES documents(id),
                FOREIGN KEY (parcel_id) REFERENCES parcels(id),
                UNIQUE(doc_id, parcel_id)
            )
        ''')

        # 4. Sokaklar Tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS streets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mahalle TEXT,
                sokak TEXT,
                UNIQUE(mahalle, sokak)
            )
        ''')

        # 5. İlişki Tablosu (Belge-Sokak)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS document_streets (
                doc_id INTEGER,
                street_id INTEGER,
                kapi_no TEXT,
                FOREIGN KEY (doc_id) REFERENCES documents(id),
                FOREIGN KEY (street_id) REFERENCES streets(id),
                UNIQUE(doc_id, street_id)
            )
        ''')

        # 6. Kullanıcılar Tablosu (RBAC - v7.0)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'personel', -- 'admin', 'personel'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 7. İşlem Kütüğü (Audit Logs - v7.0)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                action TEXT NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 8. QGIS Entegrasyon Görünümü (View) - v10.0
        # If view exists, we should recreate it to ensure it uses the JOINS 
        cursor.execute("DROP VIEW IF EXISTS vw_qgis_evraklar")
        cursor.execute('''
            CREATE VIEW vw_qgis_evraklar AS
            SELECT 
                d.id,
                UPPER(TRIM(p.mahalle)) as mahalle,
                UPPER(TRIM(p.ada)) as ada,
                UPPER(TRIM(p.parsel)) as parsel,
                d.doc_type,
                d.subject,
                d.extracted_date,
                d.file_path,
                REPLACE(d.file_path, '/', '\\') as win_file_path
            FROM documents d
            JOIN document_parcels dp ON d.id = dp.doc_id
            JOIN parcels p ON dp.parcel_id = p.id
            WHERE d.status != 'silindi'
        ''')

        # 9. FTS5 Tam Metin Arama Sanal Tablosu (v7.0)
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                doc_id UNINDEXED,
                raw_text,
                corrected_text,
                subject,
                mahalle,
                ada,
                parsel,
                file_name
            )
        ''')


        # ── Performans İndexleri ──
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(doc_type)",
            "CREATE INDEX IF NOT EXISTS idx_docs_status ON documents(status)",
            "CREATE INDEX IF NOT EXISTS idx_docs_date ON documents(extracted_date)",
            "CREATE INDEX IF NOT EXISTS idx_docs_hash ON documents(file_hash)",
            "CREATE INDEX IF NOT EXISTS idx_docs_sokak ON documents(sokak)",
            "CREATE INDEX IF NOT EXISTS idx_parcels_ada ON parcels(ada)",
            "CREATE INDEX IF NOT EXISTS idx_parcels_mahalle ON parcels(mahalle)",
            "CREATE INDEX IF NOT EXISTS idx_streets_sokak ON streets(sokak)",
        ]
        for idx_sql in indexes:
            try:
                cursor.execute(idx_sql)
            except Exception:
                pass

        # ── Migration: Mevcut tablolara yeni sütunları ekle ──
        migrations = [
            ("documents", "file_hash", "TEXT"),
            ("documents", "sokak", "TEXT"),
            ("documents", "kapi_no", "TEXT"),
            ("documents", "page_number", "INTEGER DEFAULT 1"),
            ("documents", "sniper_image_path", "TEXT"),  # v8.4 Evidence
            ("documents", "version", "INTEGER DEFAULT 1"), # v7.0 Versioning
            ("documents", "parent_id", "INTEGER"),         # v7.0 Versioning
        ]
        for table, column, col_type in migrations:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
                logger.info(f"Migration: {table}.{column} eklendi")
            except sqlite3.OperationalError:
                pass  # Sütun zaten var

        # Eski UNIQUE index'i kaldır (file_path artık UNIQUE değil)
        try:
            cursor.execute("DROP INDEX IF EXISTS sqlite_autoindex_documents_1")
        except Exception:
            pass

        conn.commit()
        conn.close()
        
        self.get_or_create_admin()
        logger.info(f"Veritabanı başlatıldı: {self.db_path}")

    def get_or_create_admin(self):
        """Varsayılan admin ve personel kullanıcılarını oluşturur."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        users = [
            ("admin", hashlib.sha256("admin123".encode()).hexdigest(), "admin"),
            ("personel", hashlib.sha256("personel123".encode()).hexdigest(), "personel")
        ]
        
        for username, pass_hash, role in users:
            try:
                cursor.execute("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)", 
                               (username, pass_hash, role))
            except sqlite3.IntegrityError:
                pass # Zaten var
        conn.commit()
        conn.close()

    def verify_user(self, username, password) -> Optional[dict]:
        """Kullanıcının giriş bilgilerini doğrular."""
        pass_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users WHERE username=? AND password_hash=?", (username, pass_hash))
        user = cursor.fetchone()
        conn.close()
        return dict(user) if user else None

    def log_audit(self, user_id, username, action, details=""):
        """Kullanıcı işlemlerini loglar."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO audit_logs (user_id, username, action, details) VALUES (?, ?, ?, ?)",
                       (user_id, username, action, details))
        conn.commit()
        conn.close()

    # ══════════════════════════════════════════════════════════════════════════
    #  BELGE EKLEME
    # ══════════════════════════════════════════════════════════════════════════
    def add_document(self, result_data: Dict[str, Any]) -> int:
        """
        İşlenmiş belge sonucunu veritabanına kaydeder.
        Duplikasyon kontrolü yapar (file_hash).

        Returns: document_id
        Raises: DuplicateDocumentError eğer aynı dosya zaten işlenmiş ise
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # v7.0 Versiyonlama: Aynı ada/parsel/mahalle için eski evrak var mı kontrolü
            ada = result_data.get('ada')
            parsel = result_data.get('parsel')
            mahalle = result_data.get('mahalle', 'BİLİNMİYOR')
            
            version = 1
            parent_id = None
            
            if ada and mahalle and int(result_data.get('_is_version_update', 0)) == 1:
                # Sadece açıkça yeni versiyon olarak gelirse veya her yeni kayıt versiyon sayılıyorsa
                # Burada tüm aynı ada parsel'i V2 yapmak yerine sadece gerçekten "üstüne yazılan/güncellenenleri" versiyonlayalım.
                pass
            
            # Eğer otomatik ada/parsel grubuna = versiyon denilecekse:
            if ada and mahalle:
                cursor.execute('''
                    SELECT d.id, d.version FROM documents d
                    JOIN document_parcels dp ON d.id = dp.doc_id
                    JOIN parcels p ON dp.parcel_id = p.id
                    WHERE p.ada=? AND p.mahalle=? AND (p.parsel=? OR p.parsel IS NULL)
                    ORDER BY d.version DESC LIMIT 1
                ''', (str(ada), mahalle, str(parsel) if parsel else None))
                last_doc = cursor.fetchone()
                if last_doc:
                    parent_id = last_doc[0]
                    version = last_doc[1] + 1
            # 0. Hash hesapla (duplikasyon kontrolü)
            file_path = result_data.get('image_path')
            file_hash = None
            if file_path and Path(file_path).exists():
                file_hash = hashlib.md5(
                    Path(file_path).read_bytes()).hexdigest()
                # Aynı hash + sayfa var mı? (PDF sayfa bazlı kontrol)
                page_num = result_data.get('page_number', 1)
                cursor.execute(
                    "SELECT id, file_path FROM documents WHERE file_hash=? AND page_number=?",
                    (file_hash, page_num))
                existing = cursor.fetchone()
                if existing:
                    logger.warning(
                        f"⚠️ Duplikasyon: {file_path} p{page_num} → zaten ID={existing[0]}")
                    # Yine de kaydet, uyarı ekleyerek
                    result_data['_duplicate_of'] = existing[0]

            # 1. Güven ve durum belirleme (Gemini tabanlı)
            ocr_details = result_data.get('ocr_details', {})
            
            # Gemini kullanıldığında güveni alan doluluk oranından hesapla
            engine = ocr_details.get('engine', '')
            if 'gemini' in engine.lower():
                filled = 0
                total_fields = 5  # mahalle, ada, parsel, tarih, raw_text
                for fld in ('mahalle', 'ada', 'parsel', 'tarih', 'raw_text'):
                    val = result_data.get(fld, '')
                    if val and str(val).strip():
                        filled += 1
                # Temel güven: 0.5 + alan doluluk bonusu (max 0.5)
                conf = 0.5 + (filled / total_fields) * 0.5
            else:
                conf = max(
                    ocr_details.get('easyocr_conf', 0),
                    ocr_details.get('tesseract_conf', 0)
                )

            status = 'needs_review'
            if conf >= 0.80:
                status = 'approved'
            elif conf < 0.30:
                status = 'failed'

            # 2. Belgeyi ekle
            page_number = result_data.get('page_number', 1)
            cursor.execute('''
                INSERT INTO documents (
                    file_path, file_hash, page_number,
                    doc_type, ocr_confidence, status,
                    extracted_date, document_number, subject,
                    sokak, kapi_no,
                    raw_text, corrected_text, metadata,
                    sniper_image_path, version, parent_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                file_path,
                file_hash,
                page_number,
                result_data.get('doc_type', 'general'),
                conf,
                status,
                result_data.get('tarih'),
                result_data.get('belge_no') or result_data.get('karar_no'),
                result_data.get('konu'),
                result_data.get('sokak'),
                result_data.get('kapi_no'),
                result_data.get('raw_text'),
                result_data.get('corrected_text'),
                json.dumps(ocr_details),
                result_data.get('sniper_image_path'),
                version,
                parent_id
            ))

            doc_id = cursor.lastrowid

            # 3. Parsel ilişkisi
            ada = result_data.get('ada')
            parsel = result_data.get('parsel')
            mahalle = result_data.get('mahalle', 'BİLİNMİYOR')

            if ada:
                cursor.execute('''
                    INSERT OR IGNORE INTO parcels (mahalle, ada, parsel)
                    VALUES (?, ?, ?)
                ''', (mahalle, str(ada), str(parsel) if parsel else None))

                cursor.execute('''
                    SELECT id FROM parcels
                    WHERE mahalle=? AND ada=? AND (parsel=? OR parsel IS NULL)
                ''', (mahalle, str(ada), str(parsel) if parsel else None))

                row = cursor.fetchone()
                if row:
                    cursor.execute('''
                        INSERT OR IGNORE INTO document_parcels (doc_id, parcel_id)
                        VALUES (?, ?)
                    ''', (doc_id, row[0]))

            # 4. Sokak ilişkisi
            sokak = result_data.get('sokak')
            kapi_no = result_data.get('kapi_no')
            if sokak:
                cursor.execute('''
                    INSERT OR IGNORE INTO streets (mahalle, sokak)
                    VALUES (?, ?)
                ''', (mahalle, sokak))

                cursor.execute(
                    "SELECT id FROM streets WHERE mahalle=? AND sokak=?",
                    (mahalle, sokak))
                row = cursor.fetchone()
                if row:
                    cursor.execute('''
                        INSERT OR IGNORE INTO document_streets
                        (doc_id, street_id, kapi_no) VALUES (?, ?, ?)
                    ''', (doc_id, row[0], kapi_no))

            # 5. FTS5'e Ekle (V7.0)
            file_name = Path(file_path).name if file_path else ''
            cursor.execute('''
                INSERT INTO documents_fts (doc_id, raw_text, corrected_text, subject, mahalle, ada, parsel, file_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                doc_id,
                result_data.get('raw_text', ''),
                result_data.get('corrected_text', ''),
                result_data.get('konu', ''),
                mahalle,
                str(ada) if ada else '',
                str(parsel) if parsel else '',
                file_name
            ))

            conn.commit()
            logger.info(f"Belge kaydedildi ID={doc_id}: "
                        f"{Path(file_path).name if file_path else '?'}")
            return doc_id

        except Exception as e:
            logger.error(f"Veritabanı hatası: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    # ══════════════════════════════════════════════════════════════════════════
    #  SORGULAR
    # ══════════════════════════════════════════════════════════════════════════
    def get_document_by_id(self, doc_id: int) -> Optional[Dict]:
        """ID ile belge getir (parsel ve sokak bilgileri dahil)."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT d.*,
                       p.mahalle as p_mahalle, p.ada, p.parsel,
                       s.sokak as s_sokak, ds.kapi_no as s_kapi_no
                FROM documents d
                LEFT JOIN document_parcels dp ON d.id = dp.doc_id
                LEFT JOIN parcels p ON dp.parcel_id = p.id
                LEFT JOIN document_streets ds ON d.id = ds.doc_id
                LEFT JOIN streets s ON ds.street_id = s.id
                WHERE d.id = ?
            """, (doc_id,))
            row = cursor.fetchone()

            if not row:
                return None
            doc = dict(row)
            # Alanları birleştir (parsel tablosundan veya documents'tan)
            if not doc.get('p_mahalle'):
                # Documents.corrected_text'ten mahalle bilgisi çekmeyi dene
                pass
            return doc
        except Exception as e:
            logger.error(f"Belge sorgulama hatası: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def search_documents(self, query: str) -> List[Dict]:
        """Metin içinde arama yap (Case-insensitive & Geniş kapsamlı)."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # FTS5 (v7.0) Tam Metin Arama + Eski Uyumluluk LIKE Araması
            clean_query = query.replace('"', '""')
            fts_query = f'"{clean_query}"*'
            q = f"%{query}%"
            
            # 1. FTS5 sonuçlarını ID bazında topla
            fts_ids = []
            try:
                cursor.execute("SELECT doc_id FROM documents_fts WHERE documents_fts MATCH ?", (fts_query,))
                fts_ids = [row[0] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                pass
                
            # 2. Standart LIKE sorgusunu ID bazında topla
            cursor.execute("""
                SELECT id FROM documents 
                WHERE raw_text LIKE ? OR 
                      corrected_text LIKE ? OR 
                      subject LIKE ? OR 
                      document_number LIKE ? OR
                      file_path LIKE ?
            """, (q, q, q, q, q))
            like_ids = [row[0] for row in cursor.fetchall()]
            
            # Tüm benzersiz ID'leri birleştir
            all_ids = list(set(fts_ids + like_ids))
            
            if not all_ids:
                return []
                
            # 3. İlgili evrak datalarını çek
            placeholders = ','.join('?' for _ in all_ids)
            sql = f"""
                SELECT d.*,
                       (SELECT p.mahalle FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as p_mahalle,
                       (SELECT p.ada FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as ada,
                       (SELECT p.parsel FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as parsel,
                       (SELECT s.sokak FROM document_streets ds JOIN streets s ON ds.street_id = s.id WHERE ds.doc_id = d.id LIMIT 1) as s_sokak
                FROM documents d
                WHERE d.id IN ({placeholders})
                ORDER BY d.processed_date DESC
                LIMIT 100
            """
            
            cursor.execute(sql, all_ids)
            rows = cursor.fetchall()
            
            # Row objelerini dict'e çevir
            results = []
            for row in rows:
                d = dict(row)
                # YOL DÜZELTME: Dosya adı sadece isim olarak
                if d.get('file_path'):
                     d['file_name'] = Path(d['file_path']).name
                results.append(d)
                
            return results
        except Exception as e:
            logger.error(f"FTS5 Arama hatası: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_documents_by_parcel(self, ada: str, parsel: str = None,
                                 mahalle: str = None) -> List[Dict]:
        """Ada/Parsel/Mahalle'ye göre belge getir."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT d.*,
                       (SELECT p.mahalle FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as mahalle,
                       (SELECT p.ada FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as ada,
                       (SELECT p.parsel FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as parsel
                FROM documents d
                WHERE EXISTS (
                    SELECT 1 FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id 
                    WHERE dp.doc_id = d.id AND p.ada = ?
                )
            """
            params = [str(ada)]

            if parsel:
                query = query.replace("p.ada = ?", "p.ada = ? AND p.parsel = ?")
                params.append(str(parsel))
            if mahalle:
                query = query.replace("p.ada = ?", "p.ada = ? AND p.mahalle LIKE ?")
                params.append(f"%{mahalle}%")

            query += " ORDER BY d.processed_date DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Parsel sorgulama hatası: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_documents_by_street(self, sokak: str,
                                 mahalle: str = None) -> List[Dict]:
        """Sokak adına göre belge getir."""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT d.*, 
                       (SELECT s.mahalle FROM document_streets ds JOIN streets s ON ds.street_id = s.id WHERE ds.doc_id = d.id LIMIT 1) as mahalle,
                       (SELECT s.sokak FROM document_streets ds JOIN streets s ON ds.street_id = s.id WHERE ds.doc_id = d.id LIMIT 1) as sokak,
                       (SELECT ds.kapi_no FROM document_streets ds JOIN streets s ON ds.street_id = s.id WHERE ds.doc_id = d.id LIMIT 1) as kapi_no
                FROM documents d
                WHERE EXISTS (
                    SELECT 1 FROM document_streets ds JOIN streets s ON ds.street_id = s.id 
                    WHERE ds.doc_id = d.id AND s.sokak LIKE ?
                )
            """
            params = [f"%{sokak}%"]

            if mahalle:
                query = query.replace("s.sokak LIKE ?", "s.sokak LIKE ? AND s.mahalle LIKE ?")
                params.append(f"%{mahalle}%")

            query += " ORDER BY d.processed_date DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Sokak sorgulama hatası: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def search_advanced(self, ada: str = None, parsel: str = None,
                         mahalle: str = None, sokak: str = None,
                         doc_type: str = None, status: str = None,
                         date_from: str = None, date_to: str = None,
                         konu: str = None, free_text: str = None) -> List[Dict]:
        """
        Çok kriterli gelişmiş arama.
        Her zaman parcels ve streets tablolarını LEFT JOIN yapar.
        """
        conn = None
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Her zaman LEFT JOIN — tüm aramalarda Mahalle/Ada/Parsel/Sokak görünsün
            select = """SELECT d.*,
                    (SELECT p.mahalle FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as p_mahalle,
                    (SELECT p.ada FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as ada,
                    (SELECT p.parsel FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id LIMIT 1) as parsel,
                    (SELECT s.sokak FROM document_streets ds JOIN streets s ON ds.street_id = s.id WHERE ds.doc_id = d.id LIMIT 1) as s_sokak"""
            frm = """ FROM documents d """

            where_parts = []
            params = []

            if ada:
                where_parts.append("EXISTS (SELECT 1 FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id AND p.ada = ?)")
                params.append(str(ada))
            if parsel:
                where_parts.append("EXISTS (SELECT 1 FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id AND p.parsel = ?)")
                params.append(str(parsel))
            if sokak:
                where_parts.append("(d.sokak LIKE ? OR EXISTS (SELECT 1 FROM document_streets ds JOIN streets s ON ds.street_id = s.id WHERE ds.doc_id = d.id AND s.sokak LIKE ?))")
                params.append(f"%{sokak}%")
                params.append(f"%{sokak}%")

            if mahalle:
                where_parts.append(
                    "(d.corrected_text LIKE ? OR EXISTS (SELECT 1 FROM document_parcels dp JOIN parcels p ON dp.parcel_id = p.id WHERE dp.doc_id = d.id AND p.mahalle LIKE ?))")
                params.append(f"%{mahalle}%")
                params.append(f"%{mahalle}%")

            if doc_type:
                where_parts.append("d.doc_type = ?")
                params.append(doc_type)

            if status:
                where_parts.append("d.status = ?")
                params.append(status)

            if date_from:
                where_parts.append(
                    "(d.extracted_date >= ? OR d.processed_date >= ?)")
                params.append(date_from)
                params.append(date_from)

            if date_to:
                where_parts.append(
                    "(d.extracted_date <= ? OR d.processed_date <= ?)")
                params.append(date_to)
                params.append(date_to)

            if konu:
                where_parts.append("d.subject LIKE ?")
                params.append(f"%{konu}%")

            if free_text:
                where_parts.append(
                    "(d.corrected_text LIKE ? OR d.raw_text LIKE ?"
                    " OR d.sokak LIKE ? OR d.subject LIKE ?"
                    " OR d.document_number LIKE ?)")
                params.extend([f"%{free_text}%"] * 5)

            sql = select + frm
            if where_parts:
                sql += " WHERE " + " AND ".join(where_parts)
            sql += " ORDER BY d.processed_date DESC LIMIT 100"

            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Gelişmiş arama yürütme hatası: {e}")
            return []
        finally:
            if conn:
                conn.close()

    # ══════════════════════════════════════════════════════════════════════════
    #  İSTATİSTİKLER
    # ══════════════════════════════════════════════════════════════════════════
    def get_statistics(self) -> Dict[str, Any]:
        """Dashboard istatistikleri."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        stats = {}

        # Toplam belge sayısı
        cursor.execute("SELECT COUNT(*) FROM documents")
        stats["total_documents"] = cursor.fetchone()[0]

        # Duruma göre dağılım
        cursor.execute("""
            SELECT status, COUNT(*) FROM documents GROUP BY status
        """)
        stats["by_status"] = dict(cursor.fetchall())

        # Belge tipine göre dağılım
        cursor.execute("""
            SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type
        """)
        stats["by_type"] = dict(cursor.fetchall())

        # Ortalama OCR güven
        cursor.execute("SELECT AVG(ocr_confidence) FROM documents")
        avg = cursor.fetchone()[0]
        stats["avg_confidence"] = round(avg * 100, 1) if avg else 0

        # Toplam benzersiz parsel sayısı
        cursor.execute("SELECT COUNT(*) FROM parcels")
        stats["total_parcels"] = cursor.fetchone()[0]

        # Toplam sokak sayısı
        cursor.execute("SELECT COUNT(*) FROM streets")
        stats["total_streets"] = cursor.fetchone()[0]

        # Mahalle bazlı belge dağılımı (top 10)
        cursor.execute("""
            SELECT p.mahalle, COUNT(DISTINCT dp.doc_id) as cnt
            FROM parcels p
            JOIN document_parcels dp ON p.id = dp.parcel_id
            GROUP BY p.mahalle ORDER BY cnt DESC LIMIT 10
        """)
        stats["top_mahalle"] = [
            {"mahalle": r[0], "count": r[1]} for r in cursor.fetchall()]

        # Son 10 belge
        cursor.execute("""
            SELECT id, file_path, doc_type, processed_date, status
            FROM documents ORDER BY processed_date DESC LIMIT 10
        """)
        stats["recent_documents"] = [
            {"id": r[0], "file": Path(r[1]).name if r[1] else "?",
             "type": r[2], "date": r[3], "status": r[4]}
            for r in cursor.fetchall()]

        conn.close()
        return stats

    def get_all_parcels(self) -> List[Dict]:
        """Tüm benzersiz parselleri ve belge sayılarını getir."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT p.mahalle, p.ada, p.parsel, COUNT(dp.doc_id) as doc_count
            FROM parcels p
            LEFT JOIN document_parcels dp ON p.id = dp.parcel_id
            GROUP BY p.mahalle, p.ada, p.parsel
            ORDER BY p.ada, p.parsel
        """)

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def check_duplicate(self, file_path: str) -> Optional[Dict]:
        """Dosyanın daha önce işlenip işlenmediğini kontrol et."""
        if not file_path or not Path(file_path).exists():
            return None

        file_hash = hashlib.md5(Path(file_path).read_bytes()).hexdigest()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM documents WHERE file_hash=?", (file_hash,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Dashboard için istatistikleri getir."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {
            "total_documents": 0,  # DashboardTab expects total_documents
            "total_docs": 0,       # Keep for backward compat if needed
            "total_pages": 0,
            "last_docs": [],
            "doc_types": {},
            "neighborhoods": {},
            "by_status": {"approved": 0, "needs_review": 0, "failed": 0},
            "avg_confidence": 0,
            "total_parcels": 0
        }
        
        try:
            # Toplam belge
            cursor.execute("SELECT COUNT(*) FROM documents")
            cnt = cursor.fetchone()[0]
            stats["total_docs"] = cnt
            stats["total_documents"] = cnt
            
            # Status dağılımı
            cursor.execute("SELECT status, COUNT(*) FROM documents GROUP BY status")
            for status, count in cursor.fetchall():
                if status in stats["by_status"]:
                    stats["by_status"][status] = count
            
            # Ortalama Güven
            cursor.execute("SELECT AVG(ocr_confidence) FROM documents")
            avg = cursor.fetchone()[0]
            stats["avg_confidence"] = (avg * 100) if avg else 0
            
            # Toplam Parsel
            cursor.execute("SELECT COUNT(*) FROM parcels")
            stats["total_parcels"] = cursor.fetchone()[0]
            
            # ... (Existing logic for pages, last_docs, etc.)
            cursor.execute("SELECT SUM(page_number) FROM documents")
            total_pages = cursor.fetchone()[0]
            stats["total_pages"] = total_pages if total_pages else stats["total_docs"]

            # v8.4: Bugünün İstatistikleri (Dashboard metrics)
            import datetime
            today_str = datetime.date.today().strftime("%Y-%m-%d")
            
            # SQLite 'processed_date' formatı: YYYY-MM-DD HH:MM:SS
            # Bugün eklenenler
            cursor.execute(
                "SELECT COUNT(*) FROM documents WHERE date(processed_date) = ?", 
                (today_str,)
            )
            stats["today_scan_count"] = cursor.fetchone()[0]
            
            # Bugün Otomatik Onaylanan (High Confidence)
            cursor.execute(
                "SELECT COUNT(*) FROM documents WHERE date(processed_date) = ? AND status='approved'", 
                (today_str,)
            )
            stats["today_approved_count"] = cursor.fetchone()[0]
            
            # Bugün Manuel İnceleme
            cursor.execute(
                "SELECT COUNT(*) FROM documents WHERE date(processed_date) = ? AND status='needs_review'", 
                (today_str,)
            )
            stats["today_manual_count"] = cursor.fetchone()[0]
            
            # Başarı Oranı (Bugün)
            if stats["today_scan_count"] > 0:
                stats["today_success_rate"] = int((stats["today_approved_count"] / stats["today_scan_count"]) * 100)
            else:
                stats["today_success_rate"] = 0
            
        except Exception as e:
            logger.error(f"İstatistik hatası: {e}")
        finally:
            conn.close()
            
        return stats

    # ══════════════════════════════════════════════════════════════════════════
    #  GÜVENLİK & KİMLİK DOĞRULAMA (v7.0)
    # ══════════════════════════════════════════════════════════════════════════
    def get_or_create_admin(self):
        """Varsayılan admin hesabını oluşturur."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username='admin'")
        if not cursor.fetchone():
            pwd_hash = hashlib.sha256("admin123".encode()).hexdigest()
            cursor.execute('''INSERT INTO users (username, password_hash, role) 
                              VALUES (?, ?, 'admin')''', ('admin', pwd_hash))
            
            pwd2 = hashlib.sha256("personel123".encode()).hexdigest()
            cursor.execute('''INSERT INTO users (username, password_hash, role) 
                              VALUES (?, ?, 'personel')''', ('personel', pwd2))
            conn.commit()
        conn.close()

    def verify_user(self, username, password) -> Optional[Dict]:
        """Kullanıcı girişi doğrulaması (RBAC)."""
        self.get_or_create_admin() # Kurulumda yetkili hesapların olduğundan emin ol
        pwd_hash = hashlib.sha256(password.encode()).hexdigest()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role FROM users WHERE username=? AND password_hash=?", (username, pwd_hash))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def log_audit(self, user_id, username, action, details=""):
        """Sistem işlemlerini işlem kütüğüne (audit log) kaydeder."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO audit_logs (user_id, username, action, details)
                VALUES (?, ?, ?, ?)
            ''', (user_id, username, action, details))
            conn.commit()
        except Exception as e:
            logger.error(f"Audit log hatası: {e}")
        finally:
            conn.close()
