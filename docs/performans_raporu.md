# Performans ve Ölçeklenebilirlik Raporu

> Bu rapor `scripts/benchmark.py` aracının **gerçek ölçüm çıktısından**
> üretilmiştir; tüm sayılar `data/processed/benchmark_raporu.json`
> dosyasındaki değerlerle birebir aynıdır.
>
> Ölçüm tarihi: 2026-07-11T12:57:40 · LLM backend: `offline`
> (kural-tabanlı/offline mod)

## 1. Amaç

Şartnamedeki *"Gerçek zamana yakın çalışma avantaj sağlayacaktır"* (Demo)
maddesi ile ticarileşme/ölçeklenebilirlik iddialarını ölçülmüş sayılara
bağlamak: evrak/saniye (throughput), gecikme yüzdelikleri (p95/p99),
adım bazında süre dağılımı, tepe bellek ve soğuk başlangıç süresi.

## 2. Ortam ve Yöntem

| Özellik | Değer |
|---|---|
| İşletim sistemi | Darwin 23.6.0 (arm64) |
| Çekirdek sayısı | 8 (ölçüm **tek süreç/tek çekirdek** üzerinde) |
| Python | 3.9.6 |
| LLM backend | `offline` — ölçüm kural-tabanlı mod içindir |
| Evrak kümesi | 67 evrak (`data/raw/kurgu_evraklar`, `data/raw/kurgu_evraklar_heldout`, `data/raw/kurgu_evraklar_heldout_v2`) |
| Tekrar sayısı | 3 (her evrak 3 kez işlendi) |

Yöntem (ayrıntı: `scripts/benchmark.py` modül docstring'i):

1. **Soğuk başlangıç ayrı ölçülür** — pipeline import+kurulum ve ilk evrak
   (ısınma) süreleri tekrarlı ölçümlere karıştırılmaz; aksi hâlde p99
   yapay şişerdi.
2. **Gecikme**, `time.perf_counter` ile evrak başına duvar saati olarak
   ölçülür; ortalama tek başına yanıltıcı olduğundan medyan ve kuyruk
   yüzdelikleri (p95/p99) birlikte raporlanır.
3. **Bellek** ayrı bir turda `tracemalloc` ile ölçülür (izleme ek yükü
   gecikme ölçümünü bozmasın diye).
4. **Ölçekleme**: aynı evrak kümesi bellek içinde 1x/5x/10x
   çoğaltılıp toplam süre ölçülür; evrak başına süre sabit kalıyorsa
   (doğrusallık oranı ≈ 1.0) sistem evrak sayısında doğrusal ölçeklenir.
5. **Rastgelelik yoktur**: setler ve dosyalar sabit (ad) sırayla işlenir.

## 3. Sonuçlar

### 3.1 Genel özet

| Metrik | Değer |
|---|---|
| Soğuk başlangıç (pipeline kurulumu) | 0.02 sn |
| Isınma (ilk evrak) | 0.042 sn |
| **Throughput** | **91.8 evrak/sn** (201 evrak / 2.188 sn) |
| Gecikme — ortalama | 10.89 ms |
| Gecikme — medyan | 10.67 ms |
| Gecikme — p95 | 14.08 ms |
| Gecikme — p99 | 15.27 ms |
| Gecikme — min–maks | 6.62–16.46 ms |
| Tepe bellek (tracemalloc) | 0.2 MB |

### 3.2 Adım bazında ortalama süre

| Agent | Çalışma sayısı | Ortalama (ms) | Pay (%) |
|---|---|---|---|
| ocr | 201 | 0.0 | 0.0 |
| classification | 201 | 1.81 | 19.0 |
| info_extraction | 201 | 1.75 | 18.3 |
| missing_info | 201 | 0.13 | 1.4 |
| legislation | 201 | 1.03 | 10.8 |
| triage | 201 | 0.03 | 0.3 |
| summarization | 201 | 0.97 | 10.2 |
| anonimlestirme | 201 | 0.67 | 7.0 |
| draft_writer | 201 | 0.01 | 0.2 |
| routing | 201 | 3.15 | 33.0 |
| user_info | 201 | 0.0 | 0.0 |

### 3.3 Ölçekleme testi (bellek içi çoğaltma)

| Ölçek | Evrak | Toplam (sn) | Evrak başına (ms) | Doğrusallık oranı |
|---|---|---|---|---|
| 1x | 67 | 0.72 | 10.75 | 1.0 |
| 5x | 335 | 3.616 | 10.79 | 1.0 |
| 10x | 670 | 7.216 | 10.77 | 1.0 |

## 4. Yorum

- **Gerçek zamana yakın çalışma iddiası ölçümle doğrulanmıştır:** evrak
  başına p99 gecikme 15.27 ms'dir; yani en yavaş yüzde birlik dilimde bile
  bir evrağın uçtan uca işlenmesi (sınıflandırma + bilgi çıkarımı + eksik
  bilgi + mevzuat + özet + KVKK nüshası + taslak + yönlendirme) saniyenin
  altıda birinden kısadır. Demo/arayüz kullanımında yanıt anlıktır.
- **Kurumsal hacim projeksiyonu (ölçülen 91.8 evrak/sn üzerinden):**
  tek çekirdekte günde 500 evrak alan orta ölçekli bir il müdürlüğünün
  tüm günlük hacmi ~5.4 saniyede, günde 2.000 evrak alan büyük bir
  kurumun hacmi ~22 saniyede (< 1 dakika) işlenir. Saatlik kapasite
  ~330.000 evraktır; Türkiye ölçeğinde merkezî bir evrak akışı için bile
  tek makine yeterlidir.
- **Doğrusal ölçeklenme:** 1x→10x yük artışında evrak başına süre
  10.75→10.77 ms ile sabit kalmıştır (doğrusallık oranı 1.0). Pipeline
  evrak başına durum biriktirmez (her işlemde `AgentState` sıfırlanır);
  bu, uzun süre çalışan bir servis örneğinde performans erimesi
  olmayacağının kanıtıdır.
- **Yatay ölçeklenme potansiyeli:** işleme evrak başına bağımsız
  (durumsuz) olduğundan süreç sayısıyla çarpılabilir; ölçüm yapılan 8
  çekirdekli makinede süreç başına ~92 evrak/sn taban değeri, çok
  süreçli dağıtımda kabaca çekirdek sayısıyla ölçeklenebilir bir üst
  sınır tanımlar (bu rapor tek süreç değerini taahhüt eder).
- **Darboğaz analizi:** en maliyetli adım yönlendirmedir (routing,
  ortalama 3.15 ms, toplam sürenin %33'ü); onu sınıflandırma (%19) ve
  bilgi çıkarımı (%18.3) izler. Olası bir optimizasyon bu üç regex/sözlük
  yoğun adıma odaklanmalıdır — ancak mevcut mutlak değerler zaten
  milisaniye mertebesinde olduğundan optimizasyon gerekliliği yoktur.
- **Kaynak ayak izi:** tepe Python tahsisi 0.2 MB, pipeline kurulumu
  0.02 sn'dir; sistem düşük donanımlı kurum bilgisayarlarında ve
  soğuk başlatılan sunucusuz (serverless) ortamlarda dahi çalıştırılabilir.

## 5. Sınırlılıklar

1. **Tek makine, tek süreç:** tüm sayılar tek bir geliştirme makinesinde
   (Darwin/arm64, Python 3.9) tek süreçte ölçülmüştür; farklı
   donanımda mutlak değerler değişir (göreli dağılım ve doğrusallık
   bulgusu taşınabilir).
2. **Sentetik evrak uzunlukları:** değerlendirme setindeki 67 kurgu
   evrak 1–2.3 KB (ortalama ~1.8 KB) düz metindir. Gerçek hayattaki çok
   sayfalı taranmış PDF'lerde görüntü OCR'ı (Tesseract vb.) baskın
   maliyet olur; bu ölçümde OCR adımı düz metin okuduğu için ~0 ms
   görünmektedir ve OCR maliyetini temsil etmez.
3. **Kural-tabanlı mod:** ölçüm LLM'siz (offline) moddadır. LLM
   eskalasyonu etkinleştirilirse eskalasyona düşen evraklarda model/ağ
   gecikmesi (saniyeler mertebesi) eklenir; bu rapor yalnızca
   kural-tabanlı çekirdeğin performansını taahhüt eder.
4. **Bellek ölçüm yöntemi:** `tracemalloc` yalnızca Python nesne
   tahsislerini izler; sürecin işletim sistemi düzeyindeki toplam
   bellek kullanımını (RSS — yorumlayıcı + kütüphaneler) içermez.
5. **Sıcak önbellek:** tekrarlı ölçümler aynı süreç içinde yapıldığından
   dosya sistemi ve regex derleme önbellekleri sıcaktır; soğuk maliyet
   ayrıca raporlanan soğuk başlangıç/ısınma değerlerinde görülür.

## 6. Yeniden Üretim

```bash
python3 scripts/benchmark.py --tekrar 3
# Çıktılar: konsol tabloları + data/processed/benchmark_raporu.json
python3 -m pytest tests/test_benchmark.py -q   # metrik fonksiyonlarının birim testleri
```
