# Katkı Rehberi (CONTRIBUTING)

Bu depo, TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması (1. Senaryo) için
geliştirilen **Kamu Evrak Akıllı Ajan Sistemi**'nin kaynak kodunu içerir.
Katkılarınızı memnuniyetle karşılıyoruz; aşağıdaki kurallar hem kod kalitesini
hem de yarışma şartnamesine uyumu korumak içindir.

Mimarinin nasıl genişletileceği (yeni ajan, yeni evrak türü, yeni birim,
yeni mevzuat belgesi, yeni API ucu) adım adım
[docs/gelistirici_rehberi.md](docs/gelistirici_rehberi.md) dosyasında anlatılır.

---

## 1. Geliştirme Kurulumu

```bash
# Depoyu klonlayın
git clone https://github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan.git
cd teknofest-2026-kamu-evrak-akilli-ajan

# Sanal ortam (Python 3.9+)
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# Çekirdek bağımlılıklar — sistem bunlarla TAM çalışır (offline, LLM'siz)
pip install -r requirements.txt

# (Opsiyonel) OCR / semantik arama / yerel model yetenekleri
pip install -r requirements-optional.txt

# Kurulumu doğrulayın
python -m src.main --input data/raw/kurgu_evraklar/dilekce_01.txt
```

Tek komutla demo için depo kökünde `./baslat.sh` (web arayüzü) veya
`./baslat.sh --api` (REST API) kullanılabilir.

## 2. Testleri Çalıştırma

```bash
pytest tests/ -q                      # tüm testler (kısa çıktı)
pytest tests/test_classification.py   # tek modül
pytest tests/ --cov=src --cov-report=html   # kapsama raporu
python -m compileall -q src scripts   # derleme/sözdizimi denetimi
```

Bir pull request açmadan önce **tüm testler yerelde yeşil olmalıdır**.
Aynı denetimler her push/PR'da GitHub Actions CI'ında (Python 3.9 ve 3.12)
otomatik çalışır; CI kırmızıyken PR birleştirilmez.

## 3. Üslup Kuralları

- **Türkçe zorunluluğu**: Tüm docstring'ler, kod yorumları, log mesajları ve
  kullanıcıya dönük çıktılar Türkçedir (teknik terimler İngilizce orijinal
  formlarıyla kullanılabilir). Bu, yarışma şartnamesinin gereğidir.
- **Python 3.9 uyumu**: Kod tabanı Python 3.9'u destekler. Yeni modüllerde
  `from __future__ import annotations` kullanın; 3.10+ sözdizimine
  (`match`, `X | Y` çalışma zamanı tip birleşimi vb.) dayanmayın.
- **stdlib önceliği**: Yeni **çekirdek** bağımlılık eklemeyin. Çekirdek
  (`requirements.txt`) ile sistem offline ve LLM'siz TAM çalışır; bu
  bozulamaz. Zorunlu yeni yetenekler önce stdlib ile denenmeli, mümkün
  değilse `requirements-optional.txt` altında **opsiyonel** (import hatasına
  dayanıklı) eklenmelidir.
- **Logger deseni**: Her modül kendi logger'ını
  `logger = logging.getLogger("kamu_evrak_ajan.<modul>")` kalıbıyla açar;
  `print` yalnızca CLI çıkış noktalarında kullanılır.
- **Ajan sözleşmesi**: Her ajan, paylaşılan `AgentState` nesnesini alan ve
  geri döndüren tek bir `run(self, state)` metodu sunar
  (bkz. `src/agents/orchestrator.py`).
- **Gerçek kişisel veri YASAK**: Test/örnek verilerde yalnızca açıkça kurgu
  değerler kullanılır (kurgu TCKN'ler checksum'ı geçebilir ama gerçek bir
  kişiye ait olamaz). KVKK ilkesi ihlal edilemez.

## 4. Dal (Branch) ve Commit Düzeni

- `main` dalı her zaman yeşil (testleri geçen) tutulur; değişiklikler
  konu dalları üzerinden PR ile gelir.
- Dal adları: `feat/<kisa-ad>`, `fix/<kisa-ad>`, `docs/<kisa-ad>`.
- Commit mesajları, depodaki mevcut gelenekle uyumlu olarak
  **Conventional Commits + Türkçe özet** biçimindedir:

  ```
  feat(triage): süreli evrak için iş günü hesabı
  fix(kvkk): kişi adı sızıntısı kapatıldı
  docs: geliştirici rehberi eklendi
  ```

- Bir commit tek bir mantıksal değişiklik içerir; kod + testi birlikte gelir.
- Davranış değiştiren her PR'a test eşlik eder; kullanıcıya dönük
  değişiklikler `CHANGELOG.md` dosyasının `[Yayınlanmamış]` bölümüne işlenir.

## 5. Değerlendirme Bütünlüğü Kuralları (İHLAL EDİLEMEZ)

Bu proje ölçülebilir başarım raporluyor; ölçümün güvenilirliği her şeyin
üstündedir:

- **Held-out (tutulmuş) setlere bakarak kural yazılmaz.**
  `data/raw/kurgu_evraklar_heldout*` altındaki setler nihai ölçüm içindir;
  bu setlerdeki hatalara bakılarak kural/kod kalibre edilirse set held-out
  niteliğini KAYBEDER ve bu durum `docs/teknik_rapor.md` §5'e açıkça
  yazılmak zorundadır. Kural geliştirme yalnızca geliştirme seti
  (`data/raw/kurgu_evraklar`, 52 evrak) üzerinde yapılır.
- **Rapor dosyaları elle düzenlenmez.** `data/processed/eval_report*.json`
  yalnızca `scripts/evaluate.py` ile üretilir.
- **Sonuçlar olduğu gibi raporlanır.** Ölçüm ne çıkarsa çıksın gizlenmez,
  yuvarlanmaz, seçici sunulmaz; sonuç manipülasyonu şartnameye göre etik
  ihlaldir.
- **Etiket şeması** `{tur, birim_kodu, eksik_alanlar, aciklama}` biçimindedir;
  `eksik_alanlar` anahtarları `src/agents/missing_info_agent.py` içindeki
  `ZORUNLU_ALANLAR` ile birebir uyumlu olmalıdır.

## 6. Hata Bildirimi ve Öneriler

GitHub Issues üzerinden bildirin. İyi bir hata kaydında şunlar bulunur:
yeniden üretme adımları (mümkünse örnek evrak metni), beklenen/gözlenen
davranış, Python sürümü ve `pytest tests/ -q` çıktısı.
