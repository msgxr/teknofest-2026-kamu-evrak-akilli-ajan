# Değişiklik Günlüğü (CHANGELOG)

Bu projedeki kayda değer tüm değişiklikler bu dosyada belgelenir.

Biçim [Keep a Changelog](https://keepachangelog.com/tr/1.1.0/) standardına,
sürümleme [Semantik Sürümleme](https://semver.org/lang/tr/) ilkelerine dayanır.

> **Şeffaflık notu:** Depoda henüz git etiketi (tag) bulunmadığından aşağıdaki
> sürüm numaraları, gerçek commit geçmişinin (bkz. `git log --oneline`)
> geriye dönük ve dürüst bir gruplamasıdır. Her bölümdeki commit kısaltmaları
> doğrulanabilir kanıttır; tarihler commit tarihlerinden alınmıştır.

## [Yayınlanmamış]

### Eklendi

- **TAKP aktarım provası + rozet (P2-12, şartname izi: m.7 açık kaynak):**
  `docs/takp_aktarim_plani.md` — doğrulanmış durum tespiti (resmî org
  github.com/tracikkaynak 2019'dan beri hareketsiz; resmî ekleme süreci
  dokümante değil; fiilî gelenek `turkiye-acik-kaynak-platformu`
  topic'i — bu repoda zaten ekli), üç senaryolu aktarım akışı (transfer/
  fork-mirror/topic) gh komutlarıyla, ön-aktarım kontrol listesi ve
  sorumlu+zamanlama. README'ye TAKP topic rozeti eklendi.
- **Kokpit tasarruf hesabı kaynaklı + parametrik (P2-11, şartname izi: Ticarileşme-15):**
  Evrak başına manuel işlem süresi artık `kokpit_ozeti(manuel_dakika=...)`
  parametresi ve arayüzdeki kaydırıcıyla (3-60 dk) kurumun KENDİ iş
  analizi ölçümüne göre ayarlanabilir; sonuçta `varsayim_mi` bayrağı
  taşınır. Literatür bağlamı doğrulanmış hakemli kaynakla verildi:
  Arslan & Kaya (2017, DergiPark) EBYS-öncesi ortalama ~4,7 saat/evrak
  (1-8 saat; beyana dayalı ölçüm) — varsayılan 12 dk bunun çok altında,
  bilinçli MUHAFAZAKÂR alt sınır olarak konumlandı (abartılı tasarruf
  iddiası riski önlendi). 3 yeni test; toplam 321/321 yeşil.
- **Demo Senaryosu 2.0 (P1-9, şartname izi: Demo-15):**
  4 sahneli jüri gösterimi (`demo/demo_scenario.py`): (1) dilekçe →
  cevap taslağı; (2) İVEDİ üst yazı → triyaj + yönlendirme (evrak
  çalışma anında bugünün tarihiyle üretilir — kalan-gün hesabı canlı
  kalır); (3) taranmış/gürültülü görüntü → OCR hattı (Pillow ile
  çalışma anında üretilir; OCR yığını yoksa dürüst bildirimle atlanır);
  (4) **"İNTERNETİ KES"** — tüm ağ soketleri programatik engellenirken
  aynı evrak yeniden işlenir (offline-first kanıtı, m.8 yedek plan
  tavsiyesinin cevabı). `--kayit` bayrağı konsol dökümünü dosyaya
  kaydeder (kayıt yedeği); demo sonunda ≤240 sn süre provası raporlanır.
  Sonuç panellerine madde-dayanaklı format denetimi, mevzuat madde
  etiketi+gerekçesi ve taslak kalite hakemi eklendi.
- **Adversarial tutulmuş set v3 + hata analizi (P1-7, şartname izi: Uygulama-35/veri çeşitliliği):**
  - 16 zorlayıcı kurgu evrak (dördüncü kurgu evren "Puslupınar/Kavakdüzü";
    8 tür × 2; 9 birimin tamamı hedef): bozuk sayı bloğu, kopuk İlgi
    zinciri, geçersiz/sözel tarihler, KVKK-yoğun içerik, yanlış bitişli
    vatandaş dilekçesi, çok konulu evraklar, iki yeni çift-doğalı olur.
  - Üretim çift-etiketlemeli: iki bağımsız yazar + çapraz kontrol; tek
    itiraz (v2 dosyasına yakın klon — held-out kontaminasyon riski) kabul
    edilip evrak yeniden yazıldı. Veri kartı `data/README.md` §2c.
  - **İLK ölçüm düzeltmesiz raporlandı** (12.07.2026): sınıflandırma 0,938 /
    yönlendirme 1,000 / eksik bilgi F1 0,667 / isabet@3 0,875 / kalite 95,8.
    Dört karışma deseni teknik rapor §5.1'de analiz edildi, §6 Sınırlılıklar
    beş somut maddeyle genişletildi (İlgi metinsel-varlık yanılması, sözel
    tarih, rapor iskelet bağımlılığı, KVKK tema-tetikleyici boşluğu,
    iyelik sinyali sınır durumu) — held-out bütünlüğü korundu.
  - `evaluate.py`'ye tür-bazlı **confusion matrix** eklendi
    (`siniflandirma.confusion_matrix`; 4 birim testi). Toplam 318/318 yeşil.
- **MCP entegrasyon vizyonu (P1-8, şartname izi: Yenilikçilik-15):**
  `docs/mcp_vizyonu.md` — mevcut REST API'nin Model Context Protocol
  araçlarına birebir eşlenmesi: mimari çizim, 5 araç şeması taslağı
  (evrak_isle, evrak_anonimlestir, birimleri_listele,
  evrak_turlerini_listele, sistem_sagligi), KVKK-varsayılan ve öneri-dili
  ilkeleri, ürünleşme yol haritası. Çalışan MCP sunucusu İDDİA EDİLMEZ
  (dürüst kapsam beyanı belgededir).
- **Bağımsız taslak kalite hakemi (P1-6, şartname izi: G2/Uygulama-35 kanıtı):**
  - `src/utils/taslak_hakemi.py`: taslaklar üretici ajandan bağımsız 0-100
    ölçeğinde puanlanır — LLM varsa dört boyutlu rubrik (LLM-as-judge),
    yoksa kural tabanlı eşdeğer (biçim %40 + üslup %30 + temellilik %30);
    iki yol aynı ölçeğe normalize.
  - **Mevzuat temellilik** her iki yolda deterministik (RAGAS-vari
    groundedness): öneri listesinde olmayan atıf halüsinasyon işareti
    sayılıp ağır cezalandırılır; zayıf-eşleşmeli atıf düşük puan alır.
  - Sonuç `taslak_kalitesi` anahtarıyla pipeline çıktısında;
    `evaluate.py` ortalama/asgari puan + hakem yöntemi dağılımı raporlar.
    Ölçüm (12.07.2026, kural hakem): ortalama 92,9 / 95,8 / 94,6.
  - 11 yeni test (`tests/test_taslak_hakemi.py`); toplam 314/314 yeşil.
- **İnsan Onayı Kuyruğu + KVKK varsayılan anonim görünüm (P0-5, şartname izi: yenilik/HITL):**
  - Streamlit'e "✋ İnsan Onayı Kuyruğu" sekmesi: düşük güvenli /
    gizlilik-kısıtlı kararlar kayıt defterinden gerekçeleriyle listelenir;
    **Onayla** veya **Düzelterek Kaydet** aksiyonları geri bildirim
    döngüsüne (`geri_bildirim.jsonl`, `aksiyon: onaylandi|duzeltildi`)
    yazılır — nihai karar insandadır (KVKK ÜYZ Rehberi ile hizalı).
  - Kayıt defteri şeması genişletildi: `insan_onayi_gerekce` sütunu
    (geriye uyumlu ALTER TABLE geçişiyle) + `sorgula(insan_onayi=...)`
    filtresi.
  - KVKK paylaşım nüshası artık **varsayılan görünüm** (açık expander);
    ham nüsha yalnızca "bilinçli erişim" expander'ı arkasında, KVKK m.12
    uyarısıyla gösterilir.
  - 3 yeni test (gerekçe saklama, filtre, eski şemadan geçiş); toplam 304/304.
- **Triyaj yasal-süre motoru sertifikasyonu (P0-4, şartname izi: yenilik/G1 destek):**
  - İş günü hesabına **sabit tarihli ulusal resmî tatiller** eklendi (2429
    sayılı Kanun: 1 Oca, 23 Nis, 1 May, 19 May, 15 Tem, 30 Ağu, 29 Eki);
    hicri takvime bağlı dinî bayramlar için **parametrik `resmi_tatiller`**
    kümesi (`TriageAgent(resmi_tatiller=...)`). Ek tatil verilmediğinde
    hesap ihtiyatlı (erken) taraftadır — süre kaçırma riski doğmaz.
  - Kenar-durum testleri: 15 Temmuz atlama, tatil+hafta sonu bileşimi,
    yıl geçişi (31 Ara→4 Oca), parametrik ek tatil + sabit tatil bileşimi,
    ajan üzerinden uçtan uca etki. Teknik rapora kaynaklı yasal süre
    dayanak tablosu (3071 m.7, 4982 m.11, 2577 m.7, CİMER, 2429) eklendi.
  - `_acik_sureler` içindeki `self` erişim hatası giderildi (staticmethod →
    instance method). 5 yeni test; toplam 301/301 yeşil.
- **Sayı üretici + üstveri↔belge tutarlılık doğrulayıcı (P0-3, şartname izi: G2/yenilik):**
  - `src/utils/sayi_uretici.py`: m.11 biçimli (E-DETSİS-SDP-kayıt) kurgu
    sayı üretimi — kurum adından deterministik 8 haneli kurgu Devlet
    Teşkilatı Numarası; gerçek DETSİS/SDP kayıtlarıyla eşleşme iddia
    edilmez. Taslaklara sayı yazılmaz (dürüst EBYS ibaresi korunur);
    üstverideki `sayi_onerisi` alanını besler.
  - `uret_ustveri` artık belge metnini alır: Sayı/Konu/tarih/gizlilik
    üstveriye belge görüntüsünden BİREBİR taşınır; yeni
    `ustveri_belge_tutarliligi` doğrulayıcısı **m.28/3 ilkesini**
    ("belge görüntüsü ile üstveri arasında fark olamaz") otomatik
    denetime çevirir ve Streamlit'te sonuç rozetiyle gösterilir.
  - Ortak yazışma desenleri tek modülde toplandı
    (`src/utils/yazisma_desenleri.py`); format denetçisi ve üstveri
    doğrulayıcı aynı doğruluk kaynağını kullanır. 15 yeni birim test
    (`tests/test_sayi_ustveri.py`).
- **Madde-referanslı format denetçisi (P0-2, şartname izi: G2-b):**
  - Her denetim kuralı `{kural_id, kural, durum, detay, dayanak, agirlik}`
    şemasına taşındı; dayanaklar 2646 sayılı Yönetmeliğin RESMÎ metninden
    fıkra düzeyinde doğrulandı (mevzuat.gov.tr + tccb.gov.tr çapraz
    kontrol) — jüri önünde madde gösterilebilir. Skor ağırlıklı ortalama;
    koşullu kurallar bağlam yokken listeye eklenmez (haksız ceza yok).
  - Yeni kurallar: sayı biçimi E-DETSİS-SDP-kayıt (m.11/1-2; dürüst EBYS
    ibaresi kabul), konu kısa-öz (m.13/2), **bitiş ifadesi ↔ muhatap
    hiyerarşisi tutarlılığı** (m.16/12-a — denk makama da 'arz'), yabancı
    kelime uyarısı (m.16/8), 'a)' maddeleme biçimi (m.16/10), yetki devri
    imza düzeni (m.17/9), **gizlilik damgalı evrakta kısıtlı mod** (m.25:
    damga taslağa taşınmalı + insan onayı işareti).
  - Kapanış seçimi hiyerarşi-farkında yapıldı: muhatap/gönderen kademeleri
    tespit edilebiliyorsa m.16/12-a esas alınır (önceki davranış denk
    makama 'rica' varsayıyordu — yönetmeliğe göre düzeltildi).
  - Streamlit ve HTML işlem raporunda her kuralın yanında dayanak
    (madde/fıkra) gösterilir. 29 yeni birim test (`tests/test_draft_writer.py`).
- **Hibrit mevzuat RAG'i (P0-1, şartname izi: G1-e):**
  - Mevzuat önerileri artık **madde referanslı ve gerekçeli**: her öneri
    `{mevzuat_adi, madde_no, madde_etiketi, gerekce, benzerlik, doc_id, bolum}`
    alanlarını taşır; gerekçe yalnızca gözlenen eşleşme sinyallerinden
    (ortak ayırt edici terimler, tür önceliği, aktif alan teması) kurulur.
  - **Düzeltici (corrective) sorgu genişletme döngüsü:** en iyi önerinin
    benzerliği düzeltme tetiğinin (0.15; geliştirme setiyle kalibre)
    altında kalırsa sorgu, evrak türünün usul söz dağarcığıyla bir kez
    genişletilip arama yinelenir ve yalnızca benzerlik iyileşirse benimsenir
    (Singh vd. 2025, arXiv:2501.09136; Li vd. 2025, arXiv:2507.09477).
    Döngü kaydı pipeline çıktısındaki `mevzuat_arama_meta` alanında
    izlenebilir; mutlak benzerlik ölçeği ve `zayif_esleme` işaretiyle uyumludur.
  - **Opsiyonel yoğun (dense) katman:** `EMBEDDING_SEMANTIK_AKTIF=1` ile
    turkish-e5-large adayları BM25 ile puan birleşimine girer;
    `EMBEDDING_RERANK_AKTIF=1` ile bge-reranker-v2-m3 aday havuzunu yeniden
    sıralar (`src/utils/semantik_arama.py`). Katmanlar varsayılan kapalıdır
    ve yokluklarında salt-BM25 davranışı birebir korunur (offline-first).
- **Mevzuat isabet@3 metriği (`scripts/evaluate.py`):** etiketlerdeki
  opsiyonel `mevzuat_beklenen` doc_id listesine karşı isabet@3 / isabet@1
  oranları ve kaçırılanlar listesi raporlanır; saf Python metrik
  fonksiyonları birim testlidir.
- Etiket şemasına opsiyonel `mevzuat_beklenen` alanı (üç veri setinde,
  çift aşamalı etiketleme: etiketleyici + bağımsız doğrulayıcı; gerekçeler
  `data/raw/mevzuat_beklenen_gerekceleri.json`).
- Birim testler: `tests/test_legislation.py` (madde çıkarımı, öneri
  şeması, usul mevzuatı garantisi, düzeltici döngü, hibrit puan birleşimi,
  opsiyonel katman zarif düşüşü) ve `tests/test_evaluation.py` isabet@k testleri.
- GitHub Actions CI iş akışı (`.github/workflows/ci.yml`): Python 3.9 + 3.12
  matrisinde derleme denetimi, tüm test paketi ve 5 evraklık hızlı değerlendirme smoke'u.
- Katkı rehberi (`CONTRIBUTING.md`) ve mimari genişletme rehberi
  (`docs/gelistirici_rehberi.md`).
- `Dockerfile` + `.dockerignore` (container ile çalıştırma seçeneği; imaj
  yayınlanmaz, Dockerfile sağlanır) ve tek komut başlatma betiği `baslat.sh`.
- Bu değişiklik günlüğü (`CHANGELOG.md`).

### Düzeltildi

- HTML işlem raporunda format denetim kontrolleri `durum` anahtarını
  okumadığından tüm kurallar ✗ görünüyordu — durum okuma zinciri
  düzeltildi (`src/utils/islem_raporu.py`).

### Değiştirildi

- ChromaDB araması birincil yol olmaktan çıkarıldı; yalnızca BM25 indeksi
  kurulamadığında denenen **yedek yol** oldu (önceden kuruluysa BM25'i
  tamamen atlıyordu — hibrit tasarımla bu zayıflık giderildi).
- `AgentState`'e `legislation_meta` izlenebilirlik alanı eklendi;
  pipeline çıktısına `mevzuat_arama_meta` anahtarı yansır.
- `docs/model_bilgileri.md` hibrit RAG modelleriyle güncellendi
  (turkish-e5-large: MIT; bge-reranker-v2-m3: Apache 2.0 — bağlantı,
  sürüm, lisans ve kullanım talimatıyla; ağırlıklar depoya yüklenmez).

## [0.4.0] — 2026-07-11 (kalite, üçlü ensemble ve entegrasyon yetenekleri)

### Eklendi
- Hibrit **üçlü sınıflandırma ensemble'ı**: kural tabanlı skorlama + saf-Python
  Naive Bayes + opsiyonel LLM (`474f621`).
- **SQLite evrak kayıt defteri** (denetim izi) ve kendine yeten HTML işlem
  raporu (`163b903`).
- **Sıfır bağımlılıklı REST API** (`python -m src.api`) — EBYS entegrasyonu
  için servis ucu (`11a17c3`).
- **Evrak ilişki zinciri** (İlgi referanslarından yazışma zinciri kurma) ve
  aktif öğrenme kalibrasyon önerileri (`b57e011`).
- Benchmark paketi: ~92 evrak/sn, p95 14 ms (`81ae57e`).

### Düzeltildi
- Türkçe ünsüz yumuşaması desteği ve cümle bölme sağlamlaştırması (`f4d2359`).
- Morfolojik eşleşme, evrak "Sayı"sı ile İlgi atıf numarasının ayrımı,
  içerik-farkında olur yönlendirmesi (`7afc4aa`).
- KVKK anonimleştirmede kişi adı sızıntısı — üç yeni yakalama katmanı (`c27210d`).
- Özet/taslakta cümle bütünlüğü ve resmî üslup rötuşları (`fede399`).
- Mevzuat/triage: mutlak benzerlik ölçeği + başvuru-niteliği koşulu (`c91fdf3`).

### Değiştirildi
- Kişisel veri alanları açıkça-kurgu değerlere çevrildi (`9f1393f`).
- Uyum matrisi, teknik rapor ve README güncel mimariyle hizalandı (`74e7b5a`).

## [0.3.0] — 2026-07-11 (yenilik ajanları: 9 → 11 ajan)

### Eklendi
- **Akıllı önceliklendirme (triage) ajanı**: İVEDİ/GÜNLÜDÜR damgaları ve yasal
  sürelerden (4982, 3071, 2577, CİMER) son işlem tarihi hesabı (`ebd410e`).
- **KVKK anonimleştirme ajanı**: kişisel verileri (TC, ad, telefon, IBAN,
  adres) maskeleyen paylaşım nüshası (`65e9a1a`).
- Kurum kokpiti (toplu işleme + dağılım analizleri), e-Yazışma üstverisi ve
  geri bildirim döngüsü (`208afd7`).
- Yenilik ajanlarının orkestratör entegrasyonu — 9 ajandan 11 ajana (`cd1afa1`).

### Değiştirildi
- Güvenlik denetimi ve sertleştirmeler (girdi sınırı, hata sızıntısı önleme
  vb.) yayın öncesi uygulandı (`cca0d97`).

## [0.2.0] — 2026-07-11 (çekirdek sistem: uçtan uca çalışan iki görev)

### Eklendi
- Model-agnostik LLM katmanı: stdlib `urllib` ile OpenAI-uyumlu API / Ollama /
  offline otomatik tespit (`7b4e5f9`).
- Koşullu akışlı saf Python orkestratör + Türkçe dil sezimi (`bfbeb7b`).
- **Görev 1 ajanları**: sınıflandırma, bilgi çıkarımı, eksik bilgi tespiti,
  özetleme (`9a0f937`).
- **Görev 2 ajanları**: yönetmelik uyumlu taslak yazımı, birim yönlendirme,
  kullanıcı bilgilendirme (`c7ec3e6`).
- BM25 tabanlı mevzuat RAG — 15 belgelik kamuya açık mevzuat korpusu (`441a143`).
- Etiketli sentetik veri setleri: 35 geliştirme + 16 tutulmuş evrak (`54dd23d`);
  tutulmuş set v2 (16 evrak, üçüncü kurgu evren) (`d412378`).
- Değerlendirme aracı (`scripts/evaluate.py`) ve başarım raporları (`f7027f0`).
- Streamlit demo arayüzü (`342ab89`) ve genişletilmiş demo senaryosu (`ff96bf0`).
- Ön değerlendirme sunumu (12 slayt) ve PPTX üretim aracı (`a5d8b90`).

### Değiştirildi
- Teknik rapor, README ve model bilgileri gerçek durumla hizalandı (`bde54b0`);
  v2 sonuçları ve şartname uyum matrisi işlendi (`c222ba9`).

## [0.1.0] — 2026-07-10 (proje iskeleti)

### Eklendi
- İlk commit: proje yapısı, README, lisans (Apache 2.0), bağımlılık ayrımı ve
  temel iskelet — TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması,
  1. Senaryo (`3ecf3c4`).
