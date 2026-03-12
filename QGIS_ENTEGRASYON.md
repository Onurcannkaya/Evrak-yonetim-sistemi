# Sivas Belediyesi QGIS - Evrak Yönetim Sistemi Entegrasyon Rehberi

Sivas Belediyesi sınırları içerisinde yer alan coğrafi haritalarınız (Parseller vb.) ile Evrak Yönetim Sistemi veritabanını birbirine bağlayarak, haritada seçtiğiniz herhangi bir binanın/parselin taranmış taranabilir evraklarını anında görüntüleyebilirsiniz.

## Adım 1: QGIS'e Veritabanını (SQLite) Bağlama
Sistemimiz, QGIS'in yerel olarak desteklediği `evrak_yonetim.db` (SQLite) dosyasını kullanmaktadır.

1. QGIS'i açın.
2. Sol tarafta bulunan **Tarayıcı (Browser)** panelini bulun. (Eğer kapalıysa üst menüden **Görünüm > Paneller > Tarayıcı** yolunu izleyip açın).
3. Tarayıcı panelini kullanarak bilgisayarınızdaki klasörler arasında gezinin ve evrak uygulamasının bulunduğu dizine (örn: Masaüstü) gidin.
4. `evrak_yonetim.db` dosyasını bulun ve yanındaki ok (genişlet) simgesine basın. QGIS arkaplanda SQLite'ı okuyacaktır.
5. Altında açılan listeden **`vw_qgis_evraklar`** tablosunu bulun.
6. Bu tabloyu farenizle sürükleyip alt kısımdaki **Katmanlar (Layers)** paneline bırakın.

> *Not: Katmanlar panelinize eklendi! Bu katman, geometrisi olmayan "Salt Veri Tablosu (Attribute Table)" olarak QGIS'e bağlandı.*

## Adım 2: Haritanız ile Evrakları Birleştirme (Join)
Elbette elinizde halihazırda bir Sivas "Parseller" haritanız (Shapefile, GeoPackage, PostgreSQL vb.) vardır. Bu parsel katmanınızda örneğin `MAHALLE_AD`, `ADA_NO`, `PARSEL_NO` gibi kolonlar olduğunu varsayıyoruz.

Biz QGIS katman ilişkilerini (Relations) kullanarak veya en basitinden **Action** mekanizması ile bir Python betiği gömerek işlemi çözeceğiz. En sağlam yöntem Eylemler (Actions) yazmaktır.

## Adım 3: QGIS Eylemi (Action) Eklemek (Sihirli Kısım!)

Bu adımda Parsel haritanıza tıklandığında anında ilgili evrağı getiren "Tıklama Kodunu" ekleyeceğiz.

1. QGIS katmanlar panelinden **Sivas_Parseller** (Sizin asıl harita katmanınızın adı neyse o) katmanına sağ tıklayın ve **Özellikler (Properties)** seçin.
2. Sol menüden **Eylemler (Actions)** sekmesine gelin.
3. Yeşil renkli **Eylem Ekle (➕)** butonuna tıklayın.
4. Eylem özelliklerini şu şekilde doldurun:
   - **Türü (Type):** `Python`
   - **Açıklama (Description):** `Arşivi Gör (Evrak)`
   - **Kapsam (Action Scopes):** `Feature`, `Canvas` kutucuklarını işaretleyin.

5. **Eylem Metni (Action Text)** kısmına tam olarak aşağıdaki kodu yapıştırın:

```python
import sqlite3
import os
import subprocess
from qgis.utils import iface
from PyQt5.QtWidgets import QMessageBox

# --- AYARLAR: LÜTFEN DOSYA YOLUNU KENDINİZE GÖRE DÜZENLEYİN ---
# Evrak Yonetim Sistemi kurulu olan klasördeki SQLite dosyası:
DB_PATH = r"C:\Users\okaya\Desktop\Evrak Yönetim Sistemii\evrak_yonetim.db"

# Kendi parsel haritanızdaki kolon isimlerini yazın (DİKKAT: Dışta tek tırnak, içte çift tırnak kullanın):
mahalle_kolonu = '[% "MAHALLE" %]'
ada_kolonu = '[% "ADA" %]'
parsel_kolonu = '[% "PARSEL" %]'
# -------------------------------------------------------------

mahalle_kolonu = str(mahalle_kolonu).upper().strip()
ada_kolonu = str(ada_kolonu).upper().strip()
parsel_kolonu = str(parsel_kolonu).upper().strip()

try:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Veritabanı dosyası bulunamadı: {DB_PATH}")

    # SQLite'a bağlan ve vw_qgis_evraklar üzerinden sorgula
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # QGIS'den aldığımız Mahalle, Ada ve Parsel bilgisiyle Evrak Sorgusu
    # % LIKE mantığı ile esnek arama da yapabilirsiniz, tam eşleşme yapıyoruz:
    query = """
        SELECT subject, win_file_path 
        FROM vw_qgis_evraklar 
        WHERE mahalle = ? AND ada = ? AND parsel = ?
        ORDER BY extracted_date DESC
    """
    cursor.execute(query, (mahalle_kolonu, ada_kolonu, parsel_kolonu))
    sonuclar = cursor.fetchall()
    conn.close()

    if not sonuclar:
        QMessageBox.information(None, "Kayıt Bulunamadı", 
            f"{mahalle_kolonu} Mah. {ada_kolonu} Ada {parsel_kolonu} Parsel için evrak bulunamadı.")
    else:
        # Evrak(lar) bulundu! İlk bulunanı veya tümünü açabiliriz. En güncelini açıyoruz:
        baslik, dosya_yolu = sonuclar[0]
        
        # Dosya yolunu standart Windows yoluna çekme (WinError 5 & Path sorunları için)
        gercek_path = os.path.normpath(dosya_yolu)
        
        if os.path.exists(gercek_path):
            QMessageBox.information(None, "Evrak Bulundu", 
                f"{len(sonuclar)} adet evrak bulundu.\nEn günceli ({baslik}) açılıyor...")
            os.startfile(gercek_path)
        else:
            QMessageBox.warning(None, "Dosya Bulunamadı", 
                f"Veritabanı bu kaydı ('{baslik}') içeriyor ancak dosyanın fiziki orijinali diskte bulunamadı:\n{gercek_path}")

except Exception as e:
    QMessageBox.critical(None, "Hata", f"Evrak sistemine bağlanırken hata oluştu:\n{str(e)}")
```

6. Kodu kendi sisteminize göre kısımlarını (`DB_PATH`, `MAHALLE`, `ADA`, `PARSEL`) ayarladıktan sonra **Tamam (OK)** diyerek eylemi kaydedin. Katman özelliklerini kapatın.

## Adım 4: Sistemin Test Edilmesi (Kullanımı!)
1. Üst QGIS takım çubuğunuzda bulunan dişli çarklı **"Eylemi Çalıştır (Run Feature Action)"** butonunu seçin.
2. Ekranda, Parsel haritasının üzerindeki test etmek istediğiniz bir parsele tıklayın.
3. Çıkan menüden "Arşivi Gör (Evrak)" butonuna tıklayın.
4. Hazırladığımız betik otomatik olarak sizin tıkladığınız binanın Ada/Parsel verisini okur, `evrak_yonetim.db` dosyasına gider, o parsele ait bir makbuz/tapu/pdf varsa (Aşama 1'de Tesseract ile yapılan harika Aranabilir PDF gibi) sistem varsayılan göstericinizle tık diye ekrana açar!

İşte bu kadar. Şehrin dijital arşivi canlı haritanıza sıfır yazılım entegrasyon maliyetiyle entegre oldu! 🗺️📑
