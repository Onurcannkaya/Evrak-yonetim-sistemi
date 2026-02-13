"""
Sivas Belediyesi - Akıllı Evrak Yönetim Sistemi
REST API Modülü (FastAPI)

Kent Rehberi (GIS) ile entegrasyon için API uçları
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from pathlib import Path
import logging
import json
from datetime import datetime

from document_processor import DocumentProcessor

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI uygulaması
app = FastAPI(
    title="Sivas Belediyesi Akıllı Evrak Sistemi API",
    description="GIS entegrasyonu için belge yönetim API'si",
    version="1.0.0"
)

# CORS ayarları (belediye intranet'i için)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Prod'da sadece GIS sunucusu IP'si olmalı
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Belge işleyici
processor = DocumentProcessor(archive_directory="./evrak_arsiv")


# Pydantic modelleri
class DocumentData(BaseModel):
    """Belge verisi modeli"""
    mahalle: Optional[str] = None
    ada: Optional[str] = None
    parsel: Optional[str] = None
    karar_no: Optional[str] = None
    tarih: Optional[str] = None
    doc_type: Optional[str] = None
    ocr_confidence: Optional[float] = None
    processed_date: Optional[str] = None


class DocumentSearchRequest(BaseModel):
    """Belge arama isteği"""
    mahalle: Optional[str] = Field(None, description="Mahalle adı")
    ada: Optional[str] = Field(None, description="Ada numarası")
    parsel: Optional[str] = Field(None, description="Parsel numarası")
    karar_no: Optional[str] = Field(None, description="Karar numarası")


class DocumentUploadResponse(BaseModel):
    """Belge yükleme yanıtı"""
    success: bool
    message: str
    file_path: Optional[str] = None
    data: Optional[DocumentData] = None


class DocumentSearchResponse(BaseModel):
    """Belge arama yanıtı"""
    success: bool
    count: int
    documents: List[Dict]


# API Uçları

@app.get("/")
async def root():
    """API bilgisi"""
    return {
        "service": "Sivas Belediyesi Akıllı Evrak Sistemi",
        "version": "1.0.0",
        "status": "active",
        "endpoints": {
            "upload": "/api/upload",
            "search": "/api/search",
            "get_document": "/api/document/{file_id}",
            "health": "/api/health"
        }
    }


@app.get("/api/health")
async def health_check():
    """Sistem sağlık kontrolü"""
    archive_path = Path(processor.archive_dir)
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "archive_path": str(archive_path.absolute()),
        "archive_exists": archive_path.exists()
    }


@app.post("/api/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    doc_type: str = Query("ENCUMEN", description="Belge türü (ENCUMEN, DILEKCE, vb.)")
):
    """
    Belge yükleme ve işleme
    
    GIS'den gelen taranmış belgeyi işler ve verileri çıkarır.
    
    Args:
        file: Yüklenen görüntü dosyası (PNG, JPG, TIFF)
        doc_type: Belge türü
        
    Returns:
        İşlem sonucu ve çıkarılan veriler
    """
    logger.info(f"Belge yükleniyor: {file.filename}")
    
    # Dosya türü kontrolü
    allowed_extensions = {'.png', '.jpg', '.jpeg', '.tiff', '.tif'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Desteklenmeyen dosya türü. İzin verilenler: {allowed_extensions}"
        )
    
    try:
        # Geçici dosya kaydet
        temp_path = f"./temp_upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
        
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Belgeyi işle
        result = processor.process_document(
            image_path=temp_path, 
            doc_type=doc_type
        )
        
        # Geçici dosyayı temizle
        Path(temp_path).unlink(missing_ok=True)
        
        if result['success']:
            # Yeni document_processor.py formatına uygun veri çıkarımı
            data_dict = result.get('data', {})
            
            return DocumentUploadResponse(
                success=True,
                message=result.get('message', 'İşlem başarılı'),
                file_path=data_dict.get('image_path', temp_path),
                data=DocumentData(
                    mahalle=data_dict.get('mahalle'),
                    ada=data_dict.get('ada'),
                    parsel=data_dict.get('parsel'),
                    karar_no=data_dict.get('belge_no'),
                    tarih=data_dict.get('tarih'),
                    doc_type=data_dict.get('doc_type', doc_type),
                    ocr_confidence=data_dict.get('ocr_details', {}).get('easyocr_conf'),
                    processed_date=datetime.now().isoformat()
                )
            )
        else:
            raise HTTPException(status_code=500, detail=result.get('message', 'İşlem başarısız'))
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Yükleme hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=f"İşlem hatası: {str(e)}")


@app.post("/api/search", response_model=DocumentSearchResponse)
async def search_documents(search_params: DocumentSearchRequest):
    """
    Belge arama - GIS'den ada/parsel ile sorgu
    
    Kent Rehberi'nden ada/parsel numarası geldiğinde ilgili belgeleri bulur.
    
    Args:
        search_params: Arama kriterleri
        
    Returns:
        Bulunan belgeler listesi
    """
    logger.info(f"Arama yapılıyor: {search_params.dict()}")
    
    try:
        found_documents = []
        base_path = Path(processor.archive_dir)
        
        # Tüm metadata dosyalarını tara
        for json_file in base_path.rglob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Arama kriterlerini kontrol et
                match = True
                
                if search_params.ada and metadata.get('ada') != search_params.ada:
                    match = False
                if search_params.parsel and metadata.get('parsel') != search_params.parsel:
                    match = False
                if search_params.mahalle and metadata.get('mahalle', '').upper() != search_params.mahalle.upper():
                    match = False
                if search_params.karar_no and metadata.get('karar_no') != search_params.karar_no:
                    match = False
                
                if match:
                    # PDF dosya yolunu bul
                    pdf_file = json_file.with_suffix('.pdf')
                    
                    found_documents.append({
                        'metadata': metadata,
                        'pdf_path': str(pdf_file),
                        'pdf_exists': pdf_file.exists(),
                        'metadata_path': str(json_file)
                    })
            
            except Exception as e:
                logger.warning(f"Metadata okuma hatası: {json_file} - {str(e)}")
                continue
        
        return DocumentSearchResponse(
            success=True,
            count=len(found_documents),
            documents=found_documents
        )
        
    except Exception as e:
        logger.error(f"Arama hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Arama hatası: {str(e)}")


@app.get("/api/document/by-parsel")
async def get_document_by_parsel(
    ada: str = Query(..., description="Ada numarası"),
    parsel: str = Query(..., description="Parsel numarası"),
    mahalle: Optional[str] = Query(None, description="Mahalle adı (opsiyonel)")
):
    """
    Ada/Parsel ile belge getirme - GIS için optimize edilmiş
    
    Kent Rehberi'nden direkt ada/parsel numarası ile sorgu.
    
    Args:
        ada: Ada numarası
        parsel: Parsel numarası
        mahalle: Mahalle adı (opsiyonel, daha hızlı arama için)
        
    Returns:
        Belge dosyası veya bulunamadı hatası
    """
    logger.info(f"Belge getiriliyor - Ada: {ada}, Parsel: {parsel}, Mahalle: {mahalle}")
    
    try:
        # Hızlı arama için mahalle verilmişse direkt klasöre git
        base_path = Path(processor.archive_dir)
        if mahalle:
            search_path = base_path / mahalle.upper() / f"ADA_{ada}"
        else:
            search_path = base_path
        
        # Klasörde JSON ara
        matching_files = []
        for json_file in search_path.rglob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                if metadata.get('ada') == ada and metadata.get('parsel') == parsel:
                    matching_files.append((json_file, metadata))
            
            except Exception as e:
                logger.warning(f"Metadata okuma hatası: {str(e)}")
                continue
        
        if not matching_files:
            raise HTTPException(
                status_code=404,
                detail=f"Ada {ada}, Parsel {parsel} için belge bulunamadı"
            )
        
        # En güncel dosyayı döndür (processed_date'e göre)
        matching_files.sort(
            key=lambda x: x[1].get('processed_date', ''),
            reverse=True
        )
        
        json_file, metadata = matching_files[0]
        pdf_file = json_file.with_suffix('.pdf')
        
        if pdf_file.exists():
            return FileResponse(
                path=pdf_file,
                media_type='application/pdf',
                filename=pdf_file.name
            )
        else:
            # PDF yoksa metadata döndür
            return JSONResponse(
                status_code=200,
                content={
                    "message": "PDF dosyası henüz oluşturulmamış, metadata mevcut",
                    "metadata": metadata,
                    "expected_pdf_path": str(pdf_file)
                }
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Belge getirme hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Sistem hatası: {str(e)}")


@app.get("/api/document/{file_id}")
async def get_document_by_id(file_id: str):
    """
    Dosya ID ile belge getirme
    
    Args:
        file_id: Dosya adı (örn: 32_2_ENCUMEN_20230312)
        
    Returns:
        PDF dosyası
    """
    logger.info(f"Belge getiriliyor - ID: {file_id}")
    
    # Tüm arşivi tara
    base_path = Path(processor.archive_dir)
    for pdf_file in base_path.rglob("*.pdf"):
        if pdf_file.stem == file_id or file_id in pdf_file.name:
            return FileResponse(
                path=pdf_file,
                media_type='application/pdf',
                filename=pdf_file.name
            )
    
    raise HTTPException(
        status_code=404,
        detail=f"Dosya bulunamadı: {file_id}"
    )


@app.get("/api/statistics")
async def get_statistics():
    """
    Sistem istatistikleri
    
    Returns:
        Arşiv istatistikleri (belge sayısı, mahalle sayısı, vb.)
    """
    try:
        base_path = Path(processor.archive_dir)
        
        total_pdfs = len(list(base_path.rglob("*.pdf")))
        total_metadata = len(list(base_path.rglob("*.json")))
        
        # Mahalle sayısı
        mahalleler = [d.name for d in base_path.iterdir() if d.is_dir()]
        
        # Ada sayıları
        ada_dirs = list(base_path.rglob("ADA_*"))
        
        return {
            "total_documents": total_pdfs,
            "total_metadata": total_metadata,
            "mahalle_count": len(mahalleler),
            "mahalleler": mahalleler,
            "ada_count": len(ada_dirs),
            "archive_path": str(base_path.absolute()),
            "last_updated": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"İstatistik hatası: {str(e)}")
        raise HTTPException(status_code=500, detail=f"İstatistik hatası: {str(e)}")


# Uvicorn ile başlatma
if __name__ == "__main__":
    import uvicorn
    
    # Belediye intranet'inde çalışacak şekilde yapılandırma
    uvicorn.run(
        app,
        host="0.0.0.0",  # Tüm ağ arayüzlerinden erişim
        port=8080,  # Belediye standardına göre ayarlanabilir
        log_level="info"
    )
