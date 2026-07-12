# Teknofest 2026 — Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi

<div align="center">

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Mimari](https://img.shields.io/badge/Mimari-Özgün_Çok--Ajanlı_Orkestrasyon_(saf_Python)-FF6F00?style=for-the-badge)
![License](https://img.shields.io/badge/License-Apache_2.0-green?style=for-the-badge)
![TEKNOFEST](https://img.shields.io/badge/TEKNOFEST-2026-red?style=for-the-badge)
[![CI](https://github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan/actions/workflows/ci.yml/badge.svg)](https://github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan/actions/workflows/ci.yml)
[![TAKP](https://img.shields.io/badge/T%C3%BCrkiye_A%C3%A7%C4%B1k_Kaynak_Platformu-topic-E30A17?style=for-the-badge)](https://github.com/topics/turkiye-acik-kaynak-platformu)

**Yapay Zeka Dil Ajanları Yarışması — 1. Senaryo**

*Kamu kurumlarındaki evrak işleme ve resmi yazışma süreçlerini yapay zeka destekli çok ajanlı bir sistemle otomatikleştiren akıllı agent çözümü.*

</div>

---

## 📋 İçindekiler

- [Proje Hakkında](#-proje-hakkında)
- [Özellikler](#-özellikler)
- [Sistem Mimarisi](#-sistem-mimarisi)
- [Kurulum](#-kurulum)
- [Kullanım](#-kullanım)
- [Proje Yapısı](#-proje-yapısı)
- [Görevler](#-görevler)
- [Veri Kullanımı](#-veri-kullanımı)
- [Test](#-test)
- [Demo](#-demo)
- [Katkıda Bulunma](#-katkıda-bulunma)
- [Lisans](#-lisans)
- [Takım](#-takım)

---

## 🎯 Proje Hakkında

Bu proje, **TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması** kapsamında geliştirilmektedir. Kamu kurumlarında günlük işleyişin önemli bir bölümünü oluşturan evrak hazırlama, inceleme, yönlendirme, yazışma üretimi ve arşivleme süreçlerinin yapay zeka destekli akıllı ajan sistemleriyle yeniden tasarlanmasını hedefler.

### Problem

Kamu kurumlarındaki evrak ve yazışma süreçleri:
- Çok adımlı, tekrarlı ve manuel müdahale gerektiren işlemlerden oluşur
- Zaman baskısı altında yürütülür
- Farklı personeller tarafından yönetilir, bu da iş yükünün dağılmasına ve sürelerin uzamasına neden olur

### Çözüm

Çok ajanlı (multi-agent) bir yapay zeka sistemi ile:
- 🔍 Evrak okuma, anlamlandırma ve sınıflandırma
- 📚 Mevzuat eşleştirme ve öneri
- ✍️ Resmi yazı taslağı oluşturma
- 🏢 Doğru birime yönlendirme
- ⚠️ Eksik bilgi tespiti ve kullanıcı bilgilendirme

---

## ✨ Özellikler

| Özellik | Açıklama |
|---------|----------|
| 📄 **Metin/PDF/Görüntü Okuma** | TXT ve metin katmanlı PDF çekirdekte; taranmış PDF/görüntü için opsiyonel OCR (Tesseract) |
| 🏷️ **Otomatik Sınıflandırma** | Evrak türünü (dilekçe, üst yazı, cevap, tutanak vb.) kural tabanlı skorlama ile belirleme; düşük güvende opsiyonel LLM eskalasyonu |
| 🔍 **Bilgi Çıkarımı** | Tarih, kurum, konu, muhatap gibi anahtar bilgileri çıkarma |
| ⚠️ **Eksik Bilgi Tespiti** | Evrakta olması gereken ancak eksik alanları tespit etme |
| 📚 **Hibrit Mevzuat RAG** | Saf Python BM25-Okapi çekirdeği ile **madde referanslı + gerekçeli** mevzuat önerisi; düşük skorda tür söz dağarcığıyla düzeltici (corrective) sorgu genişletme döngüsü; opsiyonel turkish-e5-large semantik katman + bge-reranker yeniden sıralama |
| 📝 **Özet Oluşturma** | Evrakın kısa ve öz özetini üretme |
| ✍️ **Yazı Taslaklama + Madde-Referanslı Format Öz-Denetimi** | Resmi üsluba uygun taslak üretme ve **her kuralı yönetmelik madde/fıkra dayanağıyla** denetleme (Yön. 2646: sayı biçimi m.11, bitiş↔hiyerarşi m.16/12, maddeleme m.16/10, gizlilik kısıtlı modu m.25...); ağırlıklı skor + jüri önünde madde gösterilebilirlik |
| ❓ **Eksik Bilgi Talep Yazısı** | Taslak tamamlanamıyorsa eksik bilgileri gerekçeli sorularla talep eden yazı üretme |
| 🏢 **Birim Yönlendirme** | Ağırlıklı sinyal skorlaması ile doğru birime yönlendirme; gerekçe + alternatifler; yakın skorda opsiyonel LLM ayrıştırması |
| 💬 **Kullanıcı Bilgilendirme** | Süreç hakkında açık bilgilendirme mesajları |
| 🔌 **Offline-First Çalışma** | LLM/İnternet olmadan tüm ajanlar kural tabanlı yollarla uçtan uca tam işlevli |
| ⏱️ **Adım Süreleri** | Her ajan adımının süresi ölçülüp raporlanır (gerçek zamana yakın çalışma kanıtı) |
| 🤖 **Çok Ajanlı Mimari** | 11 uzman ajanın framework bağımsız, saf Python orkestratör ile koordinasyonu |
| ⏰ **Akıllı Önceliklendirme** | İVEDİ/GÜNLÜDÜR damgaları + yasal sürelerden (4982, 3071, 2577, CİMER) son işlem tarihi hesabı |
| 🔒 **KVKK Paylaşım Nüshası** | Kişisel verileri (TC, ad, telefon, IBAN, adres) maskeleyen anonimleştirilmiş kopya |
| 📊 **Kurum Kokpiti** | Toplu evrak işleme; tür/birim dağılımları, eksiklik oranları ve zaman tasarrufu analizi |
| 📦 **e-Yazışma Üstverisi + m.28/3 Tutarlılık Denetimi** | EBYS entegrasyon vizyonlu üstveri taslağı (CBDDO e-Yazışma esinli); üstveri↔belge görüntüsü **birebir eşitlik denetimi** (Yön. m.28/3'ün otomasyonu) + m.11 biçimli kurgu sayı önerisi (`src/utils/sayi_uretici.py`) |
| ✍️ **Geri Bildirim Döngüsü** | Kullanıcı düzeltmeleri kayıt altına alınır; kalibrasyon önerileri üretilir (`scripts/kalibrasyon_onerisi.py`) |
| ⚖️ **Taslak Kalite Hakemi** | Üretici ajandan bağımsız 0-100 puanlama: LLM varsa rubrik (LLM-as-judge), yoksa kural tabanlı eşdeğer; RAGAS-vari **mevzuat temellilik** denetimi (öneri listesinde olmayan atıf = halüsinasyon işareti) |
| ✋ **İnsan Onayı Kuyruğu (HITL)** | Düşük güvenli / gizlilik-kısıtlı kararlar gerekçeleriyle kuyruğa düşer; Onayla/Düzelt aksiyonları geri bildirim döngüsüne yazılır — nihai karar insandadır; KVKK nüshası varsayılan görünüm, ham metin bilinçli erişimle |
| 🧠 **Hibrit ML Ensemble** | Kural + saf-Python Naive Bayes + opsiyonel LLM üçlü sınıflandırma (`src/models/istatistiksel_siniflandirici.py`) |
| 🗂️ **Evrak Kayıt Defteri** | SQLite denetim izi: her işlem kayıt altında, filtreli sorgu + istatistik |
| 🌐 **REST API** | Sıfır bağımlılıklı JSON API (`python -m src.api`) — EBYS entegrasyonu için servis ucu |
| 🔗 **Evrak İlişki Zinciri** | İlgi referanslarından yazışma zincirlerini (dilekçe → cevap) otomatik kurar |
| 📑 **HTML İşlem Raporu** | Arşive/denetime verilebilir, kendine yeten işlem denetim raporu |
| 🚀 **Performans Karnesi** | ~88 evrak/sn, p95 14 ms (`scripts/benchmark.py` ile yeniden üretilebilir) |

---

## 🏗️ Sistem Mimarisi

Sistem, **framework bağımsız, stdlib tabanlı özgün bir orkestrasyon** üzerine kuruludur: LangGraph/LangChain gibi bir agent framework'ü **kullanılmaz**. Orkestratör (`src/agents/orchestrator.py`), 11 uzman ajanı paylaşılan bir durum nesnesi (`AgentState`) üzerinde sırayla çalıştırır, her adımın süresini ve güven skorunu izler. LLM **opsiyoneldir**: OpenAI-uyumlu bir API veya yerel Ollama bulunursa yalnızca düşük güvenli kararlarda devreye girer; bulunmazsa sistem tamamen kural tabanlı modda uçtan uca çalışır.

```
┌─────────────────────────────────────────────────────────────┐
│                    📥 EVRAK GİRİŞİ                           │
│   (TXT / PDF metin katmanı; taranmış PDF-görüntü için        │
│    opsiyonel OCR)                                            │
└─────────────────┬───────────────────────────────────────────┘
                  ▼
┌─────────────────────────────────────────────────────────────┐
│   🧠 ORKESTRATÖR (saf Python, paylaşılan AgentState)         │
│   Adım süresi + güven izleme, hata toleransı                 │
└─────────────────┬───────────────────────────────────────────┘
                  ▼
        🔤 OCR / Metin Okuma Agent
                  │
        🚦 KOŞULLU KAPILAR
        ├─ Boş/okunamayan metin → süreç erken sonlanır,
        │  kullanıcı bilgilendirilir
        ├─ Dil sezimi → Türkçe olmayan girdi için uyarı
        └─ Düşük sınıflandırma güveni → insan onayı işareti
                  ▼
  GÖREV 1 — Sınıflandırma ve İçerik Analizi (sırayla)
  🏷️ Sınıflandırma (kural tabanlı skorlama;
      güven < 0.6 ve LLM varsa → LLM eskalasyonu)
  🔍 Bilgi Çıkarım → ⚠️ Eksik Bilgi Tespiti
  📚 Mevzuat Önerisi (hibrit BM25 RAG: madde referansı + gerekçe;
      düşük skorda düzeltici sorgu genişletme döngüsü) → 📝 Özet
                  ▼
  GÖREV 2 — Taslak ve Yönlendirme (sırayla)
  ✍️ Taslak Agent (+ format öz-denetimi: kontrol listesi + skor)
  🏢 Yönlendirme (ağırlıklı sinyal skorlaması;
      skorlar yakın ve LLM varsa → LLM ayrıştırması)
  💬 Kullanıcı Bilgilendirme + ❓ Eksik Bilgi Talebi
                  ▼
┌─────────────────────────────────────────────────────────────┐
│                      📤 ÇIKTILAR                             │
│  Sınıflandırma | Bilgi Çıkarım | Eksik Bilgi | Özet          │
│  Mevzuat Önerisi | Yazı Taslağı + Format Denetimi            │
│  Birim Yönlendirme | Bilgilendirme | Adım Süreleri           │
└─────────────────────────────────────────────────────────────┘
```

### Teknoloji Yığını

| Katman | Gerçekleşme |
|--------|-------------|
| Orkestrasyon | Özgün, saf Python (stdlib `dataclasses` + `time`); agent framework'ü **yok** |
| LLM erişimi (opsiyonel) | stdlib `urllib` ile OpenAI-uyumlu API (varsayılan `gpt-4o-mini`) veya yerel Ollama (varsayılan `qwen2.5:7b`); SDK bağımlılığı yok |
| Mevzuat RAG | Hibrit: saf Python BM25-Okapi (`src/utils/bm25.py`, çekirdek) + düzeltici sorgu genişletme; opsiyonel turkish-e5-large semantik arama ve bge-reranker-v2-m3 yeniden sıralama (`src/utils/semantik_arama.py`, `EMBEDDING_SEMANTIK_AKTIF=1` / `EMBEDDING_RERANK_AKTIF=1`) |
| Evrak okuma | TXT + pypdf (çekirdek); pytesseract/pdf2image/easyocr (opsiyonel OCR) |
| Arayüz | Streamlit (web) + rich (konsol) |
| Bağımlılık ayrımı | `requirements.txt` (çekirdek — sistem bunlarla TAM çalışır) / `requirements-optional.txt` (OCR, semantik arama, yerel model) — LangChain/LangGraph/torch çekirdekte **yer almaz** |

---

## ⚡ Hızlı Başlangıç

Bağımlılıklar kuruluysa (`pip install -r requirements.txt`) tek komut yeterlidir:

```bash
./baslat.sh          # Streamlit web arayüzü (http://localhost:8501)
./baslat.sh --api    # REST API (http://127.0.0.1:8765)
```

Container ile çalıştırmak isteyenler için hazır imaj yayınlanmaz; **Dockerfile sağlanır**:

```bash
docker build -t kamu-evrak-ajan .
docker run --rm -p 8501:8501 kamu-evrak-ajan
```

---

## 🚀 Kurulum

### Gereksinimler

- Python 3.9 veya üzeri
- pip

### Adımlar

```bash
# 1. Depoyu klonlayın
git clone https://github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan.git
cd teknofest-2026-kamu-evrak-akilli-ajan

# 2. Sanal ortam oluşturun
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 3. Çekirdek bağımlılıkları yükleyin (sistem bunlarla TAM çalışır)
pip install -r requirements.txt

# 3b. (Opsiyonel) OCR, semantik arama, yerel model yetenekleri için
pip install -r requirements-optional.txt

# 4. (Opsiyonel) LLM kullanacaksanız ortam değişkenlerini ayarlayın
#    LLM tanımlanmazsa sistem kural tabanlı modda tam işlevli çalışır.
cp .env.example .env    # Windows: copy .env.example .env
# .env içinde OPENAI_API_KEY tanımlayın veya yerel Ollama başlatın

# 5. Örnek bir evrak işleyerek kurulumu doğrulayın
python -m src.main --input data/raw/kurgu_evraklar/dilekce_01.txt
```

---

## 📖 Kullanım

### Komut Satırı

```bash
# Tek bir evrak işleme (etiketli kurgu evraklar data/raw/kurgu_evraklar/ altındadır)
python -m src.main --input data/raw/kurgu_evraklar/dilekce_01.txt

# Çalışma modu seçimi: full (varsayılan) / classify (Görev 1) / draft (Görev 2)
python -m src.main --input data/raw/kurgu_evraklar/ust_yazi_01.txt --mode classify

# Demo senaryosu çalıştırma (3 farklı evrak türü, uçtan uca)
python -m src.main --demo
# veya doğrudan:
python demo/demo_scenario.py

# Streamlit web arayüzü
streamlit run src/app.py

# Ölçülebilir başarım raporu (52 etiketli evrak üzerinde
# sınıflandırma / yönlendirme / eksik bilgi / süre metrikleri)
python scripts/evaluate.py
```

### Python API

`pipeline.process()` bir **sözlük (dict)** döndürür; tüm sonuç alanlarına anahtarla erişilir.

```python
from src.pipelines.end_to_end_pipeline import EndToEndPipeline

# Pipeline oluştur
pipeline = EndToEndPipeline()

# Dosyadan evrak işle (TXT / PDF; OCR bağımlılıkları kuruluysa PNG/JPG)
sonuc = pipeline.process("data/raw/kurgu_evraklar/dilekce_01.txt")

# Sonuçları görüntüle (dict erişimi)
print(sonuc["siniflandirma"]["tur_adi"])   # Evrak türü (ör. "Dilekçe")
print(sonuc["siniflandirma"]["guven"])     # Güven skoru (0-1)
print(sonuc["ozet"])                       # Evrak özeti
print(sonuc["yazi_taslagi"])               # Resmi yazı taslağı
print(sonuc["yonlendirme"]["birim"])       # Birim yönlendirme önerisi
print(sonuc["islem_adimlari"])             # Adım adım süre/durum kaydı

# Dosya olmadan doğrudan metin işleme
sonuc = pipeline.orchestrator.process_text(
    "Sayın Yazı İşleri Müdürlüğüne,\n\nDilekçeme ilişkin bilgi talep ediyorum. Arz ederim."
)
print(sonuc["siniflandirma"]["tur"])
```

---

## 📁 Proje Yapısı

```
teknofest-2026-kamu-evrak-akilli-ajan/
├── README.md                       # Bu dosya
├── LICENSE                         # Apache 2.0 Lisansı
├── requirements.txt                # Çekirdek bağımlılıklar (sistem bunlarla TAM çalışır)
├── requirements-optional.txt       # Opsiyonel bağımlılıklar (OCR, semantik arama, yerel model)
├── pyproject.toml                  # Proje konfigürasyonu
├── .gitignore                      # Git ignore kuralları
├── .env.example                    # Ortam değişkenleri örneği (LLM opsiyonel)
├── docs/                           # Dokümantasyon (teknik rapor, model bilgileri)
├── src/                            # Kaynak kodu
│   ├── agents/                     # Agent modülleri (orkestratör + 11 uzman ajan)
│   ├── models/                     # LLM wrapper (stdlib, OpenAI-uyumlu/Ollama)
│   ├── pipelines/                  # İş akışları
│   ├── utils/                      # Yardımcı araçlar (BM25, Türkçe NLP, kokpit, e-Yazışma üstverisi)
│   ├── templates/                  # Yazı şablonları
│   ├── app.py                      # Streamlit web arayüzü
│   └── main.py                     # Komut satırı giriş noktası
├── data/                           # Veri setleri (52 geliştirme + 48 tutulmuş kurgu evrak + mevzuat)
├── scripts/                        # Değerlendirme aracı (evaluate.py)
├── tests/                          # Test dosyaları
├── demo/                           # Demo senaryoları
└── presentations/                  # Sunumlar
```

---

## 🎯 Görevler

### Görev 1: Evrak Sınıflandırma ve İçerik Analizi

Kuruma ulaşan evrakın ilk inceleme ve değerlendirme aşamasını yapay zeka ile otomatikleştirme:
- OCR ile evrak okuma
- Evrak türü belirleme
- Anahtar bilgi çıkarma
- Eksik bilgi tespiti
- Mevzuat önerisi
- Özet oluşturma

### Görev 2: Resmi Yazı Taslaklama ve Birim Yönlendirme

Evrakın işleme alınması sonrasında uygun resmi yazı taslağı oluşturma ve birim yönlendirme:
- Resmi yazı taslağı oluşturma (üst yazı, cevap, bilgilendirme vb.)
- Resmi üslup uygunluğu
- Doğru birime yönlendirme
- Kullanıcı bilgilendirme
- Eksik bilgi talebi

---

## 📊 Veri Kullanımı

Bu projede **gerçek kamu verisi kullanılmamaktadır**. Aşağıdaki veri kaynakları kullanılmaktadır:
- ✅ Açık kaynak metinler
- ✅ Kurgu evrak örnekleri
- ✅ Yapay olarak oluşturulmuş resmi yazışma taslakları
- ✅ Kamuya açık mevzuat metinleri (mevzuat.gov.tr)

Veri setlerinin kaynak ve kullanım hakları `data/README.md` dosyasında detaylı olarak açıklanmıştır.

---

## 🧪 Test

```bash
# Tüm testleri çalıştır
pytest tests/

# Belirli bir test modülünü çalıştır
pytest tests/test_classification.py

# Kapsama raporu ile
pytest tests/ --cov=src --cov-report=html
```

---

## 📈 Başarım

Etiketli sentetik setlerde, tamamen çevrimdışı (kural tabanlı) modda ölçülmüştür
(`python scripts/evaluate.py`; ayrıntı ve metodolojik notlar: [docs/teknik_rapor.md](docs/teknik_rapor.md)):

| Metrik | Geliştirme seti (52 evrak) | Tutulmuş set (16 evrak) | Tutulmuş set v2 (16 evrak) |
|---|---|---|---|
| Sınıflandırma doğruluğu | 1.000 | 1.000 | 1.000 |
| Birim yönlendirme doğruluğu | 0.962 | 1.000 | 0.938 |
| Eksik bilgi tespiti (micro-F1) | 1.000 | 1.000 | 1.000 |
| Mevzuat önerisi isabet@3 | 0.962 | 0.875 | 0.750 |
| Taslak kalitesi (bağımsız hakem, 0-100) | 93.6 | 95.8 | 94.6 |
| Evrak başına medyan süre | 0.011 sn | 0.012 sn | 0.012 sn |

**Adversarial dayanıklılık (tutulmuş set v3, 16 zorlayıcı evrak — İLK ölçüm, düzeltmesiz):**
sınıflandırma 0.938 · **yönlendirme 1.000** · eksik bilgi micro-F1 0.667 · mevzuat isabet@3 0.875 ·
taslak kalitesi 95.8 — bozuk sayı bloğu, kopuk İlgi zinciri, sözel tarih, KVKK-yoğun içerik ve
çift-doğalı olurlara karşı ölçülmüştür; hata desenleri [teknik raporda](docs/teknik_rapor.md) §5.1'de
analiz edilmiş, held-out bütünlüğü gereği düzeltme YAPILMAMIŞTIR.

Benchmark (84 evrak × 5 tekrar, tek çekirdek, çevrimdışı): **~88 evrak/saniye**, gecikme medyan 11.3 ms / p95 14.2 ms — ayrıntı: [docs/performans_raporu.md](docs/performans_raporu.md).

> Not: Geliştirme seti kural kalibrasyonunda kullanılmıştır. Tutulmuş set v2'nin
> İLK ölçümü 1.000 / 0.875 / 0.857 idi; hata analizinde bulunan iki kök neden
> (Türkçe ünsüz yumuşamasının eşleştiricide hesaba katılmaması ve belge "Sayı"sı ile
> İlgi atıf numarasının ayrıştırılmaması) dosyaya özgü ezber olmadan, **ilkesel**
> düzeltmelerle giderilmiş ve tablo yeniden ölçülmüştür (ayrıntılı geçmiş:
> [docs/teknik_rapor.md](docs/teknik_rapor.md) §5). Kalan tek yönlendirme farkı,
> raporda analiz edilen bilinen bir sınır durumudur (çift-doğalı makam oluru).
> `mevzuat_beklenen` etiketleri sistem çıktısına bakılmadan, içerik + hukuki kural
> rehberiyle atanmıştır (bkz. `data/README.md`).
> Sentetik set ölçeği sınırlıdır; düşük güvenli kararlar "insan onayı gerekli"
> işaretiyle döner.

---

## 🎬 Demo

Demo senaryosu farklı evrak türleri üzerinde sistemin uçtan uca çalışmasını gösterir:

```bash
python demo/demo_scenario.py
```

Demo hakkında detaylı bilgi için `demo/README.md` dosyasına bakınız.

---

## 🔧 Katkı ve Sürdürülebilirlik

Proje, sürdürülebilir açık kaynak geliştirme için gerekli altyapıyla gelir:

- **CI**: Her push/PR'da GitHub Actions, Python 3.9 ve 3.12 üzerinde derleme denetimi, tüm test paketini ve 5 evraklık hızlı değerlendirme smoke'unu çalıştırır ([.github/workflows/ci.yml](.github/workflows/ci.yml)).
- **Katkı kuralları**: Kurulum, üslup, dal/commit düzeni ve değerlendirme bütünlüğü kuralları için [CONTRIBUTING.md](CONTRIBUTING.md).
- **Mimari genişletme**: Yeni ajan / evrak türü / birim / mevzuat belgesi / API ucu ekleme adımları gerçek dosya-satır referanslarıyla [docs/gelistirici_rehberi.md](docs/gelistirici_rehberi.md) içindedir.
- **Sürüm geçmişi**: [CHANGELOG.md](CHANGELOG.md) (Keep a Changelog biçimi).

---

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Hata bildirimi ve önerileriniz için GitHub üzerinden issue açabilir, değişiklikleriniz için pull request gönderebilirsiniz.

---

## 📄 Lisans

Bu proje [Apache License 2.0](LICENSE) ile lisanslanmıştır.

---

## 👥 Takım

Takım bilgileri başvuru sonrası eklenecektir.

---

## 🙏 Teşekkürler

- [TEKNOFEST](https://www.teknofest.org) — Yarışma organizasyonu
- [Bilişim Vadisi](https://www.bilisimvadisi.com.tr) — Yarışma yürütücüsü
- [Türksat](https://www.turksat.com.tr) — Yarışma destekçisi
- [Türkiye Açık Kaynak Platformu (TAKP)](https://github.com/Turkiye-Acik-Kaynak-Platformu) — Açık kaynak altyapı

---

<div align="center">

**TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması**

*Bu proje TEKNOFEST 2026 kapsamında geliştirilmektedir.*

</div>
