# Veri Setleri

Bu dizin, proje kapsamında kullanılan veri setlerini içerir.

## ⚠️ Önemli Not

**Bu projede gerçek kamu verisi kullanılmamaktadır.** Tüm evraklar sentetiktir; geçen kişi, kurum, sayı, T.C. kimlik numarası ve olaylar kurgudur. Kurgu T.C. kimlik numaraları yalnızca algoritmik (checksum) doğrulama testleri için üretilmiş olup gerçek kişilere ait değildir.

## Veri Kaynakları

### 1. Kurgu Evrak Örnekleri (`raw/kurgu_evraklar/`)

Değerlendirme ve demo amaçlı, etiketli sentetik resmî evrak veri seti.

- **Dosya sayısı:** 35 adet `.txt` (UTF-8) + 1 adet `etiketler.json`
  - 32 adet sistematik örnek: 8 evrak türü × 4 örnek
  - 3 adet ilk sürümden gelen örnek (`ornek_*.txt`)
- **Adlandırma şeması:** `<tur>_01.txt` … `<tur>_04.txt`
  - Tür anahtarları: `dilekce`, `ust_yazi`, `cevap_yazisi`, `bilgilendirme`, `tutanak`, `rapor`, `genelge`, `onayli_belge`
- **Çeşitlilik:** Farklı kurumlar (bakanlık, valilik, kaymakamlık, belediye, üniversite, genel müdürlük) ve farklı konular; 9 hedef birimin (yazı işleri, hukuk, insan kaynakları, mali hizmetler, bilgi işlem, strateji, basın ve halkla ilişkiler, destek hizmetleri, genel müdürlük) her biri en az 2 evrakta doğru yönlendirme hedefidir.
- **Kasıtlı eksik alanlar:** Her evrak türünden en az 1 dosyada, eksik bilgi tespiti (Görev 1) ölçümü için kasıtlı olarak eksik bırakılmış alanlar vardır (ör. imzasız dilekçe, sayısız üst yazı, tarihsiz tutanak). Eksiklikler etiket dosyasında belirtilmiştir.
- **Üretim yöntemi:** Sentetik — takım tarafından, Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik'teki biçim öğeleri (sayı, konu, ilgi, imza, dağıtım vb.) örnek alınarak elle yazılmıştır.
- **Kaynak:** Takım üretimi
- **Lisans:** Apache 2.0

#### Etiket formatı (`raw/kurgu_evraklar/etiketler.json`)

Tüm `.txt` dosyaları için tek bir JSON sözlüğü:

```json
{
  "dilekce_03.txt": {
    "tur": "dilekce",
    "birim_kodu": "yazi_isleri",
    "eksik_alanlar": ["imza", "tc_kimlik"],
    "aciklama": "Kaymakamlık arşivinden yapı ruhsatı örneği talebi; imza ve T.C. kimlik numarası kasıtlı olarak eksik."
  }
}
```

- `tur`: Evrak türü anahtarı (yukarıdaki 8 tür + `diger`).
- `birim_kodu`: Doğru yönlendirme hedefi olan birimin anahtarı (`yazi_isleri`, `hukuk`, `insan_kaynaklari`, `mali_hizmetler`, `bilgi_islem`, `strateji`, `basin_halkla_iliskiler`, `destek_hizmetleri`, `genel_mudurluk`).
- `eksik_alanlar`: Evrakta gerçekten eksik olan alanların listesi; alan adları eksik bilgi tespit modülüyle uyumludur (`tarih`, `sayi`, `konu`, `muhatap`, `ilgi`, `imza`, `ad_soyad`, `tc_kimlik`, `adres`, `kurum_bilgisi`, `dagitim`, `katilimcilar`). Tam evraklarda boş listedir.
- `aciklama`: Evrağı tek cümlede tanımlayan açıklama.

### 2. Held-out (Tutulmuş) Değerlendirme Seti (`raw/kurgu_evraklar_heldout/`)

Kural kalibrasyonundan bağımsız **dış geçerlilik** ölçümü için ayrılmış, etiketli sentetik evrak seti.

- **Amaç:** Sınıflandırma, yönlendirme ve eksik bilgi tespiti kuralları `raw/kurgu_evraklar/` (geliştirme seti) üzerinde kalibre edilmiştir; aynı set üzerinde ölçülen metrikler ezberleme (overfitting) riskini dışlayamaz. Bu set, kural geliştirme ve kalibrasyon sürecinin **hiçbir aşamasında kullanılmamıştır**; üzerinde ölçülen metrikler sistemin görülmemiş evraklara genelleme başarımını gösterir. Held-out set üzerinde çıkan hatalar giderilmek istenirse, düzeltme sonrası ölçümün "held-out" niteliği kaybolur ve bu durum raporda açıkça belirtilmelidir.
- **Dosya sayısı:** 16 adet `.txt` (UTF-8) + 1 adet `etiketler.json` — 8 evrak türü × 2 örnek
- **Adlandırma şeması:** `<tur>_h1.txt`, `<tur>_h2.txt` (aynı 8 tür anahtarı)
- **Geliştirme setinden bilinçli farklılaşma:** Bağımsızlığı güçlendirmek için farklı bir kurgu kurum evreni (sahil belediyesi, il özel idaresi, devlet hastanesi, il sağlık müdürlüğü, gençlik ve spor il müdürlüğü, bölge müdürlüğü), farklı konular (çevre/kıyı işgali şikayeti, trafik cezası itirazı, sağlık personeli görevlendirme, afet koordinasyonu, yurt/burs işlemleri, kültür festivali) ve farklı üslup dokusu (maddesiz akan uzun paragraflar, nokta ayraçlı tarih biçimi `GG.AA.YYYY`, `Şb. Müd.`, `Yrd.`, `V.` gibi kısaltmalar) kullanılmıştır. 9 hedef birimin her biri en az 1 evrakta doğru yönlendirme hedefidir.
- **Kasıtlı eksik alanlar:** 4 dosyada (dilekçede imza+adres, cevap yazısında ilgi, tutanakta tarih, genelgede dağıtım) alanlar kasıtlı olarak eksik bırakılmış ve etiket dosyasına işlenmiştir; kalan 12 dosya tam alanlıdır.
- **Etiket formatı:** Geliştirme setiyle birebir aynı şema (`tur`, `birim_kodu`, `eksik_alanlar`, `aciklama`) ve aynı tür/birim/alan anahtar kümeleri.
- **Üretim yöntemi:** Sentetik — geliştirme setiyle aynı yöntemle, Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik'teki biçim öğeleri örnek alınarak takım tarafından elle yazılmıştır. Geçen tüm kişi, kurum, yer adı, sayı ve T.C. kimlik numaraları kurgudur; kurgu T.C. kimlik numaraları yalnızca checksum doğrulaması geçecek şekilde üretilmiştir ve gerçek kişilere ait değildir.
- **Kaynak:** Takım üretimi
- **Lisans:** Apache 2.0

Held-out ölçümü çalıştırma:

```bash
python3 scripts/evaluate.py \
    --veri-dizini data/raw/kurgu_evraklar_heldout \
    --rapor-dosyasi data/processed/eval_report_heldout.json
```

### 2b. Yeni Tutulmuş Set v2 (`raw/kurgu_evraklar_heldout_v2/`)

İlk held-out set üzerindeki tek turluk hata analizi ve ilkesel düzeltmeler sonrasında (bkz. `docs/teknik_rapor.md` §5, not 2) setin held-out niteliği zayıfladığından, **tamamen dokunulmamış** ikinci bir tutulmuş set oluşturulmuştur.

- **Amaç:** Sistemin genelleme başarımının güncel ve güvenilir kestirimi. Bu set kural geliştirme, kalibrasyon ve hata analizi süreçlerinin **hiçbir aşamasında kullanılmamıştır** ve **yalnızca bir kez ölçülmüştür**; üzerinde çıkan hatalar olduğu gibi raporlanmış, hiçbir kural düzeltmesi yapılmamıştır.
- **Dosya sayısı:** 16 adet `.txt` (UTF-8) + 1 adet `etiketler.json` — 8 evrak türü × 2 örnek
- **Adlandırma şeması:** `<tur>_v1.txt`, `<tur>_v2.txt` (aynı 8 tür anahtarı)
- **Önceki setlerden bilinçli farklılaşma:** Üçüncü bir kurgu kurum evreni (iç bozkır ili "Bozkırova" / "Sarpdere" ilçesi: valilik, il tarım ve orman müdürlüğü, il özel idaresi, belediye, kurgu "Dağyeli Teknik Üniversitesi", organize sanayi bölgesi müdürlüğü, bölge müdürlüğü), önceki setlerde hiç kullanılmamış konular (tarımsal sulama ücreti, mera işgali, karla mücadele/kış lojistiği, taşınır mal sayımı, siber olay tatbikatı, EBYS bakım kesintisi, OSB atıksu arıtma yatırımı, uluslararası öğrenci değişimi, gezici kütüphane) ve farklı üslup dokusu (gövde metinlerinde yazıyla tarih "9 Temmuz 2026", genelge/bilgilendirmede numaralı madde yapısı, raporda tire imli bulgu listeleri, `Uzm.`, `Müh.`, `İl Müdürü a.`, `Doç. Dr.` imza kısaltmaları) kullanılmıştır. 9 hedef birimin her biri en az 1 evrakta doğru yönlendirme hedefidir.
- **Kasıtlı eksik alanlar:** 6 dosyada, ilk held-out setin kullanmadığı alanlar da dahil olmak üzere kasıtlı eksikler vardır (dilekçede tc_kimlik+adres, üst yazıda sayı, cevap yazısında tarih, tutanakta katılımcılar, raporda hazırlayan, genelgede dağıtım); kalan 10 dosya tam alanlıdır.
- **Etiket formatı:** Diğer setlerle birebir aynı şema (`tur`, `birim_kodu`, `eksik_alanlar`, `aciklama`).
- **Üretim yöntemi:** Sentetik — diğer setlerle aynı yöntemle takım tarafından elle yazılmıştır. Geçen tüm kişi, kurum, yer adı, sayı ve T.C. kimlik numaraları kurgudur; kurgu T.C. kimlik numaraları yalnızca checksum doğrulaması geçecek şekilde üretilmiştir ve gerçek kişilere ait değildir.
- **Kaynak:** Takım üretimi
- **Lisans:** Apache 2.0

v2 ölçümü çalıştırma:

```bash
python3 scripts/evaluate.py \
    --veri-dizini data/raw/kurgu_evraklar_heldout_v2 \
    --rapor-dosyasi data/processed/eval_report_heldout_v2.json
```

### 3. Mevzuat Metinleri (`raw/mevzuat_metinleri/`)
- Kamuya açık mevzuat metinleri
- **Kaynak:** [mevzuat.gov.tr](https://mevzuat.gov.tr)
- **Lisans:** Kamu kullanımına açık

### 4. İşlenmiş Veriler (`processed/`)
- Ham verilerin temizlenmiş ve yapılandırılmış halleri
- Sınıflandırma etiketleri ve metadata
- Değerlendirme raporları: `eval_report.json` (geliştirme seti), `eval_report_heldout.json` (held-out set), `eval_report_heldout_v2.json` (yeni tutulmuş set v2)

## Kullanım Hakları

Tüm veri setleri açık kaynak lisans kapsamında kullanılmaktadır. Üçüncü taraf verilerin orijinal lisans koşullarına uyulmuştur.
