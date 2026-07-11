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
- GitHub Actions CI iş akışı (`.github/workflows/ci.yml`): Python 3.9 + 3.12
  matrisinde derleme denetimi, tüm test paketi ve 5 evraklık hızlı değerlendirme smoke'u.
- Katkı rehberi (`CONTRIBUTING.md`) ve mimari genişletme rehberi
  (`docs/gelistirici_rehberi.md`).
- `Dockerfile` + `.dockerignore` (container ile çalıştırma seçeneği; imaj
  yayınlanmaz, Dockerfile sağlanır) ve tek komut başlatma betiği `baslat.sh`.
- Bu değişiklik günlüğü (`CHANGELOG.md`).

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
