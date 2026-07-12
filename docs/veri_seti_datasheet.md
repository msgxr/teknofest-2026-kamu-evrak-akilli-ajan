# Veri Seti Datasheet'i — Kurgu Evrak Setleri

> Bu belge, Gebru vd. (2021) "Datasheets for Datasets" biçimini izler.
> Amaç: değerlendirme verisinin kökeni, bileşimi ve sınırlarının şeffaf ve
> tekrarlanabilir belgelenmesi.

## 1. Motivasyon
- **Neden:** TEKNOFEST 2026 şartnamesi GERÇEK kamu verisi kullanımını yasaklar;
  bu setler sistemin uçtan uca değerlendirilmesi için üretilmiş SENTETİK veridir.
- **Kim:** Takım (Agentra Tech) tarafından üretilmiş; Apache 2.0.

## 2. Bileşim
| Set | Adet | Amaç |
|---|---|---|
| `kurgu_evraklar` | 52 | Geliştirme/kalibrasyon (kural setinin ayarlandığı set) |
| `kurgu_evraklar_heldout` | 16 | Tutulmuş (held-out) — geliştirmede kullanılmadı |
| `kurgu_evraklar_heldout_v2` | 16 | İkinci tutulmuş set |
| `kurgu_evraklar_heldout_v3` | 16 | Adversarial tutulmuş set (kusurlu/zorlayıcı girdiler) |
| `mevzuat_metinleri` | 15 | Kamuya açık mevzuat korpusu (RAG) |
- **Türler (8):** dilekçe, üst yazı, cevap yazısı, tutanak, rapor, genelge,
  onaylı belge, bilgilendirme. **Birimler (9):** temsili kamu organizasyon şeması.
- **Etiket şeması:** `{tur, birim_kodu, eksik_alanlar, aciklama, mevzuat_beklenen}`.
  Etiketler bağımsız çift gözden geçirmeyle doğrulandı.

## 3. Kişisel Veri ve KVKK
- **Gerçek PII YOKTUR.** Kurgu TCKN'ler resmî checksum'ı geçer ancak gerçek bir
  kişiye ait DEĞİLDİR; ad/adres/telefon/IBAN tümüyle uydurmadır.
- Sistem çıktısında bu alanlar KVKK anonimleştirme ajanıyla maskelenir.

## 4. Toplama ve Ön İşleme
- **Üretim:** desen çeşitliliği hedeflenerek elle + şablonla üretim (CİMER
  başvurusu, dağıtımlı yazı, damgalı süreli yazı, çok-konulu evrak vb.).
- **Format:** düz metin (.txt), UTF-8. Ortalama ~1,8 KB.
- **Bütünlük:** her setin içerik hash'i değerlendirme raporundaki
  tekrarlanabilirlik mührüne gömülür (`set_icerik_hash`).

## 5. Kullanım ve Dağıtım
- **Kullanım:** yalnızca bu sistemin geliştirilmesi ve değerlendirilmesi.
- **Değerlendirme bütünlüğü:** tutulmuş setler üzerinde ölçülen hatalara
  bakılarak kural/kod düzeltmesi YAPILMAZ (yapılırsa `teknik_rapor.md` §5'e
  açıkça yazılır). Held-out metrikleri, eklenen tüm geliştirmelerde değişmeden
  kalmıştır (deterministik doğrulama).
- **Dağıtım:** açık kaynak depoda (TAKP GitHub), Apache 2.0.

## 6. Bakım
- Setler genişletildikçe (ör. 35→52) `data/README.md` ve bu datasheet güncellenir;
  içerik hash'i otomatik değişerek eski raporlarla karışmayı önler.
