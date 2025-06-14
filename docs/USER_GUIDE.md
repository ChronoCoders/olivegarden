# 👤 Zeytin Ağacı Analiz Sistemi - Kullanıcı Kılavuzu

Bu kılavuz, Zeytin Ağacı Analiz Sistemi'nin web arayüzü üzerinden nasıl kullanılacağını adım adım açıklar.

## 📋 İçindekiler

1. [Sisteme Giriş](#sisteme-giriş)
2. [Ana Sayfa](#ana-sayfa)
3. [Dosya Yükleme](#dosya-yükleme)
4. [Analiz Modu Seçimi](#analiz-modu-seçimi)
5. [Analiz Sonuçları](#analiz-sonuçları)
6. [Rapor İndirme](#rapor-i̇ndirme)
7. [Harita Görünümü](#harita-görünümü)
8. [Sorun Giderme](#sorun-giderme)

## 🔐 Sisteme Giriş

### Giriş Sayfası

1. Web tarayıcınızda sistem adresine gidin (örn: `https://your-domain.com`)
2. Ana sayfada giriş yapmadan da dosya yükleme ve analiz görüntüleme yapabilirsiniz
3. Admin işlemleri için giriş yapmanız gerekir

### Admin Girişi

**Varsayılan Admin Bilgileri:**
- Kullanıcı Adı: `admin`
- Şifre: `admin123`

> ⚠️ **Güvenlik Uyarısı:** Production ortamında mutlaka varsayılan şifreyi değiştirin!

**Giriş Adımları:**
1. Sayfanın üst kısmındaki "Giriş" butonuna tıklayın
2. Kullanıcı adı ve şifrenizi girin
3. "Giriş Yap" butonuna tıklayın
4. Başarılı girişten sonra admin paneli erişiminiz olur

## 🏠 Ana Sayfa

### Sayfa Bileşenleri

**1. Header Bölümü:**
- Sistem logosu ve başlığı
- GPU durumu göstergesi
- Kullanıcı bilgileri (giriş yapıldıysa)

**2. GPU Durumu Göstergesi:**
- 🟢 **GPU Mevcut:** Yeşil ikon ile GPU adı gösterilir
- 🔴 **GPU Mevcut Değil:** Kırmızı ikon ile "CPU modu kullanılacak" mesajı

**3. Ana İçerik Alanı:**
- Dosya yükleme bölümü
- Analiz sonuçları bölümü (analiz tamamlandıktan sonra)

## 📁 Dosya Yükleme

### Desteklenen Dosya Formatları

**RGB Görseller:**
- `.jpg`, `.jpeg` - JPEG formatı
- `.png` - PNG formatı

**Multispektral Dosyalar:**
- `.tif`, `.tiff` - GeoTIFF formatı

### Dosya Gereksinimleri

- **Maksimum Dosya Boyutu:** 100MB/dosya
- **Minimum Çözünürlük:** 512x512 piksel
- **Önerilen Çözünürlük:** 1024x1024 piksel ve üzeri

### Yükleme Yöntemleri

**Yöntem 1: Sürükle-Bırak**
1. Dosyalarınızı seçin
2. Yükleme alanına sürükleyin
3. Dosyalar otomatik olarak listelenecek

**Yöntem 2: Manuel Seçim**
1. "Seçmek için tıklayın" linkine tıklayın
2. Dosya seçici penceresi açılacak
3. Tek veya çoklu dosya seçin
4. "Aç" butonuna tıklayın

### Dosya Listesi

Yüklenen dosyalar şu bilgilerle listelenir:
- 📷 **Dosya Adı:** Orijinal dosya adı
- 📊 **Dosya Boyutu:** MB/KB cinsinden boyut
- 🏷️ **Dosya Tipi:** RGB veya Multispektral

### Dosya Validasyonu

Sistem otomatik olarak şunları kontrol eder:
- Dosya formatı uygunluğu
- Dosya boyutu limitleri
- Görsel çözünürlüğü
- Dosya bütünlüğü

**Hata Durumları:**
- ❌ Desteklenmeyen format
- ❌ Dosya çok büyük
- ❌ Çözünürlük çok düşük
- ❌ Bozuk dosya

## ⚙️ Analiz Modu Seçimi

Dosyalar yüklendikten sonra analiz modu seçimi görünür.

### CPU Modu
- 🖥️ **Simge:** Mikroişlemci ikonu
- ⏱️ **Hız:** Orta hız
- 🔋 **Kaynak:** Düşük güç tüketimi
- ✅ **Uyumluluk:** Her sistemde çalışır

**Ne Zaman Kullanılır:**
- GPU mevcut değilse
- Küçük dosyalar için
- Güç tasarrufu isteniyorsa

### GPU Modu
- ⚡ **Simge:** Şimşek ikonu
- 🚀 **Hız:** Yüksek hız
- 🔥 **Kaynak:** Yüksek güç tüketimi
- 💻 **Gereksinim:** NVIDIA GPU gerekli

**Ne Zaman Kullanılır:**
- Büyük dosyalar için
- Hızlı sonuç isteniyorsa
- GPU mevcut ise

### Mod Seçimi

1. İstediğiniz modu seçin (varsayılan: CPU)
2. Seçilen mod mavi/turuncu renkte vurgulanır
3. "Dosyaları Yükle" butonuna tıklayın

## 🔬 Analiz Süreci

### Yükleme Aşaması

1. **Dosya Yükleme:** Dosyalar sunucuya yüklenir
2. **Validasyon:** Dosya kontrolü yapılır
3. **Hazırlık:** Analiz için dosyalar hazırlanır

### Analiz Aşaması

**Analiz Başlatma:**
- Admin girişi gereklidir
- Seçilen mod gösterilir
- Gerçek zamanlı ilerleme takibi

**Analiz Adımları:**
1. 🔍 **RGB Analizi:** YOLOv8 ile ağaç/zeytin tespiti
2. 🌿 **Multispektral Analizi:** NDVI, GNDVI, NDRE hesaplama
3. 📊 **Sonuç Hesaplama:** Metrikler ve sağlık durumu
4. 📄 **Rapor Oluşturma:** PDF ve Excel raporları

### İlerleme Gösterimi

- ⏳ **Yükleme:** Dönen ikon ile bekleme
- 📈 **Analiz:** Mod ve süre bilgisi
- ✅ **Tamamlama:** Sonuç gösterimi

## 📊 Analiz Sonuçları

### Ana Metrikler

**1. Toplam Ağaç Sayısı**
- 🌳 Simge ile gösterilir
- YOLOv8 tespiti sonucu
- Büyük sayılarla vurgulanır

**2. Toplam Zeytin Sayısı**
- 🫒 Simge ile gösterilir
- Tahmini zeytin adedi
- Ağaç başına ortalama hesabı

**3. Tahmini Zeytin Miktarı**
- ⚖️ Simge ile gösterilir
- Kilogram cinsinden
- Ortalama zeytin ağırlığı ile hesaplanır

**4. Sağlık Durumu**
- 💚 Simge ile gösterilir
- NDVI değerine göre sınıflandırma
- Renk kodlu gösterim

### Spektral İndeksler

**NDVI (Normalized Difference Vegetation Index)**
- Bitki sağlığı göstergesi
- -1 ile +1 arası değer
- Yüksek değer = Sağlıklı bitki

**GNDVI (Green Normalized Difference Vegetation Index)**
- Yeşil bitki örtüsü göstergesi
- Klorofil aktivitesi ölçümü

**NDRE (Normalized Difference Red Edge)**
- Stres tespiti için kullanılır
- Erken uyarı sistemi

### Sağlık Durumu Sınıflandırması

| NDVI Değeri | Sağlık Durumu | Renk | Açıklama |
|-------------|---------------|------|----------|
| > 0.7 | Çok Sağlıklı | 🟢 Yeşil | Mükemmel durum |
| 0.5 - 0.7 | Sağlıklı | 🟡 Sarı | Normal durum |
| 0.3 - 0.5 | Orta Stresli | 🟠 Turuncu | Dikkat gerekli |
| 0.1 - 0.3 | Stresli | 🔴 Kırmızı | Müdahale gerekli |
| < 0.1 | Çok Stresli | 🟣 Mor | Acil müdahale |

### Performans Bilgileri

**Analiz Süresi:**
- Toplam işlem süresi
- Saniye cinsinden gösterim
- Mod karşılaştırması

**Kullanılan Cihaz:**
- CPU veya GPU
- Cihaz adı (GPU için)
- Bellek kullanımı

**İşlenen Dosya:**
- Toplam dosya sayısı
- Başarılı işlenen dosyalar
- Hata olan dosyalar

## 📄 Rapor İndirme

### Rapor Türleri

**PDF Raporu:**
- 📄 Profesyonel görünüm
- Grafik ve tablolar
- Yazdırma dostu format
- Detaylı analiz açıklamaları

**Excel Raporu:**
- 📊 Veri analizi için uygun
- Çoklu sayfa yapısı
- Grafik ve pivot tablo desteği
- Ham veri erişimi

### İndirme Adımları

1. **Admin Girişi:** Rapor indirme admin yetkisi gerektirir
2. **Format Seçimi:** PDF veya Excel seçin
3. **İndirme:** Dosya otomatik olarak indirilir

### Rapor İçeriği

**Özet Bölümü:**
- Analiz tarihi ve saati
- Toplam metrikler
- Sağlık durumu özeti
- Kullanılan teknoloji bilgisi

**Detay Bölümü:**
- Dosya bazında sonuçlar
- Spektral indeks değerleri
- Performans metrikleri
- Teknik detaylar

**Öneriler Bölümü:**
- Sağlık durumuna göre öneriler
- Bakım tavsiyeleri
- İyileştirme önerileri

## 🗺️ Harita Görünümü

### Harita Özellikleri

**Interaktif Harita:**
- Leaflet.js tabanlı
- Zoom ve pan desteği
- Responsive tasarım

**Veri Gösterimi:**
- Ağaç konumları (nokta)
- Sağlık durumu renk kodları
- Popup bilgi pencereleri

### Harita Kullanımı

**Navigasyon:**
- 🔍 **Zoom:** Mouse tekerleği veya +/- butonları
- 👆 **Pan:** Sürükle-bırak ile hareket
- 📱 **Mobil:** Dokunmatik hareketler

**Bilgi Erişimi:**
- Noktalara tıklayarak detay görüntüleme
- Popup pencerede metrik bilgileri
- Renk kodları ile hızlı durum tespiti

### Renk Kodları

- 🟢 **Yeşil:** Çok sağlıklı ağaçlar
- 🟡 **Sarı:** Sağlıklı ağaçlar
- 🟠 **Turuncu:** Orta stresli ağaçlar
- 🔴 **Kırmızı:** Stresli ağaçlar
- 🟣 **Mor:** Çok stresli ağaçlar

## 🔧 Sorun Giderme

### Yaygın Problemler

**1. Dosya Yüklenmiyor**

*Olası Nedenler:*
- Dosya boyutu çok büyük (>100MB)
- Desteklenmeyen format
- İnternet bağlantısı problemi

*Çözümler:*
- Dosya boyutunu küçültün
- Desteklenen formatları kullanın (.jpg, .png, .tif)
- İnternet bağlantınızı kontrol edin

**2. Analiz Başlamıyor**

*Olası Nedenler:*
- Admin girişi yapılmamış
- Dosya yüklenmemiş
- Sunucu problemi

*Çözümler:*
- Admin hesabı ile giriş yapın
- En az bir dosya yükleyin
- Sayfayı yenileyin

**3. GPU Modu Çalışmıyor**

*Olası Nedenler:*
- GPU mevcut değil
- CUDA driver problemi
- Bellek yetersizliği

*Çözümler:*
- CPU modunu kullanın
- GPU driver'larını güncelleyin
- Sistem yöneticisine başvurun

**4. Sonuçlar Görünmüyor**

*Olası Nedenler:*
- Analiz henüz tamamlanmamış
- JavaScript hatası
- Tarayıcı uyumsuzluğu

*Çözümler:*
- Analiz tamamlanmasını bekleyin
- Sayfayı yenileyin
- Farklı tarayıcı deneyin

### Hata Mesajları

**"Dosya validasyon hatası"**
- Dosya formatını kontrol edin
- Dosya bütünlüğünü kontrol edin
- Farklı dosya deneyin

**"Çok fazla istek"**
- Rate limit aşıldı
- 5 dakika bekleyin
- Daha az sıklıkla istek gönderin

**"Admin yetkisi gerekli"**
- Admin hesabı ile giriş yapın
- Token süresini kontrol edin
- Yeniden giriş yapın

**"Analiz bulunamadı"**
- Analiz ID'sini kontrol edin
- Analiz silinmiş olabilir
- Yeni analiz başlatın

### Tarayıcı Uyumluluğu

**Desteklenen Tarayıcılar:**
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

**Önerilen Ayarlar:**
- JavaScript aktif
- Cookies aktif
- Local storage aktif
- Modern tarayıcı sürümü

### Performans İpuçları

**Hızlı Analiz İçin:**
- GPU modu kullanın (mevcut ise)
- Dosya boyutlarını optimize edin
- Gereksiz dosyaları yüklemeyin

**Kararlı Çalışma İçin:**
- Güvenilir internet bağlantısı
- Güncel tarayıcı kullanın
- Popup blocker'ı kapatın

### Destek Alma

**Teknik Destek:**
1. Hata mesajını not alın
2. Tarayıcı konsol loglarını kontrol edin
3. Sistem yöneticisine başvurun
4. Log dosyalarını paylaşın

**Kullanıcı Desteği:**
- Bu kılavuzu tekrar okuyun
- Video eğitimleri izleyin
- SSS bölümünü kontrol edin
- Kullanıcı forumlarına başvurun

## 📱 Mobil Kullanım

### Mobil Uyumluluk

Sistem responsive tasarım ile mobil cihazlarda da kullanılabilir:

**Desteklenen Özellikler:**
- ✅ Dosya yükleme
- ✅ Analiz görüntüleme
- ✅ Rapor indirme
- ✅ Harita görünümü

**Sınırlı Özellikler:**
- ⚠️ Büyük dosya yükleme
- ⚠️ Detaylı rapor görüntüleme
- ⚠️ Admin paneli

### Mobil İpuçları

- Yatay ekran kullanın
- WiFi bağlantısı tercih edin
- Dosya boyutlarını küçük tutun
- Basit dokunuş hareketleri kullanın

## 🎯 En İyi Uygulamalar

### Dosya Hazırlama

1. **Görsel Kalitesi:**
   - Yüksek çözünürlük kullanın
   - İyi aydınlatma koşulları
   - Net ve odaklı çekimler

2. **Dosya Organizasyonu:**
   - Anlamlı dosya isimleri
   - Tarih/saat bilgisi ekleyin
   - Lokasyon bilgisi dahil edin

3. **Multispektral Veriler:**
   - Koordinat sistemi bilgisi
   - Band bilgileri doğru
   - Kalibrasyon yapılmış

### Analiz Optimizasyonu

1. **Mod Seçimi:**
   - Küçük dosyalar: CPU
   - Büyük dosyalar: GPU
   - Hız önceliği: GPU

2. **Dosya Kombinasyonu:**
   - RGB + Multispektral ideal
   - Aynı alanın farklı açıları
   - Farklı zaman dilimlerinden veriler

3. **Sonuç Değerlendirme:**
   - Spektral indeksleri birlikte değerlendirin
   - Görsel sonuçları kontrol edin
   - Tarihsel verilerle karşılaştırın

Bu kılavuz, sistemi etkili bir şekilde kullanmanız için gerekli tüm bilgileri içermektedir. Daha detaylı teknik bilgi için API dokümantasyonunu inceleyebilirsiniz.