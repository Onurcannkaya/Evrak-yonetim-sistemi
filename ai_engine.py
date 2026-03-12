import os
import json
import shutil
import logging
import uuid
import tempfile
from google import genai
from google.genai import types
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import difflib
from utils import extract_text_from_file, get_base_dir

class DocumentResponse(BaseModel):
    mahalle: str = Field(description="Mahalle adı. Yoksa boş bırak.")
    ada: str = Field(description="Ada Numarası. Yoksa boş bırak.")
    parsel: str = Field(description="Parsel Numarası. Yoksa boş bırak.")
    tarih: str = Field(description="Tarih veya yıl. Yoksa boş bırak.")

class DocumentResponseWithText(BaseModel):
    mahalle: str = Field(description="Mahalle adı. Yoksa boş bırak.")
    ada: str = Field(description="Ada Numarası. Yoksa boş bırak.")
    parsel: str = Field(description="Parsel Numarası. Yoksa boş bırak.")
    tarih: str = Field(description="Tarih veya yıl. Yoksa boş bırak.")
    raw_text: str = Field(description="Belgedeki tüm yazılı metinler.")

# ─────── TABLO BELGELERİ İÇİN MODELLER ───────
class TableRow(BaseModel):
    sira: str = Field(default="", description="Sıra veya satır numarası")
    mahalle: str = Field(default="", description="Mahalle adı")
    ada: str = Field(default="", description="Ada numarası")
    parsel: str = Field(default="", description="Parsel numarası")
    nitelik: str = Field(default="", description="Taşınmaz niteliği (Tarla, Çayır vb.)")
    tc_kimlik: str = Field(default="", description="TC Kimlik numarası")
    ad_soyad: str = Field(default="", description="Ad Soyad")
    baba_adi: str = Field(default="", description="Baba adı")
    adres: str = Field(default="", description="Tebligat adresi")

class TableDocumentResponse(BaseModel):
    table_title: str = Field(default="", description="Tablonun başlığı veya belge adı")
    rows: List[TableRow] = Field(default_factory=list, description="Tablodaki tüm satırlar")

# ─────── SİVAS MAHALLE LİSTESİ (Fuzzy Matching İçin) ───────
SIVAS_MAHALLELER = [
    "AKDEĞIRMEN", "ALIBABA", "ALTUNTABAK", "AŞAĞI", "BAĞLAR",
    "BARBAROS", "BEŞTEPE", "BÜYÜKMINIÇ", "CEVİZLİDERE", "ÇAYBOYU",
    "ÇİFTLİK", "DEMİRÇELİK", "DİKİLİTAŞ", "EMEK", "ESKİKALE",
    "FATİH", "FERHATBOSTANı", "GEYİKTEPE", "GÜLTEPE", "GÜNBULDU",
    "GÜNEY", "HACIİLYAS", "HAFİK", "HANLI", "HİSAR", "HÜRRİYET",
    "İNÖNÜ", "İSTASYON", "KADIBURHANETTİN", "KALECİK", "KANDEMİR",
    "KARDEŞLER", "KARŞIYAKA", "KAYABEY", "KEPEKLİ", "KILIÇASLAN",
    "KIZILIRMAK", "KONAK", "KOYULHISAR", "KÜÇÜKMINIÇ", "MADEN",
    "MECİDİYE", "MEVLANA", "MİMAR SİNAN", "NUMUNE", "PAŞABEY",
    "PULUR", "SELÇUK", "SULARBAŞI", "SUŞEHRI", "ŞÜKRİYE",
    "TOKAT", "TUZLUGÖL", "ULAŞ", "YAPITEPE", "YENİKENT",
    "YENİŞEHİR", "YEŞİLYURT", "YILDIZ", "YUKARIMİNİÇ", "ZARA",
    "GEMEREK", "GÜRÜN", "İMRANLI", "KANGAL", "ŞARKIŞLA",
    "DİVRİĞİ", "DOĞANŞAR", "AKINCI", "GÖLOVA", "ALTINYAYLA",
]

def fuzzy_match_mahalle(raw_mahalle: str, threshold: float = 0.75) -> str:
    """Sivas mahalle listesiyle fuzzy matching uygular."""
    if not raw_mahalle or not raw_mahalle.strip():
        return raw_mahalle
    
    upper = raw_mahalle.strip().upper()
    # Tam eşleşme kontrolü
    for m in SIVAS_MAHALLELER:
        if m.upper() == upper:
            return m
    
    # Fuzzy matching
    matches = difflib.get_close_matches(upper, [m.upper() for m in SIVAS_MAHALLELER], n=1, cutoff=threshold)
    if matches:
        idx = [m.upper() for m in SIVAS_MAHALLELER].index(matches[0])
        return SIVAS_MAHALLELER[idx]
    
    return raw_mahalle

def post_process_local(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Gemini'den gelen sonuçları yerel olarak düzeltir.
    - Mahalle fuzzy matching
    - Ada/Parsel temizleme (sadece rakam bırakma)
    """
    if not result:
        return result
    
    # Mahalle düzeltme
    mahalle = result.get("mahalle", "")
    if mahalle:
        result["mahalle"] = fuzzy_match_mahalle(mahalle)
    
    # Ada ve Parsel — sadece ilk sayısal değeri al
    for key in ("ada", "parsel"):
        val = result.get(key, "")
        if val:
            digits = "".join(c for c in str(val) if c.isdigit())
            if digits:
                result[key] = digits
    
    return result

# Configure Gemini with the API key from config.json or environment variable
def _load_config():
    """Config dosyasını yükle. Önce exe dizinini, sonra _internal dizinini arar."""
    from utils import get_resource_dir
    # 1. Exe'nin yanında kullanıcının koyduğu config.json (öncelikli)
    for base in [get_base_dir(), get_resource_dir()]:
        config_path = os.path.join(base, "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                continue
    return {}

def get_api_key():
    config = _load_config()
    key = config.get("google_api_key", "")
    if key and key != "DUMMY_KEY_FOR_TEST":
        return key
    return os.environ.get("GEMINI_API_KEY", "")

class DocumentAnalyzer:
    def __init__(self):
        self.api_key = get_api_key()
        if not self.api_key:
            raise ValueError("Google Gemini API anahtarı bulunamadı! 'config.json' içine 'google_api_key' ekleyin.")
        
        # Initialize the new genai client
        self.client = genai.Client(api_key=self.api_key)
        
        # Model: gemini-2.0-flash (hızlı), config.json'dan da değiştirilebilir
        config = _load_config()
        self.model_name = config.get("model_name", "gemini-2.0-flash")
        
        mahalle_str = ", ".join(SIVAS_MAHALLELER)
        self.system_instruction = f"""
        Sen uzman bir veri çıkarma asistanısın. Sivas Belediyesi'ne ait eski daktilo ve el yazısı evraklarını analiz ediyorsun.
        Görevin: Verilen belge görüntüsünden mahalle, ada, parsel ve tarih bilgilerini çıkarmak. Eğer promptta senden ham metin de istenmişse (raw_text), o zaman belgedeki tüm okunaklı metni de tam bir doğrulukla (kelime atlamadan) çıkar.

        REFERANS BİLGİ (OKUMAYI İYİLEŞTİRMEK İÇİN):
        1. Daktilo belgelerinde harfler silik olabilir veya mühürler yüzünden harfler karışmış olabilir (Örn: 1 yerine l, 0 yerine O, SARKISLA veya KANDEM1R gibi hatalar). 
        2. Eğer bir mahalle okuyorsan ve harfler eksik/hatalı görünüyorsa, aşağıdaki Sivas Mahalle Listesi'ni referans alarak en yakın mantıklı sonucu üret:
        [SİVAS MAHALLE LİSTESİ]: {mahalle_str}
        3. Sayısal değerler olan ADA ve PARSEL alanları kritiktir. Bu değerlerin yanında sembol veya işaretler varsa (Örn: 123/A, 45-C) sadece asıl sayıyı al. Sayıları belirlerken daktilo hatalarına özellikle dikkat et.

        KURALLAR:
        - Yanıtını SADECE geçerli bir JSON formatında döndür.
        - Sadece istenen alanları doldur.
        - Bulamadığın alanları veya kesin emin olamadığın ("-", "Okunamadı" gibi) verileri tamamen boş bırak ("").
        """

        self.table_system_instruction = f"""
        Sen uzman bir tablo veri çıkarma asistanısın. Sivas Belediyesi'ne ait resmi belgelerdeki tabloları analiz ediyorsun.
        Görevin: Verilen belge görüntüsündeki tablodaki TÜM satırları tek tek okuyup JSON formatında döndürmek.

        REFERANS BİLGİ:
        [SİVAS MAHALLE LİSTESİ]: {mahalle_str}

        KURALLAR:
        - Tablodaki HER satırı ayrı bir kayıt olarak çıkar.
        - Hiçbir satırı atlama.
        - Sütun başlıklarını veri olarak ekleme.
        - Okunamayan veya belirsiz değerleri boş bırak ("").
        - Yanıtını SADECE geçerli bir JSON formatında döndür.
        """

    def _get_safety_settings(self):
        """Ortak güvenlik ayarları."""
        return [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            ),
        ]

    def _upload_temp_file(self, image_path: str):
        """Dosyayı güvenli isimle geçici klasöre kopyalayıp Gemini'ye yükler."""
        ext = os.path.splitext(image_path)[1]
        safe_filename = f"gemini_upload_{uuid.uuid4().hex}{ext}"
        temp_path = os.path.join(tempfile.gettempdir(), safe_filename)
        shutil.copy2(image_path, temp_path)
        sample_file = self.client.files.upload(
            file=temp_path, 
            config={'display_name': 'Document to analyze'}
        )
        return sample_file, temp_path

    def analyze_document(self, image_path: str) -> Dict[str, Any]:
        """
        Gemini Odaklı Hibrit DUAL-CHECK yaklaşım:
        1. Ham metni PyMuPDF veya OCR ile doğrudan al
        2. Gemini ile analizi tamamla
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Görsel bulunamadı: {image_path}")
        
        # 1. Ham metni doğrudan PyMuPDF ile çıkar (AI değil → kesme yok)
        raw_text = extract_text_from_file(image_path)
            
        temp_path = None
        try:
            sample_file, temp_path = self._upload_temp_file(image_path)

            # Her zaman ham metni (raw_text) Gemini'den de isteyelim, PyMuPDF yanıltabiliyor
            prompt = "Bu belgeyi analiz et ve mahalle, ada, parsel, tarih ve ham metni (raw_text) JSON olarak çıkar."
            schema_to_use = DocumentResponseWithText
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[sample_file, prompt],
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.4,
                    response_mime_type="application/json",
                    response_schema=schema_to_use,
                    max_output_tokens=65536,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    safety_settings=self._get_safety_settings()
                )
            )
            
            try:
                self.client.files.delete(name=sample_file.name)
            except Exception:
                pass
            
            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
                
            result_text = result_text.strip()
            
            # --- Robust JSON parsing for large responses ---
            import re
            data = None
            try:
                data = json.loads(result_text)
            except json.JSONDecodeError:
                pass
            
            if data and isinstance(data, dict):
                ai_raw_text = data.get("raw_text", "")
                final_text = ai_raw_text if len(ai_raw_text) > len(raw_text.strip()) else raw_text
                
                extracted = {
                    "mahalle": data.get("mahalle", ""),
                    "ada": data.get("ada", ""),
                    "parsel": data.get("parsel", ""),
                    "tarih": data.get("tarih", ""),
                    "raw_text": final_text
                }
            else:
                # JSON parse failed (large raw_text with special chars)
                # Extract structured fields with regex
                mahalle = ""
                ada = ""
                parsel = ""
                tarih = ""
                ai_raw_text = ""
                
                for field in ["mahalle", "ada", "parsel", "tarih"]:
                    m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', result_text, re.IGNORECASE)
                    if m:
                        locals()[field]  # just to verify
                        if field == "mahalle": mahalle = m.group(1)
                        elif field == "ada": ada = m.group(1)
                        elif field == "parsel": parsel = m.group(1)
                        elif field == "tarih": tarih = m.group(1)
                
                # Extract raw_text — it can be very large with embedded quotes
                # Find "raw_text": " and read until the end of the JSON
                rt_match = re.search(r'"raw_text"\s*:\s*"', result_text)
                if rt_match:
                    start_pos = rt_match.end()
                    # Find the closing " by scanning from end of string
                    # The JSON ends with "} so raw_text value ends just before "}
                    end_pos = result_text.rfind('"')
                    if end_pos > start_pos:
                        ai_raw_text = result_text[start_pos:end_pos]
                        # Unescape basic JSON escapes
                        ai_raw_text = ai_raw_text.replace('\\n', '\n').replace('\\"', '"').replace('\\\\', '\\')
                
                final_text = ai_raw_text if len(ai_raw_text) > len(raw_text.strip()) else raw_text
                
                extracted = {
                    "mahalle": mahalle,
                    "ada": ada,
                    "parsel": parsel,
                    "tarih": tarih,
                    "raw_text": final_text
                }

            # Final Anlamsal Onarım (Sivas Listeleri + Noktalama Temizliği)
            return post_process_local(extracted)
            
        except Exception as e:
            return {
                "mahalle": "",
                "ada": "",
                "parsel": "",
                "tarih": "",
                "raw_text": "",
                "error": str(e)
            }
        finally:
            # Geçici oluşturduğumuz kopyayı siliyoruz
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

    def analyze_table_document(self, image_path: str) -> Dict[str, Any]:
        """
        Tablo formatındaki belgeleri analiz eder.
        ÇEDAŞ listesi, kadastro tabloları gibi çok satırlı belgeler için.
        
        Returns:
            {
                "_is_table": True,
                "_table_rows": [{"mahalle": ..., "ada": ..., ...}, ...],
                "table_title": "...",
                "row_count": N,
                "mahalle": "İlk satırın mahallesi",
                "ada": "İlk satırın adası",
                ...
            }
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Görsel bulunamadı: {image_path}")

        temp_path = None
        try:
            sample_file, temp_path = self._upload_temp_file(image_path)

            prompt = (
                "Bu belge bir tablo içeriyor. Tablodaki TÜM satırları oku. "
                "Her satır için: mahalle, ada, parsel, nitelik (taşınmaz niteliği), "
                "tc_kimlik, ad_soyad, baba_adi, adres bilgilerini çıkar. "
                "Sütun başlıklarını veri olarak ekleme. Sıra numarasını da ekle."
            )

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[sample_file, prompt],
                config=types.GenerateContentConfig(
                    system_instruction=self.table_system_instruction,
                    temperature=0.2,
                    response_mime_type="application/json",
                    response_schema=TableDocumentResponse,
                    max_output_tokens=65536,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                    safety_settings=self._get_safety_settings()
                )
            )

            try:
                self.client.files.delete(name=sample_file.name)
            except Exception:
                pass

            result_text = response.text.strip()
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]
            result_text = result_text.strip()

            data = json.loads(result_text)
            rows = data.get("rows", [])

            # Her satıra post-process uygula
            processed_rows = []
            for row in rows:
                if isinstance(row, dict):
                    # Mahalle fuzzy matching
                    if row.get("mahalle"):
                        row["mahalle"] = fuzzy_match_mahalle(row["mahalle"])
                    # Ada/Parsel temizleme
                    for key in ("ada", "parsel"):
                        val = row.get(key, "")
                        if val:
                            digits = "".join(c for c in str(val) if c.isdigit())
                            if digits:
                                row[key] = digits
                    processed_rows.append(row)

            # İlk satırın verilerini ana sonuç olarak kullan
            first = processed_rows[0] if processed_rows else {}
            
            return {
                "_is_table": True,
                "_table_rows": processed_rows,
                "table_title": data.get("table_title", ""),
                "row_count": len(processed_rows),
                "mahalle": first.get("mahalle", ""),
                "ada": first.get("ada", ""),
                "parsel": first.get("parsel", ""),
                "tarih": "",
                "raw_text": f"Tablo belgesi: {len(processed_rows)} satır tespit edildi.",
            }

        except Exception as e:
            return {
                "_is_table": True,
                "_table_rows": [],
                "mahalle": "",
                "ada": "",
                "parsel": "",
                "tarih": "",
                "raw_text": "",
                "error": str(e)
            }
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

