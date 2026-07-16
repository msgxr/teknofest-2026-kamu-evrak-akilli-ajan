---
name: pdf-ingestion
description: Bir PDF'i, context window'u patlatmadan veya yapıyı kaybetmeden modele sok. Çoğu durumda native PDF, OCR-sonra-metin yaklaşımını yener; çok uzun dokümanlarda çıkar-sonra-özetle, native'i yener.
when_to_use: kullanıcı bir PDF bırakır, "bu raporu oku", bir dokümandan tablo/şekil çıkarma, uzun-biçimli doküman özetleme, PDF olarak duran spec dokümanı
---

# PDF İçe Alma (Ingestion)

Bir PDF'i modele beslemenin, artan ön-işleme (preprocessing) sırasıyla üç yolu:

1. **Native PDF girişi** — dosyayı doğrudan geçir. Model, sayfaları görüntü + çıkarılmış metin olarak görür. Anlamlı yerleşimi (tablolar, şekiller, formlar) olan ~100 sayfa altındaki dokümanlar için en iyisi. Yapıyı korur.

2. **Metin çıkarma sonra gönder** — `pdftotext` / `pypdf` / muadili, ardından metni gönder. Yerleşimi kaybeder ama ucuzdur. Tabloların önemli olmadığı, düz-metin-ağırlıklı dokümanlar için uygundur.

3. **Çıkar → parçala (chunk) → özetle → gönder** — 100 sayfadan büyük dokümanlar için ya da aynı dokümanı çok kez sorgulayacağın zaman. Bir kez ön-işle, özeti cache'le.

## Hangi yolu seçmeli

| Doküman biçimi | Yol |
|---|---|
| <20 sayfa, yerleşim önemli (rapor, form, fatura) | Native |
| <20 sayfa, saf düz metin (makale, not) | Metin çıkarma |
| 20-100 sayfa, karışık | Native, ama bağlam darsa parçala |
| >100 sayfa | Çıkar → parçala → özetle |
| Taranmış PDF (metin katmanı yok) | Önce OCR (Tesseract veya vision model), ardından çıkarılmış metin gibi işle |
| Asıl mesele tablolar | Native — metin çıkarıcılar tabloları bozar |
| Asıl mesele şekiller/diyagramlar | Native + açık "N. sayfadaki şekli tanımla" prompt'u |

## Native PDF — iyi varsayılanlar

- PDF'i bir prompt-caching breakpoint'inde cache'le (bkz. `prompt-caching`). Native PDF'ler büyüktür — cache'lenmemiş her tur, tüm doküman üzerinden tam input fiyatına mal olur.
- Tüm doküman yerine **belirli sayfalar** hakkında sor ("14. sayfadaki 3.2 bölümünü özetle"). Model, hedefli sorguları "bu 80 sayfalık raporu özetle"den daha iyi ele alır.
- Modelin halüsinasyon görmediğine dair bir sağlamlık kontrolü olarak **sayfa-atıflı iddialarla** devam et — "doküman X'i hangi sayfada söylüyor?".

## Çıkar-sonra-gönder — tuzaklar

- **`pdftotext` okuma sırası.** Çok-sütunlu PDF'ler iç içe geçmiş satırlar olarak çıkar. Sütun korumak için `pdftotext -layout`, düz okuma sırası için `pdftotext -raw` kullan — doküman başına seç, tahmin etme.
- **Tablolar kelime çorbasına döner.** Tablolar belirleyiciyse (load-bearing), native veya tablo-başına görüntü çıkarma. Metin değil.
- **Üstbilgi/altbilgiler her sayfada tekrarlanır.** Göndermeden önce onları ayıkla, yoksa model onları içerik olarak ele alır.
- **Dipnotlar**, çıkarılmış akışta rastgele konumlara **kayar**. Filtrele veya gürültüyü kabul et.

## Çıkar → parçala → özetle (uzun dokümanlar)

- Token sayısına göre değil, bölüme göre parçala. Bölüm-farkında bir ayrım, dokümanın mantığına saygı gösterir; naif bir 4K-token'lık ayrım, cümleleri ve tabloları keser.
- Her bölümü bir "harita"ya (map) özetle — her biri 1-2 paragraf. Haritayı, bağlama bütün olarak sığacak kadar kısa tut (200 sayfalık bir doküman için ~2-4K token).
- Tam bölüm metnini haritanın yanında sakla (bir manifest içinde yollar). Bir soru özetin ötesinde ayrıntı gerektirdiğinde talep üzerine getir (fetch).
- Doküman üzerindeki çok-turlu soru-cevabın yeniden işlememesi için haritayı bir prompt-caching breakpoint'inde cache'le.

## Kırmızı bayraklar

- **Tek bir soruyu cevaplamak için 200 sayfalık bir PDF'i native göndermek.** Önce ilgili sayfa aralığını çıkar.
- **Bir form veya faturada metin çıkarıcıya güvenmek.** Yerleşim anlam taşır. Native kullan.
- **Zaten metin katmanı olan bir PDF'i OCR'lamak.** Önce `pdftotext -q file.pdf -` ile kontrol et — metin çıkıyorsa OCR gerekmez.
- **Çıktıda sayfa atıfları yok.** Model, uzun PDF'ler boyunca kendinden emin biçimde halüsinasyon görebilir. Yanıt biçimine sayfa numaralarını zorla.
- **Aynı PDF'i cache'lemeden her turda yeniden yüklemek.** Maliyet doğrusal tırmanır; 5 dakikalık bir cache bunu düzeltir.

## Loopkit-komşusu

PDF bir spec ise, onu `spec-first` aracılığıyla `PROMPT.md`'ye çıkar — ajan her turda PDF'i yeniden taramak yerine düz metni yeniden okumalıdır.
