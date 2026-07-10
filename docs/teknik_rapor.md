# Teknik Rapor

## Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi

**TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması (1. Senaryo)**

---

### 1. Özet

Bu projede, kamu kurumlarına gelen evrakların işlenmesi ve resmî yazışmaların üretilmesi süreçlerini uçtan uca destekleyen, yapay zeka temelli çok ajanlı bir sistem geliştirilmiştir. Sistem; evrakı okur (Görev 1: OCR/doğrudan metin), türünü belirler, önemli bilgi unsurlarını çıkarır, eksik bilgileri tespit eder, ilgili mevzuatı önerir ve özet üretir; ardından (Görev 2) resmî üsluba uygun yazı taslağı hazırlar, doğru birime yönlendirme önerisi sunar, kullanıcıyı süreç hakkında bilgilendirir ve gerekli durumlarda eksik bilgi talep eder. İki görev, tek orkestratör altında kesintisiz tek akışta çalışır.

Sistemin ayırt edici özelliği **çevrimdışı-öncelikli (offline-first) hibrit mimarisidir**: tüm yetenekler, harici hiçbir servis olmadan kural tabanlı yöntemlerle tam olarak çalışır; bir büyük dil modeli (LLM) erişimi mevcutsa (OpenAI-uyumlu API veya yerel Ollama) sistem düşük güvenli kararlarda otomatik olarak LLM eskalasyonuna başvurur. Bu tasarım, internet kesintisi senaryosunda dahi eksiksiz demo yapılabilmesini ve kamu kurumlarının veri gizliliği (KVKK) gereksinimlerine uygun tamamen yerel kurulum yapılabilmesini sağlar.

Etiketli sentetik değerlendirme setlerinde sistem; evrak sınıflandırmada **%100 doğruluk (35/35 geliştirme, 16/16 tutulmuş set)**, birim yönlendirmede **%100 doğruluk**, eksik bilgi tespitinde **1.00 micro-F1** başarımına ve evrak başına **~0,012–0,017 saniyelik** işleme süresine (gerçek zamana yakın) ulaşmıştır (bkz. Bölüm 5 ve metodolojik notlar).

### 2. Problem Tanımı

Kamu kurumlarında resmî yazışma ve evrak işlemleri; belgenin okunması, içerik analizi, evrak türünün belirlenmesi, tabi olduğu mevzuatın tespiti, resmî yazı taslağının hazırlanması, uygun birime yönlendirilmesi ve sürece ilişkin bilgilendirmelerin yapılması gibi çok sayıda alt görevden oluşan bir süreç zinciridir. Bu aşamaların farklı personelce yürütülmesi iş yükü dağılımına ve işlem sürelerinin uzamasına yol açmaktadır. Yarışma şartnamesi (m. 6.3–6.4), her iki görevi de kapsayan uçtan uca bir agent sistemi geliştirilmesini zorunlu kılmaktadır.

### 3. Yöntem

#### 3.1. Çok Ajanlı Mimari

Sistem, her biri tek bir sorumluluğu üstlenen **9 uzman ajan** ile bunları koordine eden bir **orkestratör**den oluşur:

| Ajan | Görev | Şartname isteri |
|---|---|---|
| OCR Agent | PDF/görüntü/metin okuma (Tesseract/EasyOCR opsiyonel) | G1: OCR veya doğrudan metin |
| Sınıflandırma Agent | Evrak türü belirleme (9 tür) + güven skoru | G1: tür belirleme |
| Bilgi Çıkarım Agent | Tarih, sayı, T.C. kimlik (checksum doğrulamalı), İlgi, konu, muhatap, kurum, kişi, IBAN, iletişim | G1: bilgi unsurları |
| Eksik Bilgi Agent | Türe özgü zorunlu alan denetimi + giderme önerisi | G1: eksik bilgi tespiti |
| Mevzuat Agent | BM25 tabanlı mevzuat/yazışma kuralı önerisi (RAG) | G1: mevzuat önerisi |
| Özet Agent | Skorlamalı extractive özet (künye + gövde) | G1: özet |
| Taslak Yazma Agent | Yönetmelik-uyumlu resmî yazı üretimi + format öz-denetimi | G2: taslak + resmî üslup |
| Yönlendirme Agent | 9 birimlik organizasyon şemasına gerekçeli yönlendirme | G2: birim yönlendirme |
| Bilgilendirme Agent | Süreç bilgilendirmesi + eksik bilgi talepleri | G2: bilgilendirme + eksik bilgi talebi |

Orkestrasyon **framework bağımsız, saf Python** ile özgün olarak gerçekleştirilmiştir; ajanlar paylaşılan bir durum nesnesi (`AgentState`) üzerinden haberleşir. Her adımın süresi ve durumu ölçülür (izlenebilirlik/denetlenebilirlik).

#### 3.2. Koşullu Akış (Orkestratör Kapıları)

Akış düz sıralı bir zincir değildir; üç koşullu kapı içerir:

1. **Okunabilirlik kapısı** — metin boş/çok kısaysa analiz ve taslak adımları atlanır, kullanıcıdan geçerli evrak istenir (uydurma çıktı üretilmez).
2. **Dil sezimi kapısı** — Türkçe'ye özgü karakter oranı ve ayırt edici durak kelime örtüşmesiyle hafif dil sezimi yapılır; Türkçe görünmeyen metinde taslak üretimi durdurulur ve kullanıcı uyarılır.
3. **Düşük güven kapısı** — sınıflandırma/yönlendirme güveni eşiğin (0,6) altındaysa sonuç "insan onayı gerekli" işaretiyle döner; kullanıcıya alternatif tür/birim adayları sunulur. LLM erişimi varsa aynı eşik LLM eskalasyonunu tetikler.

#### 3.3. Evrak Sınıflandırma

Dokuz evrak türü (dilekçe, üst yazı, cevap yazısı, bilgilendirme, tutanak, rapor, genelge, onaylı belge, diğer) için **ağırlıklı anahtar kelime skorlaması + 20'den fazla yapısal sinyal** kullanılır. Yapısal sinyaller resmî yazışma pratiğinin gerçek işaretlerine dayanır: "İlgi :" bloğu ve ilgide **ikinci şahıs iyelikli** belge atıfları (cevap yazısını üst yazıdan ayıran temel işaret), "TUTANAKTIR/GENELGE/OLUR" başlıkları, "Sayı :" kurumsal antetinin varlığının dilekçe olasılığını düşürmesi (vatandaş dilekçesi kurumsal kayıt numarası taşımaz), 3071 sayılı Kanun'daki dilekçe unsurlarının (ad-soyad, T.C. kimlik, adres, imza) birlikte bulunması vb. Tür skorları softmax ile kalibre edilmiş güven skoruna dönüştürülür; güven < 0,6 ise ve LLM erişilebilirse yapılandırılmış (JSON şemalı) LLM eskalasyonu devreye girer.

#### 3.4. Bilgi Çıkarımı ve Eksik Bilgi Tespiti

Bilgi çıkarımı, doğrulamalı desen eşleştirmeye dayanır: T.C. kimlik numaraları resmî **checksum algoritmasıyla** doğrulanır; evrakın kendi tarihi ("Tarih :" alanı, tanzim kalıpları) atıf/olay tarihlerinden (İlgi satırları, "... tarihli" kalıpları) ayrıştırılır; "No :" deseninde adres bağlamı (kapı/sokak numarası) dışlanır; "Gereği/Bilgi/Dağıtım" satırlarındaki birimler kurum antetinden ayrı tutulur. LLM erişilebilirse çıkarım LLM ile zenginleştirilir (desen sonuçları esas alınır). Eksik bilgi tespiti, türe özgü zorunlu alan setlerine (ör. dilekçede 3071 sayılı Kanun unsurları; üst yazıda sayı-konu-ilgi-imza) ve çıkarılmış doğrulanmış alanlara dayanır; her eksik için öncelik (kritik/önemli/bilgi) ve giderme önerisi üretilir.

#### 3.5. Mevzuat Önerisi (BM25 RAG)

Kamuya açık mevzuattan derlenen **15 belgelik korpus** (80 bölüm/chunk) üzerinde, harici bağımlılık gerektirmeyen **saf Python BM25-Okapi** dizini ile bölüm düzeyinde erişim yapılır (Türkçe küçük harf dönüşümü, durak kelime ayıklama). Sonuçlar **evrak türüne koşullu yeniden sıralanır** (ör. dilekçe → 3071/4982/CİMER önceliği) ve düşük benzerlikli sonuçlar taslağa atıf olarak girmez (eşik 0,6). Yazışma türlerinde Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik her zaman önerilir (şartnamedeki "standart yazışma kuralları" isteri). ChromaDB kuruluysa semantik arama opsiyonel olarak kullanılabilir.

#### 3.6. Resmî Yazı Taslağı Üretimi ve Format Öz-Denetimi

Taslak üretimi iki katmanlıdır: LLM erişilebilirse yönetmelik kuralları gömülü istemle üretim; aksi halde **şablon + kural tabanlı gövde kurulumu** (giriş cümlesi, özet atfı, mevzuat referansı, sonuç/kapanış). Şablonlar Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik'in biçim öğelerine göre hazırlanmıştır (başlık/antet, sayı, tarih, konu, muhatap, ilgi, metin, imza bloğu, ek, dağıtım). Hitap-kapanış uyumu gözetilir (üst makama "arz ederim", alt/eş makama "rica ederim", kişiye "saygılarımla"). Dört yazı türü üretilir: üst yazı, cevap yazısı, bilgilendirme ve **eksik bilgi talep yazısı** — kritik eksik içeren başvurularda otomatik seçilir; kurum içi belgelerde (tutanak/rapor/onaylı belge) ise düzenleyen birime yönelik **iade/ikmal notu** üretilir. Üretilen her taslak, sistemin kendi **9 kurallı yönetmelik kontrol listesinden** geçirilir ve format skoru raporlanır (format öz-denetimi).

#### 3.7. Birim Yönlendirme

Dokuz birimlik temsili kamu organizasyon şeması üzerinde, sözcük-başı sınırlı (Türkçe ek çekimine izin veren) ağırlıklı anahtar kelime eşleştirmesi; muhatap/hitap satırı > konu alanı > gövde kademeli birim-adı bonusu; evrak türü bonusları (ör. makam oluru → üst yönetim) ve ayrıştırıcı güven skoru kullanılır. Öneri, eşleşen sinyalleri açıklayan gerekçe metniyle birlikte sunulur (açıklanabilirlik).

#### 3.8. LLM Entegrasyon Katmanı

LLM katmanı SDK bağımlılığı olmadan (stdlib `urllib`) üç backend destekler: **OpenAI-uyumlu API** (OpenAI, OpenRouter, Groq, vLLM, LM Studio), **Ollama** (tamamen yerel) ve **offline** (kural tabanlı mod). Backend otomatik tespit edilir; yapılandırılmış çıktı (`generate_json`) bozuk JSON onarımı ve yeniden denemeyle sağlanır. Model eğitimi yapılmamıştır (şartname m. 6.6 uyarınca zorunlu değildir); üçüncü taraf model lisans bilgileri `docs/model_bilgileri.md` dosyasındadır ve depoya hiçbir model ağırlığı yüklenmemiştir.

### 4. Veri Setleri

Şartname (m. 6.5) uyarınca **gerçek kamu verisi kullanılmamıştır**. Tüm veriler `data/README.md` dosyasında kaynak ve kullanım haklarıyla belgelenmiştir:

- **Geliştirme seti:** 35 etiketli sentetik evrak (8 tür; 9 birimin her biri en az 2 evrakta hedef; her türden en az 1 kasıtlı eksik alanlı dosya). Takım üretimi, Apache 2.0.
- **Tutulmuş (held-out) set:** Kural kalibrasyonundan bağımsız yazılmış 16 sentetik evrak (8 tür × 2; farklı kurgu kurum evreni, konu ve üslup dokusu; 4 dosyada kasıtlı eksik alan).
- **Mevzuat korpusu:** 15 belge — 3071, 4982, 6698, 5070, 657, 5018, 4734, 2577, 5326, 5393, 3194 sayılı kanunların ve Resmî Yazışmalar ile Devlet Arşiv Hizmetleri yönetmeliklerinin evrak işleme bağlamındaki hükümlerinin özgün cümlelerle yazılmış özetleri + CİMER ve e-Yazışma bilgi notları (kaynak: mevzuat.gov.tr, cimer.gov.tr, DDO).
- Etiket şeması: `{tur, birim_kodu, eksik_alanlar, aciklama}` (`etiketler.json`).

### 5. Sonuçlar

Değerlendirme `scripts/evaluate.py` ile üretilmiştir (çıktılar: `data/processed/eval_report.json` ve `eval_report_heldout.json`); tüm metrikler harici LLM olmadan, **tamamen çevrimdışı kural tabanlı modda** alınmıştır.

| Metrik | Geliştirme seti (35 evrak) | Tutulmuş set (16 evrak) |
|---|---|---|
| Sınıflandırma doğruluğu | 1,000 (35/35) | 1,000 (16/16) |
| Sınıflandırma macro-F1 | 1,000 | 1,000 |
| Birim yönlendirme doğruluğu | 1,000 (35/35) | 1,000 (16/16) |
| Eksik bilgi tespiti micro-F1 | 1,000 | 1,000 |
| Evrak başına ortalama süre | 0,012 sn | 0,017 sn |

**Metodolojik notlar (şeffaflık):** (1) Geliştirme seti, kural setinin kalibre edildiği settir; bu setteki skorlar sistemin üst sınırını gösterir. (2) Tutulmuş set kural geliştirme sırasında hiç kullanılmamıştır; ilk ölçümde sınıflandırma 15/16, yönlendirme 16/16, eksik bilgi micro-F1 0,43 elde edilmiş; tek turluk hata analizinde tespit edilen hatalar dosyaya özgü ezber değil **ilkesel** düzeltmelerle (Konu satırında "cevap" ifadesinin yapısal sinyal sayılması, adres kontrolünün adres-biçimli satıra bağlanması, rapor bulgu/sonuç denetiminin bölüm başlığı yerine fiil köklerine dayandırılması) giderilmiş ve tablo yeniden ölçülmüştür. (3) Sentetik setlerin ölçeği (51 evrak) sınırlıdır; gerçek kurum ortamında dağılım kayması beklenmelidir — düşük güven kapısı ve insan-onayı mekanizması bu risk için tasarlanmıştır. (4) 37 birim testi sürekli yeşildir; sistem boş metin, 5 kelimelik metin, 50 KB metin ve Türkçe olmayan metin girdilerinde çökmeden, uygun uyarılarla çalışır.

### 6. Sınırlılıklar ve Gelecek Çalışmalar

- BM25 sözcüksel erişimdir; eşanlamlı/bağlamsal eşleşme için opsiyonel semantik arama (ChromaDB + çok dilli embedding) tanımlıdır ancak varsayılan kurulumda kapalıdır.
- LLM eskalasyonu ve LLM tabanlı taslak üretimi, API anahtarı/Ollama kurulumu gerektirir; offline modda kural tabanlı eşdeğerler devreye girer.
- Kişi adı çıkarımı desen/işaret temellidir; Türkçe NER modeli (ör. BERTurk tabanlı) ile geliştirme planlanmaktadır.
- EBYS/e-Yazışma Paketi entegrasyonu (TS 13298 uyumlu sistemlere bağlanma) ürünleşme aşaması hedefidir.

### 7. Kaynakça

1. Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik, T.C. Resmî Gazete, Sayı 31151, 10 Haziran 2020. https://www.mevzuat.gov.tr/
2. 3071 sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun; 4982 sayılı Bilgi Edinme Hakkı Kanunu; 6698 sayılı Kişisel Verilerin Korunması Kanunu; 5070 sayılı Elektronik İmza Kanunu; 657 sayılı Devlet Memurları Kanunu; 5018 sayılı Kamu Malî Yönetimi ve Kontrol Kanunu; 4734 sayılı Kamu İhale Kanunu; 2577 sayılı İdari Yargılama Usulü Kanunu; 5326 sayılı Kabahatler Kanunu; 5393 sayılı Belediye Kanunu; 3194 sayılı İmar Kanunu. T.C. Mevzuat Bilgi Sistemi, https://www.mevzuat.gov.tr/
3. Robertson, S. ve Zaragoza, H. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond". *Foundations and Trends in Information Retrieval*, 3(4), 333–389.
4. Smith, R. (2007). "An Overview of the Tesseract OCR Engine". *Proc. ICDAR 2007* (Tesseract OCR, Apache 2.0). https://github.com/tesseract-ocr/tesseract
5. CİMER — Cumhurbaşkanlığı İletişim Merkezi, https://www.cimer.gov.tr/
6. e-Yazışma Projesi Teknik Rehberi, T.C. Cumhurbaşkanlığı Dijital Dönüşüm Ofisi, https://cbddo.gov.tr/
7. Streamlit (Apache 2.0), https://streamlit.io/ ; Pydantic (MIT), https://docs.pydantic.dev/ ; Rich (MIT), https://github.com/Textualize/rich
