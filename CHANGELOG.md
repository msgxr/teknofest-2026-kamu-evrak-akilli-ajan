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
