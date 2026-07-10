# Teknofest 2026 — Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-Agent_Framework-FF6F00?style=for-the-badge)
![License](https://img.shields.io/badge/License-Apache_2.0-green?style=for-the-badge)
![TEKNOFEST](https://img.shields.io/badge/TEKNOFEST-2026-red?style=for-the-badge)

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
| 📄 **OCR Desteği** | PDF, görüntü ve metin dosyalarından evrak okuma |
| 🏷️ **Otomatik Sınıflandırma** | Evrak türünü (dilekçe, üst yazı, cevap, tutanak vb.) belirleme |
| 🔍 **Bilgi Çıkarımı** | Tarih, kurum, konu, muhatap gibi anahtar bilgileri çıkarma |
| ⚠️ **Eksik Bilgi Tespiti** | Evrakta olması gereken ancak eksik alanları tespit etme |
| 📚 **Mevzuat Önerisi** | İlgili yönetmelik ve yazışma kurallarını önerme (RAG tabanlı) |
| 📝 **Özet Oluşturma** | Evrakın kısa ve öz özetini üretme |
| ✍️ **Yazı Taslaklama** | Resmi üsluba uygun yazı taslağı oluşturma |
| 🏢 **Birim Yönlendirme** | İçeriğe göre doğru birime yönlendirme önerisi |
| 💬 **Kullanıcı Bilgilendirme** | Süreç hakkında açık bilgilendirme ve eksik bilgi talebi |
| 🤖 **Çok Ajanlı Mimari** | Uzmanlaşmış agent'ların orkestrasyon ile koordinasyonu |

---

## 🏗️ Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│                    📥 EVRAK GİRİŞİ                          │
│              (PDF / Görüntü / Metin Dosyası)                │
└─────────────────┬───────────────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────────────┐
│              🧠 ORKESTRATÖR AGENT                            │
│         (İş Akışı Yönetimi ve Koordinasyon)                 │
└───┬──────────┬──────────┬──────────┬──────────┬─────────────┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│🔤 OCR  ││🏷️ Sınıf││🔍 Bilgi││⚠️ Eksik││📚 Mevz.│
│ Agent  ││ Agent  ││Çıkarım ││ Bilgi  ││ Agent  │
│        ││        ││ Agent  ││ Agent  ││        │
└────────┘└────────┘└────────┘└────────┘└────────┘
    │          │          │          │          │
    └──────────┴──────────┴──────────┴──────────┘
                          │
                  ┌───────┴───────┐
                  ▼               ▼
           ┌───────────┐   ┌───────────┐
           │📝 Özet    │   │✍️ Taslak  │
           │  Agent    │   │  Agent    │
           └───────────┘   └─────┬─────┘
                                 │
                     ┌───────────┼───────────┐
                     ▼           ▼           ▼
              ┌───────────┐┌───────────┐┌───────────┐
              │🏢 Yönlen. ││💬 Bilgil. ││❓ Eksik   │
              │  Agent    ││  Agent    ││Bilgi Talep│
              └───────────┘└───────────┘└───────────┘
                     │           │           │
                     └───────────┴───────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────┐
│                      📤 ÇIKTILAR                             │
│  Sınıflandırma | Bilgi Çıkarım | Özet | Yazı Taslağı      │
│  Mevzuat Önerisi | Birim Yönlendirme | Bilgilendirme       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Kurulum

### Gereksinimler

- Python 3.11 veya üzeri
- pip veya poetry

### Adımlar

```bash
# 1. Depoyu klonlayın
git clone https://github.com/TAKP/teknofest-2026-kamu-evrak-akilli-ajan.git
cd teknofest-2026-kamu-evrak-akilli-ajan

# 2. Sanal ortam oluşturun
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate

# 3. Bağımlılıkları yükleyin
pip install -r requirements.txt

# 4. Ortam değişkenlerini ayarlayın
copy .env.example .env
# .env dosyasını düzenleyerek API anahtarlarınızı ekleyin

# 5. Uygulamayı başlatın
python -m src.main
```

---

## 📖 Kullanım

### Komut Satırı

```bash
# Tek bir evrak işleme
python -m src.main --input data/raw/kurgu_evraklar/ornek_dilekce.pdf

# Demo senaryosu çalıştırma
python demo/demo_scenario.py

# Streamlit arayüzü ile çalıştırma
streamlit run src/app.py
```

### Python API

```python
from src.pipelines.end_to_end_pipeline import EndToEndPipeline

# Pipeline oluştur
pipeline = EndToEndPipeline()

# Evrak işle
sonuc = pipeline.process("evrak_dosyasi.pdf")

# Sonuçları görüntüle
print(sonuc.siniflandirma)    # Evrak türü
print(sonuc.ozet)             # Evrak özeti
print(sonuc.yazi_taslagi)     # Resmi yazı taslağı
print(sonuc.yonlendirme)      # Birim yönlendirme önerisi
```

---

## 📁 Proje Yapısı

```
teknofest-2026-kamu-evrak-akilli-ajan/
├── README.md                       # Bu dosya
├── LICENSE                         # Apache 2.0 Lisansı
├── requirements.txt                # Python bağımlılıkları
├── pyproject.toml                  # Proje konfigürasyonu
├── .gitignore                      # Git ignore kuralları
├── .env.example                    # Ortam değişkenleri örneği
├── docs/                           # Dokümantasyon
├── src/                            # Kaynak kodu
│   ├── agents/                     # Agent modülleri
│   ├── models/                     # Model wrapper'ları
│   ├── pipelines/                  # İş akışları
│   ├── utils/                      # Yardımcı araçlar
│   └── templates/                  # Yazı şablonları
├── data/                           # Veri setleri
├── tests/                          # Test dosyaları
├── demo/                           # Demo senaryoları
├── notebooks/                      # Jupyter notebook'lar
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

## 🎬 Demo

Demo senaryosu farklı evrak türleri üzerinde sistemin uçtan uca çalışmasını gösterir:

```bash
python demo/demo_scenario.py
```

Demo hakkında detaylı bilgi için `demo/README.md` dosyasına bakınız.

---

## 🤝 Katkıda Bulunma

Katkılarınızı bekliyoruz! Lütfen `CONTRIBUTING.md` dosyasını inceleyiniz.

---

## 📄 Lisans

Bu proje [Apache License 2.0](LICENSE) ile lisanslanmıştır.

---

## 👥 Takım

| İsim | Rol | İletişim |
|------|------|----------|
| TBD | Takım Kaptanı | - |
| TBD | Geliştirici | - |
| TBD | Geliştirici | - |
| TBD | Geliştirici | - |

---

## 🙏 Teşekkürler

- [TEKNOFEST](https://www.teknofest.org) — Yarışma organizasyonu
- [Bilişim Vadisi](https://www.bilisimvadisi.com.tr) — Yarışma yürütücüsü
- [Türksat](https://www.turksat.com.tr) — Yarışma destekçisi
- [Türkiye Açık Kaynak Platformu (TAKP)](https://github.com/nicetry-oss) — Açık kaynak altyapı

---

<div align="center">

**TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması**

*Bu proje TEKNOFEST 2026 kapsamında geliştirilmektedir.*

</div>
