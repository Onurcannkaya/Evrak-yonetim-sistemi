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
from utils import extract_text_from_file

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

# ─────── SİVAS MAHALLE LİSTESİ (Fuzzy Matching İçin) ───────
SIVAS_MAHALLELER = [
    "AKDEĞIRMEN", "ALIBABA", "ALTUNTABAK", "AŞAĞI", "BAĞLAR",
    "BARBAROS", "BEŞTEPE", "BÜYÜKMINIÇ", "CEVİZLİDERE", "ÇAYBOYU",
    "ÇİFTLİK", "DEMİRÇELİK", "DİKİLİTAŞ", "EMEK", "ESKİKALE",
    "FATİH", "FERHATBOSTANı", "GEYİKTEPE", "GÜLTEPE", "GÜNBULDU",
    "GÜNEY", "HACIİLYAS", "HAFİK", "HANLI", "HİSAR", "HÜRRİYET",
    "İNÖNÜ", "İSTASYON", "KADIBURHANETTİN", "KALECİK", "KANDEMİR",
    "KARDEŞLER", "KARŞIYAKa", "KAYABEY", "KEPEKLİ", "KILIÇASLAN",
    "KIZILIRMAK", "KONAK", "KOYULHISAR", "KÜÇÜKMINIÇ", "MADEN",
    "MECİDİYE", "MEVLANA", "MİMAR SİNAN", "NUMUNE", "PAŞABEY",
    "PULUR", "SELÇUK", "SULARBAŞI", "SUŞEHRI", "ŞÜKRİYE",
    "TOKAT", "TUZLUGÖL", "ULAŞ", "YAPITEPE", "YENİKENT",
    "YENİŞEHİR", "YEŞİLYURT", "YILDIZ", "YUKARIMİNİÇ", "ZARA",
    "GEMEREK", "GÜRÜN", "İMRANLI", "KANGaL", "ŞARKIŞLA",
    "DİVRİĞİ", "DOĞANŞAR", "AKINCI", "GÖLOVA", "ALTINYAYLA",
]

def fuzzy_match_mahalle(raw_mahalle: str, threshold: float = 0.6) -> str:
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
def get_api_key():
    config_path = "config.json"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                key = config.get("google_api_key", "")
                if key and key != "DUMMY_KEY_FOR_TEST":
                   return key
        except Exception:
            pass
    return os.environ.get("GEMINI_API_KEY", "")

class DocumentAnalyzer:
    def __init__(self):
        self.api_key = get_api_key()
        if not self.api_key:
            raise ValueError("Google Gemini API anahtarı bulunamadı! 'config.json' içine 'google_api_key' ekleyin.")
        
        # Initialize the new genai client
        self.client = genai.Client(api_key=self.api_key)
        
        # We use a vision-capable model. "gemini-1.5-flash" or "gemini-2.5-flash" are recommended
        self.model_name = "gemini-2.5-flash"
        
        mahalle_str = ", ".join(SIVAS_MAHALLELER)
        self.system_instruction = f"""
        Sen uzman bir veri çıkarma asistanısın. Sivas Belediyesi'ne ait eski daktilo ve el yazısı evraklarını analiz ediyorsun.
        Görevin: Verilen belge görüntüsünden mahalle, ada, parsel ve tarih bilgilerini çıkarmak. Eğer promptta senden ham metin de istenmişse (raw_text), o zaman belgedeki tüm okunaklı metni de çıkar.

        REFERANS BİLGİ (OKUMAYI İYİLEŞTİRMEK İÇİN):
        Daktilo belgelerinde harfler silik olabilir veya mühürler yüzünden harfler karışmış olabilir (Örn: SARKISLA, KANDEM1R). 
        Eğer bir mahalle okuyorsan ve harfler eksik/hatalı görünüyorsa, aşağıdaki Sivas Mahalle Listesi'ni referans alarak en yakın mantıklı sonucu üret:
        [SİVAS MAHALLE LİSTESİ]: {mahalle_str}

        KURALLAR:
        - Yanıtını SADECE geçerli bir JSON formatında döndür.
        - Sadece istenen alanları doldur.
        - Bulamadığın alanları veya emin olamadığın şüpheli ("-", "Okunamadı" gibi) verileri tamamen boş bırak ("").
        """
        
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
            ext = os.path.splitext(image_path)[1]
            safe_filename = f"gemini_upload_{uuid.uuid4().hex}{ext}"
            temp_path = os.path.join(tempfile.gettempdir(), safe_filename)
            shutil.copy2(image_path, temp_path)

            sample_file = self.client.files.upload(file=temp_path, config={'display_name': 'Document to analyze'})
            # Eğer PyMuPDF metin bulamadıysa (ör. JPEG), AI'dan iste
            if not raw_text:
                prompt = "Bu belgeyi analiz et ve mahalle, ada, parsel, tarih ve ham metni (raw_text) JSON olarak çıkar."
                schema_to_use = DocumentResponseWithText
            else:
                prompt = "Bu belgeyi analiz et ve mahalle, ada, parsel, tarih bilgilerini JSON olarak çıkar."
                schema_to_use = DocumentResponse
            
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[sample_file, prompt],
                config=types.GenerateContentConfig(
                    system_instruction=self.system_instruction,
                    temperature=0.4,
                    response_mime_type="application/json",
                    response_schema=schema_to_use,
                    max_output_tokens=65536,
                    safety_settings=[
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
            
            try:
                data = json.loads(result_text)
                
                # Eğer Gemini raw_text döndürdüyse onu kullan
                ai_raw_text = data.get("raw_text", "")
                final_text = ai_raw_text if ai_raw_text else raw_text
                
                extracted = {
                    "mahalle": data.get("mahalle", ""),
                    "ada": data.get("ada", ""),
                    "parsel": data.get("parsel", ""),
                    "tarih": data.get("tarih", ""),
                    "raw_text": final_text
                }
            except json.JSONDecodeError:
                import re
                mahalle = ""
                ada = ""
                parsel = ""
                tarih = ""
                ai_raw_text = ""
                
                m = re.search(r'"mahalle"\s*:\s*"([^"]*)"', result_text, re.IGNORECASE)
                if m: mahalle = m.group(1)
                
                m = re.search(r'"ada"\s*:\s*"([^"]*)"', result_text, re.IGNORECASE)
                if m: ada = m.group(1)
                
                m = re.search(r'"parsel"\s*:\s*"([^"]*)"', result_text, re.IGNORECASE)
                if m: parsel = m.group(1)
                
                m = re.search(r'"tarih"\s*:\s*"([^"]*)"', result_text, re.IGNORECASE)
                if m: tarih = m.group(1)

                rt = re.search(r'"raw_text"\s*:\s*"([^"]*)"', result_text, re.IGNORECASE | re.DOTALL)
                if rt: ai_raw_text = rt.group(1)
                
                final_text = ai_raw_text if ai_raw_text else raw_text
                
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
