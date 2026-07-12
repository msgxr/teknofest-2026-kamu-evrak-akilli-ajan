# Standart Dosya Planı (SDP) — Doğrulanmış Referans Notu

Bu belge, resmî yazışma sayı/dosya kodlama düzenini yöneten **Standart Dosya
Planı**nın (SDP) birincil kaynaktan doğrulanmış özetidir. Projedeki yazışma
sayısı üretimi ve biçim denetimi için referans olarak tutulur.

> **Neden mevzuat korpusunda (retrieval) değil, referans belge?** SDP bir
> dosya-KODLAMA standardıdır (bir yazının sayısındaki dosya konu kodunu belirler);
> mevzuat öneri ajanının önerdiği içerik-bazlı kanun/yönetmeliklerden işlevsel
> olarak farklıdır. Etiketli evrak setlerinin hiçbiri `mevzuat_beklenen` olarak
> SDP'yi işaret etmez; SDP retrieval korpusuna eklendiğinde ölçülen etki (12.07.2026,
> geliştirme seti) mevzuat isabet@3'ü **0,962 → 0,923** düşürmüştür — üç evrakta
> ilk üç öneriye girip doğru kanun önerisini dışarı itmiştir. Yani bu belge, geçerli
> bir hukuki referans olmakla birlikte retrieval korpusuna dahil edildiğinde yer
> gerçeği (ground-truth) karşılığı olmadan gürültü ekler. Bu nedenle referans belge
> olarak tutulur; SDP'yi konu alan (dosya kodu atama senaryolu) etiketli evrak
> eklendiğinde korpusa dahil edilmesi yeniden değerlendirilebilir.

## Dayanak

Standart Dosya Planı, kamu kurum ve kuruluşlarında üretilen belge ve dosyaların
konularına göre ortak bir kodlama düzeninde sınıflandırılmasını sağlar. Dayanağı
**25.03.2005 tarihli Resmî Gazete'de yayımlanan 2005/7 sayılı Başbakanlık
Genelgesidir**; plan Devlet Arşivleri Genel Müdürlüğü koordinasyonunda
hazırlanmıştır. Güncellenmiş "Saklama Süreli Standart Dosya Planı" **02.01.2024**
tarihinden itibaren yürürlüğe konmuştur.

## Üç ana bölüm

| Aralık | Ad | Kapsam | Kurumdan kuruma |
|---|---|---|---|
| 000-099 | Genel/Ortak Konular | Mevzuat, faaliyet raporu, istatistik vb. her birimde bulunması muhtemel dosyalar | AYNI |
| 100-599 | Ana Hizmet Faaliyetleri | Kurumun ana hizmet birimlerinin faaliyet belgeleri | FARKLI (kuruma özgü) |
| 600-999 | Danışma-Denetim ve Yardımcı Hizmet | Teftiş, hukuk, personel, idari/mali işler vb. | AYNI |

## Yazışma sayısıyla ilişkisi

Resmî yazının sayı bölümü, birim kimlik (DETSİS) kodundan sonra tire ile eklenen
dosya konu numarasını taşır. Örnek: **`6378844-805.02.01-3473`** — birim kodu
`6378844`, dosya konu kodu `805.02.01`, belge sıra numarası `3473`. Böylece her
yazı hem üreten birime hem konusuna göre standart biçimde kodlanır (bu proje,
kurgu sayıları bu kalıpla üretir; bkz. `src/utils/sayi_uretici.py`).

## Ortak ana konu grupları (000-099 ve 600-999; tüm kurumlarda özdeş)

| Kod | Ad | Kod | Ad |
|---|---|---|---|
| 010 | Mevzuat İşleri | 700 | Bilgi Sistemleri ve Bilgi İşlem |
| 020 | Olurlar, Onaylar | 720 | Dış İlişkiler ve Avrupa Birliği |
| 030 | Anlaşma, Sözleşme, Protokoller | 750 | Emlak ve Yapım İşleri |
| 040 | Faaliyet Raporları | 770 | Eğitim İşleri |
| 045 | Görüşler | 800 | İdari ve Sosyal İşler |
| 050 | Kurullar ve Toplantılar | 805 | Belge Yönetimi ve Arşiv İşlemleri |
| 060 | Kalite Yönetim Sistemi | 806 | Kütüphane ve Dokümantasyon |
| 600 | Araştırma ve Planlama | 807 | Bakım-Onarım İşleri |
| 602 | Plan ve Program İşleri | 810 | Sigorta İşleri |
| 610 | Soru Önergeleri | 820 | Tanıtım ve Yayın İşleri |
| 620 | Basın ve Halkla İlişkiler | 840 | Mali İşler |
| 621 | Basın İşleri | 841 | Bütçe Hazırlama ve Uygulama |
| 622 | Talep, Şikayet ve Görüşler | 850 | Kıymetli Evrak İşlemleri |
| 640 | Hukuk İşleri | 870 | Özel Kalem ve Protokol |
| 641 | Dava Dosyaları | 900 | Personel İşleri |
| 660 | Teftiş ve Denetim | 903 | Personel Özlük İşleri |
| — | — | 915 | Sendikalarla İlgili İşler |

Örnek alt kırılım: `622.01.01` → 622 Talep, Şikayet ve Görüşler > 622.01
Vatandaşların Talep ve Şikayetleri > 622.01.01 Talepler.

Ana hizmet kodları (100-599) kuruma özgü olduğundan burada listelenmez; her kurum
kendi ana hizmet dosya planını Devlet Arşivleri Başkanlığı onayıyla belirler.

## Kaynak ve doğrulama düzeyi

- **Birincil (resmî):** Dayanak (2005/7 Genelge, 25.03.2005), üç bölüm yapısı ve
  622 örnek kodu — [Resmî Gazete 20050325-10](https://www.resmigazete.gov.tr/eskiler/2005/03/20050325-10.htm).
  020, 805, 900 kodları ve örnek sayı kalıbı — Devlet Arşivleri Başkanlığı genel
  açıklamaları (devletarsivleri.gov.tr).
- **Çapraz doğrulanmış (iki bağımsız resmî kurum SDP'si birebir örtüştü):** Ortak
  ana konu grubu listesi — Erciyes Üniversitesi ve T.C. Ticaret Bakanlığı standart
  dosya planları.
- **Doğrulanamayan:** 2005 Resmî Gazete sayı numarası birebir okunamadı (tarih
  25.03.2005 kesin); Devlet Arşivleri birincil SDP kitabı taranmış görüntü PDF
  olduğundan tam liste birincilden birebir okunamamış, ikincil resmî kurum
  kaynaklarıyla mükerrer doğrulanmıştır.

Bu belge kaynaklardaki bilgilerin özgün cümlelerle özetidir (tam metin kopyası
değildir); SDP kamu kullanımına açıktır.
