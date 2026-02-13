# Sivas Belediyesi Akıllı Evrak Yönetim Sistemi
# Docker Container Yapılandırması
# *** TAM BAĞIMSIZ - Tesseract OCR gerektirmez ***

FROM python:3.10-slim

# Maintainer bilgisi
LABEL maintainer="Sivas Belediyesi Bilgi İşlem"
LABEL description="Akıllı Evrak Yönetim Sistemi - EasyOCR ile tam bağımsız"

# Çalışma dizini
WORKDIR /app

# Sistem bağımlılıkları (sadece OpenCV ve PDF için gerekli)
RUN apt-get update && apt-get install -y \
    libopencv-dev \
    libgl1-mesa-glx \
    libglib2.0-0 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Python bağımlılıkları
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# EasyOCR modellerini önceden indir (opsiyonel - build süresini uzatır ama ilk çalıştırmayı hızlandırır)
# RUN python -c "import easyocr; reader = easyocr.Reader(['tr', 'en'], gpu=False)"

# Uygulama dosyalarını kopyala
COPY document_processor.py .
COPY api_server.py .

# Arşiv dizini oluştur
RUN mkdir -p /app/evrak_arsiv

# Port
EXPOSE 8080

# Sağlık kontrolü
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/api/health')"

# Başlatma komutu
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8080"]
