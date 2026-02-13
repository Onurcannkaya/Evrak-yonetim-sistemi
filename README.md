# Sivas Belediyesi - Akıllı Evrak Yönetim Sistemi v4.0

## Hızlı Başlangıç

### Sistem Gereksinimleri
- **Python:** 3.12 veya üzeri
- **İşletim Sistemi:** Windows 10/11
- **RAM:** Minimum 8GB (16GB önerilir)
- **İnternet:** Kent Rehberi doğrulaması için gerekli

### Kurulum

Tüm bağımlılıklar zaten yüklü. Eğer yeni bir bilgisayarda kurulum yapıyorsanız:

```bash
pip install -r requirements.txt
```

### Başlatma

**Yöntem 1: Kısayol (Önerilen)**
- `Evrak_Sistemi_Baslat.bat` dosyasına çift tıklayın

**Yöntem 2: Komut Satırı**
```bash
python gui_app.py
```

## Özellikler

### ✅ Otomatik Belge Sınıflandırma
- **Meclis Kararı** (1993-48 formatı)
- **Tapu/İmar Belgesi** (Genel)

### ✅ Gelişmiş OCR Motoru
- **Triple-Engine:** EasyOCR (Türkçe+İngilizce) + Tesseract + PaddleOCR
- **Adaptif Restorasyon:** 5 seviye (Standard → Aggressive → Extreme → Ultra → Hyper)
- **ROI-Based Processing:** Düşük güvende bölgesel analiz

### ✅ Kent Rehberi Entegrasyonu
- **Otomatik Doğrulama:** Ada/Parsel bilgisi Sivas Belediyesi veritabanı ile kontrol edilir
- **Akıllı Düzeltme:** OCR hataları otomatik tespit edilir ve düzeltilir
  - Örnek: Ada "15" → "150" (5 alternatif arasından en uygun seçilir)

### ✅ Veritabanı Yönetimi
- **SQLite:** Tüm belgeler otomatik kaydedilir
- **Arama:** Ada, Parsel, Mahalle, Tarih ile filtreleme
- **Dışa Aktarma:** PDF rapor oluşturma

## Kullanım

1. **Belge Yükle:** "Dosya Seç" butonuna tıklayın
2. **İşle:** "Analiz Et" butonuna tıklayın
3. **Sonuçları İncele:** Sağ panelde metadata görüntülenir
4. **Kaydet:** "Kaydet" butonuyla veritabanına ekleyin

### Kent Rehberi Doğrulaması

Sistem otomatik olarak:
1. Ada/Parsel bilgisini Kent Rehberi API'sine gönderir
2. Eğer direkt eşleşme yoksa, alternatif sayılar dener (15 → 150, 151, 152...)
3. En uygun eşleşmeyi bulur ve önerir
4. Kullanıcı onayı ile düzeltmeyi uygular

**Not:** Mahalle isimleri doğrulanmaz çünkü belgeler ilçe verilerini veya eski mahalle isimlerini içerebilir.

## Dosya Yapısı

```
Evrak Yönetim Sistemii/
├── gui_app.py                    # Ana GUI uygulaması
├── document_processor.py         # OCR ve veri çıkarım motoru
├── city_guide_client.py          # Kent Rehberi API istemcisi
├── database_manager.py           # SQLite veritabanı yöneticisi
├── Evrak_Sistemi_Baslat.bat     # Windows başlatıcı
├── requirements.txt              # Python bağımlılıkları
├── municipal_dictionary.txt      # Belediye terimleri sözlüğü
├── sivas_mahalleler.txt         # Sivas mahalle listesi
└── evrak_database.db            # Belge veritabanı (otomatik oluşturulur)
```

## Sorun Giderme

### OCR Motorları Yüklenmiyor
```bash
# EasyOCR dil paketlerini manuel yükle
python -c "import easyocr; reader = easyocr.Reader(['tr', 'en'])"

# PaddleOCR modellerini manuel yükle
python -c "from paddleocr import PaddleOCR; ocr = PaddleOCR(use_angle_cls=True, lang='tr')"
```

### Kent Rehberi Bağlantı Hatası
- İnternet bağlantınızı kontrol edin
- `https://kentrehberi.sivas.bel.tr` adresine erişebildiğinizi doğrulayın
- Sistem Kent Rehberi olmadan da çalışır (sadece doğrulama yapılmaz)

### Düşük OCR Güveni
- Belgenin kalitesini artırın (tarama çözünürlüğü minimum 300 DPI)
- Kontrast ve parlaklık ayarlarını optimize edin
- Sistem otomatik olarak 5 seviye restorasyon uygular

## Teknik Detaylar

### OCR Pipeline
1. **Sınıflandırma:** Belge tipi otomatik tespit edilir
2. **Restorasyon:** Adaptif görüntü iyileştirme (5 seviye)
3. **Triple-Engine OCR:** 3 motor paralel çalışır, en iyi sonuç seçilir
4. **Semantik Düzeltme:** Municipal Dictionary ile yaygın hatalar düzeltilir
5. **ROI Processing:** Düşük güvende bölgesel analiz
6. **Kent Rehberi Doğrulama:** Ada/Parsel bilgisi API ile kontrol edilir

### Performans
- **İlk Belge:** ~30-60 saniye (model yükleme dahil)
- **Sonraki Belgeler:** ~10-20 saniye
- **Veritabanı:** Sınırsız belge kapasitesi

## Versiyon Geçmişi

### v4.0 (2026-02-12)
- ✅ Kent Rehberi API entegrasyonu
- ✅ Otomatik Ada/Parsel doğrulama ve düzeltme
- ✅ Header analizi (başlık bölgesi ayrı taranır)
- ✅ Numeric OCR refinement
- ✅ 5 seviye adaptif restorasyon

### v3.0
- ✅ PaddleOCR entegrasyonu (Triple-Engine)
- ✅ ROI-based processing
- ✅ Meclis Kararı özel parser

### v2.0
- ✅ GUI uygulaması
- ✅ SQLite veritabanı
- ✅ Dual-OCR (EasyOCR + Tesseract)

### v1.0
- ✅ Temel OCR ve veri çıkarımı

## Destek

Sorularınız için: Sivas Belediyesi Bilgi İşlem Müdürlüğü
