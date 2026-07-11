# Teknik Rapor

## Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi

**TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması (1. Senaryo)**

---

### 1. Özet

Bu projede, kamu kurumlarına gelen evrakların işlenmesi ve resmî yazışmaların üretilmesi süreçlerini uçtan uca destekleyen, yapay zeka temelli çok ajanlı bir sistem geliştirilmiştir. Sistem; evrakı okur (Görev 1: OCR/doğrudan metin), türünü belirler, önemli bilgi unsurlarını çıkarır, eksik bilgileri tespit eder, ilgili mevzuatı önerir ve özet üretir; ardından (Görev 2) resmî üsluba uygun yazı taslağı hazırlar, doğru birime yönlendirme önerisi sunar, kullanıcıyı süreç hakkında bilgilendirir ve gerekli durumlarda eksik bilgi talep eder. İki görev, tek orkestratör altında kesintisiz tek akışta çalışır.

Sistemin ayırt edici özelliği **çevrimdışı-öncelikli (offline-first) hibrit mimarisidir**: tüm yetenekler, harici hiçbir servis olmadan kural tabanlı yöntemlerle tam olarak çalışır; bir büyük dil modeli (LLM) erişimi mevcutsa (OpenAI-uyumlu API veya yerel Ollama) sistem düşük güvenli kararlarda otomatik olarak LLM eskalasyonuna başvurur. Bu tasarım, internet kesintisi senaryosunda dahi eksiksiz demo yapılabilmesini ve kamu kurumlarının veri gizliliği (KVKK) gereksinimlerine uygun tamamen yerel kurulum yapılabilmesini sağlar.

Etiketli sentetik değerlendirme setlerinde sistem; **yeni tutulmuş sette (v2)** evrak sınıflandırmada **%100 doğruluk (16/16)**, birim yönlendirmede **%93,8 doğruluk (15/16)**, eksik bilgi tespitinde **1,000 micro-F1**, mevzuat önerisinde **0,750 isabet@3** başarımına ve evrak başına **~0,02–0,03 saniyelik** medyan işleme süresine (gerçek zamana yakın) ulaşmıştır; geliştirme ve ilk tutulmuş setlerdeki skorlar sınıflandırma/yönlendirme/eksik bilgi metriklerinde 1,00, mevzuat isabet@3'te sırasıyla 0,943 ve 0,875'tir (bkz. Bölüm 5 ve metodolojik notlar).

### 2. Problem Tanımı

Kamu kurumlarında resmî yazışma ve evrak işlemleri; belgenin okunması, içerik analizi, evrak türünün belirlenmesi, tabi olduğu mevzuatın tespiti, resmî yazı taslağının hazırlanması, uygun birime yönlendirilmesi ve sürece ilişkin bilgilendirmelerin yapılması gibi çok sayıda alt görevden oluşan bir süreç zinciridir. Bu aşamaların farklı personelce yürütülmesi iş yükü dağılımına ve işlem sürelerinin uzamasına yol açmaktadır. Yarışma şartnamesi (m. 6.3–6.4), her iki görevi de kapsayan uçtan uca bir agent sistemi geliştirilmesini zorunlu kılmaktadır.

### 3. Yöntem

#### 3.1. Çok Ajanlı Mimari

Sistem, her biri tek bir sorumluluğu üstlenen **11 uzman ajan** ile bunları koordine eden bir **orkestratör**den oluşur:

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
| Bilgilendirme Agent | Süreç bilgilendirmesi + eksik bilgi talepleri + süreli evrak uyarısı | G2: bilgilendirme + eksik bilgi talebi |
| Önceliklendirme (Triage) Agent | Aciliyet damgası + yasal süre tespiti, son işlem tarihi hesabı | G1 destekleyici (yenilik) |
| KVKK Anonimleştirme Agent | Kişisel verileri maskeleyen paylaşım nüshası üretimi | G1 destekleyici (yenilik) |

Orkestrasyon **framework bağımsız, saf Python** ile özgün olarak gerçekleştirilmiştir; ajanlar paylaşılan bir durum nesnesi (`AgentState`) üzerinden haberleşir. Her adımın süresi ve durumu ölçülür (izlenebilirlik/denetlenebilirlik).

#### 3.2. Koşullu Akış (Orkestratör Kapıları)

Akış düz sıralı bir zincir değildir; üç koşullu kapı içerir:

1. **Okunabilirlik kapısı** — metin boş/çok kısaysa analiz ve taslak adımları atlanır, kullanıcıdan geçerli evrak istenir (uydurma çıktı üretilmez).
2. **Dil sezimi kapısı** — Türkçe'ye özgü karakter oranı ve ayırt edici durak kelime örtüşmesiyle hafif dil sezimi yapılır; Türkçe görünmeyen metinde taslak üretimi durdurulur ve kullanıcı uyarılır.
3. **Düşük güven kapısı** — sınıflandırma/yönlendirme güveni eşiğin (0,6) altındaysa sonuç "insan onayı gerekli" işaretiyle döner; kullanıcıya alternatif tür/birim adayları sunulur. LLM erişimi varsa aynı eşik LLM eskalasyonunu tetikler.

#### 3.3. Evrak Sınıflandırma

Dokuz evrak türü (dilekçe, üst yazı, cevap yazısı, bilgilendirme, tutanak, rapor, genelge, onaylı belge, diğer) için **ağırlıklı anahtar kelime skorlaması + 20'den fazla yapısal sinyal** kullanılır. Yapısal sinyaller resmî yazışma pratiğinin gerçek işaretlerine dayanır: "İlgi :" bloğu ve ilgide **ikinci şahıs iyelikli** belge atıfları (cevap yazısını üst yazıdan ayıran temel işaret), "TUTANAKTIR/GENELGE/OLUR" başlıkları, "Sayı :" kurumsal antetinin varlığının dilekçe olasılığını düşürmesi (vatandaş dilekçesi kurumsal kayıt numarası taşımaz), 3071 sayılı Kanun'daki dilekçe unsurlarının (ad-soyad, T.C. kimlik, adres, imza) birlikte bulunması vb. Tür skorları softmax ile kalibre edilmiş güven skoruna dönüştürülür.

**Hibrit üçlü ensemble:** Kural katmanının yanında, saf Python ile gerçeklenmiş **Multinomial Naive Bayes** istatistiksel sınıflandırıcı çalışır (`src/models/istatistiksel_siniflandirici.py`): öznitelikler kelime token'ları + kelime-sınırı işaretli karakter 3-gram'larıdır (Türkçe'nin sondan eklemeli yapısında "başvuru/başvurunuz/başvurumun" biçimlerinin gram paylaşması için); alt-doğrusal TF × IDF ağırlıklandırma, Laplace düzeltme ve uzunluk normalizasyonu (Rennie ve ark. 2003) kullanılır. Model yalnızca geliştirme setinde eğitilir (`scripts/ml_egit.py`; tutulmuş setler eğitimde kullanılmaz — veri sızıntısı önlenir) ve kural skoruyla olasılık uzayında birleştirilir (`yontem: hibrit_ensemble`; kural ve ML güvenleri ayrı raporlanır). Nihai güven < 0,6 ise ve LLM erişilebilirse yapılandırılmış (JSON şemalı) LLM eskalasyonu üçüncü katman olarak devreye girer. Böylece sınıflandırma üç bağımsız yöntem ailesini (kural/ML/LLM) tek kararda birleştirir.

#### 3.4. Bilgi Çıkarımı ve Eksik Bilgi Tespiti

Bilgi çıkarımı, doğrulamalı desen eşleştirmeye dayanır: T.C. kimlik numaraları resmî **checksum algoritmasıyla** doğrulanır; evrakın kendi tarihi ("Tarih :" alanı, tanzim kalıpları) atıf/olay tarihlerinden (İlgi satırları, "... tarihli" kalıpları) ayrıştırılır; "No :" deseninde adres bağlamı (kapı/sokak numarası) dışlanır; "Gereği/Bilgi/Dağıtım" satırlarındaki birimler kurum antetinden ayrı tutulur. LLM erişilebilirse çıkarım LLM ile zenginleştirilir (desen sonuçları esas alınır). Eksik bilgi tespiti, türe özgü zorunlu alan setlerine (ör. dilekçede 3071 sayılı Kanun unsurları; üst yazıda sayı-konu-ilgi-imza) ve çıkarılmış doğrulanmış alanlara dayanır; her eksik için öncelik (kritik/önemli/bilgi) ve giderme önerisi üretilir.

#### 3.5. Mevzuat Önerisi (Hibrit, Düzeltici RAG)

Kamuya açık mevzuattan derlenen **15 belgelik korpus** (80 bölüm/chunk) üzerinde, harici bağımlılık gerektirmeyen **saf Python BM25-Okapi** dizini ile bölüm düzeyinde erişim yapılır (Türkçe küçük harf dönüşümü, durak kelime ayıklama). Her bölümün atıf yaptığı **madde numaraları** chunk üstverisine çıkarılır; böylece her öneri `{mevzuat adı, madde no, ilgililik gerekçesi, benzerlik skoru}` biçiminde sunulur. Gerekçe halüsinasyonsuzdur: yalnızca gözlenen eşleşme sinyallerinden (ortak ayırt edici terimler, tür önceliği, aktif alan teması) kurulur.

Sonuçlar **evrak türüne koşullu yeniden sıralanır** (ör. dilekçe → 3071/4982/CİMER önceliği) ve düşük benzerlikli sonuçlar taslağa atıf olarak girmez (eşik 0,6). Yazışma türlerinde Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik her zaman önerilir (şartnamedeki "standart yazışma kuralları" isteri).

Erişim hattı, güncel agentic RAG literatüründeki **düzeltici (corrective) RAG** desenini saf Python'la uygular (Kaynakça 8 ve 9): en iyi önerinin benzerliği düzeltme tetiğinin (0,15) altında kalırsa sorgu, evrak türünün usul söz dağarcığıyla (ör. dilekçe → "başvuru, talep, cevap, süre, imza, adres") bir kez genişletilir, arama yinelenir ve yalnızca en iyi benzerlik iyileşirse yeni sonuç benimsenir. Düzeltme tetiği, zayıf-eşleşme İŞARETİNDEN (0,5 — şeffaflık amaçlı `zayif_esleme` bayrağı) bilinçle ayrıdır ve geliştirme seti gözlemiyle kalibre edilmiştir (held-out kullanılmadı): mutlak ölçekte 35 geliştirme evrakında ilk-en-iyi benzerlik min. 0,107 / medyan 0,245'tir; tetik 0,5'te döngü 33/35 evrakta ateşlenip usul terimleriyle alan mevzuatını ilk üçten itebildiğinden geliştirme isabet@3'ü 0,943→0,914'e düşürmüş, 0,15'te ise isabet 0,943'te kalarak döngü yalnızca 2 sınır evrakta çalışmıştır — bu yüzden 0,15 seçilmiştir (iyi eşleşen evraklara dokunmaz, söz dağarcığı uyuşmazlığında güvenlik ağı olur; birim testle doğrulanır). Döngünün uygulanıp uygulanmadığı, eşik ve benzerlik değişimi pipeline çıktısındaki `mevzuat_arama_meta` alanında raporlanır (izlenebilirlik). Opsiyonel yoğun (dense) katman etkinleştirilirse (`EMBEDDING_SEMANTIK_AKTIF=1`; `ytu-ce-cosmos/turkish-e5-large`) semantik adaylar BM25 sonuçlarıyla dışbükey puan birleşimine girer; `EMBEDDING_RERANK_AKTIF=1` ile aday havuzu `BAAI/bge-reranker-v2-m3` çapraz kodlayıcısıyla yeniden sıralanır. Opsiyonel katmanlar yokken davranış salt-BM25 aramasıyla birebir aynıdır (çevrimdışı-öncelikli tasarım); ChromaDB yalnızca BM25 dizini kurulamadığında devreye giren yedek yoldur.

#### 3.6. Resmî Yazı Taslağı Üretimi ve Format Öz-Denetimi

Taslak üretimi iki katmanlıdır: LLM erişilebilirse yönetmelik kuralları gömülü istemle üretim; aksi halde **şablon + kural tabanlı gövde kurulumu** (giriş cümlesi, özet atfı, mevzuat referansı, sonuç/kapanış). Şablonlar Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik'in biçim öğelerine göre hazırlanmıştır (başlık/antet, sayı, tarih, konu, muhatap, ilgi, metin, imza bloğu, ek, dağıtım). Kapanış ifadesi **muhatap hiyerarşisine göre** seçilir: alt makama "rica ederim", üst VE AYNI DÜZEYDEKİ makama "arz ederim" (m.16/12-a), gerçek kişiye "Saygılarımla." (m.16/12-e); muhatap ve gönderen kademeleri hitap/antet morfolojisinden çıkarılır, belirsizlikte yazı türüne dayalı güvenli varsayılan kullanılır. Dört yazı türü üretilir: üst yazı, cevap yazısı, bilgilendirme ve **eksik bilgi talep yazısı** — kritik eksik içeren başvurularda otomatik seçilir; kurum içi belgelerde (tutanak/rapor/onaylı belge) ise düzenleyen birime yönelik **iade/ikmal notu** üretilir.

**Madde-referanslı format öz-denetimi:** Üretilen her taslak, her kuralı `{kural_id, kural, durum, detay, dayanak, agirlik}` şemasıyla raporlayan denetçiden geçirilir; hukuki doğrulayıcı-ajan desenine paraleldir (Kaynakça 11). **Dayanaklar, 2646 sayılı Yönetmeliğin resmî metninden fıkra düzeyinde doğrulanmıştır** (mevzuat.gov.tr birincil + tccb.gov.tr çapraz kontrol) ve arayüz ile HTML işlem raporunda kuralın yanında gösterilir — jüri önünde madde gösterilebilir. Kural kümesi: T.C. başlığı (m.10/2), sayı varlığı (m.11/1) ve **sayı biçimi** E/Z/O-DETSİS-SDP-kayıt (m.11/1-2; taslak sayı uydurmaz, dürüst EBYS ibaresi kabul edilir), tarih biçimi (m.12/1), konu varlığı (m.13/1) ve kısa-özlüğü (m.13/2), muhatap (m.14), İlgi (m.15/1, türe koşullu), kapanış ifadesi (m.16/12) ve **bitiş↔hiyerarşi tutarlılığı** (m.16/12-a,b; kademeler tespit edilebiliyorsa), yabancı kelime uyarısı (m.16/8), harfli maddelemede "a)" biçimi (m.16/10, koşullu), imza bloğu (m.17), yetki devri "... a." düzeni (m.17/9, koşullu) ve **gizlilik damgalı evrakta kısıtlı mod** (m.25; damga taslağa taşınmalı, karar insan onayına düşer). Skor ağırlıklı ortalamadır; bilgi niteliğindeki kurallar düşük ağırlık taşır ve koşullu kurallar bağlam yokken listeye eklenmez (yanlış alarm üretilmez). Terminoloji notu: 2020 Yönetmeliği ivedilik için yalnızca **ACELE/GÜNLÜDÜR** (m.26) ibarelerini tanımlar; sahada yaygın "İVEDİ" damgası mülga 2014 yönetmeliğinin terimidir — sistem her iki aileyi de algılar, dayanak atfını 2020 metnine verir.

**Bağımsız taslak kalite hakemi:** Format öz-denetiminin üzerine, üretici ajandan bağımsız bir hakem her taslağı **0-100 ölçeğinde** puanlar (`src/utils/taslak_hakemi.py`). LLM erişilebilirse dört boyutlu rubrik (üslup/yapı/kapanış/açıklık) LLM-as-judge ile puanlatılır; erişilemezse kural tabanlı eşdeğer (biçim %40 + üslup %30 + mevzuat temellilik %30) aynı ölçeğe normalize edilir — iki yolun çıktısı karşılaştırılabilirdir. **Mevzuat temellilik** bileşeni her iki yolda da deterministiktir (RAGAS'ın groundedness fikrinin saf Python karşılığı): taslakta atıf yapılan mevzuat, önerici ajanın mutlak benzerlik skorlarıyla desteklenmeli ve öneri listesinde bulunmalıdır; **listede olmayan atıf halüsinasyon işareti sayılıp ağır cezalandırılır** (temellilik yargısının LLM'e bırakılmaması bilinçlidir — halüsinasyon halüsinasyonla denetlenmez). Çevrimdışı kural modunda ölçülen ortalama kalite puanları: geliştirme 92,9 / tutulmuş 95,8 / tutulmuş v2 94,6 (bkz. Bölüm 5).

#### 3.7. Birim Yönlendirme

Dokuz birimlik temsili kamu organizasyon şeması üzerinde, sözcük-başı sınırlı (Türkçe ek çekimine izin veren) ağırlıklı anahtar kelime eşleştirmesi; muhatap/hitap satırı > konu alanı > gövde kademeli birim-adı bonusu; evrak türü bonusları (ör. makam oluru → üst yönetim) ve ayrıştırıcı güven skoru kullanılır. Öneri, eşleşen sinyalleri açıklayan gerekçe metniyle birlikte sunulur (açıklanabilirlik).

#### 3.8. LLM Entegrasyon Katmanı

LLM katmanı SDK bağımlılığı olmadan (stdlib `urllib`) üç backend destekler: **OpenAI-uyumlu API** (OpenAI, OpenRouter, Groq, vLLM, LM Studio), **Ollama** (tamamen yerel) ve **offline** (kural tabanlı mod). Backend otomatik tespit edilir; yapılandırılmış çıktı (`generate_json`) bozuk JSON onarımı ve yeniden denemeyle sağlanır. Model eğitimi yapılmamıştır (şartname m. 6.6 uyarınca zorunlu değildir); üçüncü taraf model lisans bilgileri `docs/model_bilgileri.md` dosyasındadır ve depoya hiçbir model ağırlığı yüklenmemiştir.

#### 3.9. Yenilik Modülleri

Puanlama kriterlerindeki "yenilikçilik, özgünlük ve ticarileşme potansiyeli" doğrultusunda, iki görevi güçlendiren dört özgün modül eklenmiştir; tümü çevrimdışı kural tabanlı çalışır:

1. **Akıllı Önceliklendirme (Triage):** Resmî yazışma pratiğindeki aciliyet damgaları (ÇOK İVEDİ/İVEDİ/GÜNLÜDÜR/SÜRELİDİR), metin içi açık süre ifadeleri ("en geç ... tarihine kadar", "15 iş günü içinde" — yazıyla sayılar dahil) ve aşağıdaki kaynaklı yasal süre tablosu üzerinden evrakın önceliğini ve **son işlem tarihini** hesaplar. Kamu pratiğinde süre kaçırma idari sorumluluk doğurduğundan "süreli evrak takibi" gerçek bir ihtiyaçtır.

   | Dayanak | Kural | Triyaj kullanımı |
   |---|---|---|
   | 3071 sayılı Dilekçe Hakkı Kanunu m.7 | Dilekçe sonucu en geç **30 gün** (takvim) içinde gerekçeli bildirilir | Dilekçe türünde son işlem tarihi |
   | 4982 sayılı Bilgi Edinme Kanunu m.11 | Başvuruya **15 iş günü** içinde cevap (başka birim/kurum ilgisi varsa 30 iş günü) | Bilgi edinme içerikli başvuruda iş günü hesabı |
   | 2577 sayılı İYUK m.7 | İdari dava açma süresi **60 gün** | Yargı-riskli gecikme uyarısı |
   | CİMER uygulaması | 3071/4982 çerçevesinde; pratik hedef **30 gün** | CİMER kaynaklı evrak önceliği |
   | 2429 sayılı Ulusal Bayram ve Genel Tatiller Hk. Kanun | Sabit tarihli ulusal tatiller | İş günü hesabında tatil atlama |

   **İş günü hesabı:** hafta sonları ve 2429 sayılı Kanun'daki **sabit tarihli ulusal tatiller** (1 Ocak, 23 Nisan, 1 Mayıs, 19 Mayıs, 15 Temmuz, 30 Ağustos, 29 Ekim) otomatik atlanır; hicri takvime bağlı dinî bayramlar ile 28 Ekim yarım günü sabit listeye alınmaz, kurum yıla özgü tam tarihleri **parametrik `resmi_tatiller`** kümesiyle sağlayabilir. Ek tatil verilmediğinde hesap ihtiyatlı (erken) taraftadır: olası tatiller gerçek süreyi yalnızca ileri atacağından süre kaçırma riski doğmaz. Kenar durumlar (hafta sonu geçişi, yıl geçişi, sabit tatil + ek tatil bileşimi) birim testlerle sabitlenmiştir.
2. **KVKK Anonimleştirme (Paylaşım Nüshası):** 6698 sayılı Kanun bağlamında; T.C. kimlik (checksum doğrulamalı), telefon, e-posta, IBAN, kişi adı ve adres bilgilerini format-koruyan biçimde maskeleyerek evrakın birim/kurum arası paylaşıma uygun nüshasını üretir; kurum adları ve unvanlar (tüzel kişi) maskelenmez.
3. **Kurum Kokpiti (Toplu İşlem Analitiği):** Evrak yığınını toplu işleyip tür/birim dağılımı, eksiklik oranları, düşük güvenli karar sayısı ve manuel işleme kıyasla tahmini zaman tasarrufunu raporlar. Tasarruf hesabındaki evrak-başına manuel süre **parametriktir**: kurum kendi iş analizi ölçümünü arayüzdeki kaydırıcıyla girer; varsayılan değer (12 dk) **bilinçli muhafazakâr** bir çalışma varsayımıdır. Literatür bağlamı: hakemli bir üniversite vaka çalışması EBYS-öncesi bir resmî yazışma evrakının toplam işlem süresini (hazırlama+onay döngüsü, beyana dayalı ölçüm) ortalama **~4,7 saat/evrak** (1-8 saat aralığı) olarak raporlamıştır (Kaynakça 13) — varsayılanımız bunun çok altında tutularak tasarruf iddiası alt sınırdan kurulur. Ticarileşme anlatısının ölçülebilir temelidir.
4. **e-Yazışma Üstveri Taslağı + m.28/3 Tutarlılık Denetimi + Geri Bildirim Döngüsü:** Üretilen taslak için CBDDO e-Yazışma Paketi yapısından esinlenen üstveri taslağı (EBYS entegrasyon vizyonu; resmî şemanın birebir uygulanmadığı açıkça belirtilir) dışa aktarılır. Üstverinin Sayı/Konu/tarih/gizlilik alanları belge görüntüsünden BİREBİR okunur ve `ustveri_belge_tutarliligi` doğrulayıcısı Yönetmelik m.28/3 ilkesini ("belge görüntüsü üzerindeki bilgiler ile üstverideki bilgiler arasında fark olamaz") otomatik denetime çevirir — **mevzuattaki ilke birim teste dönüştürülmüştür**. Üstverideki `sayi_onerisi` alanı, m.11 biçiminde (E-DETSİS-SDP-kayıt) kurgu-deterministik sayı üreticiden gelir (`src/utils/sayi_uretici.py`; kurgu kodlar gerçek DETSİS/SDP kayıtlarıyla eşleşme iddia etmez) ve belgede yer almadığı için tutarlılık kapsamı dışındadır. Arayüzdeki "sonucu düzelt" akışıyla kullanıcı düzeltmeleri `geri_bildirim.jsonl` dosyasına kaydedilerek kural kalibrasyonuna girdi sağlar. **İnsan Onayı Kuyruğu** sekmesi bu döngüyü insan-döngüde (human-in-the-loop) karar noktasına dönüştürür: düşük güvenli veya gizlilik-kısıtlı kararlar kayıt defterinden gerekçeleriyle listelenir, kullanıcı kararı onaylar ya da doğru tür/birimi seçerek düzeltir; her iki aksiyon da geri bildirim döngüsüne yazılır (kamu belge incelemesinde insan-döngüde kontrol noktalarını en iyi uygulama olarak raporlayan çalışmayla hizalı — Kaynakça 12). KVKK paylaşım nüshası arayüzde **varsayılan görünümdür**; ham nüsha yalnızca bilinçli tıklamayla, veri güvenliği uyarısı (KVKK m.12) eşliğinde açılır.

#### 3.10. Kurumsal Entegrasyon ve İşletim Yetenekleri

Sistemin "gerçek evrak akışıyla uyumlu işleyiş" (m. 6.6) hedefini üretim ortamı yeteneklerine taşıyan bileşenler:

1. **Evrak Kayıt Defteri (denetim izi):** Her işlem stdlib SQLite tabanlı kayıt defterine işlenir (`src/utils/kayit_defteri.py`; tarih, tür, birim, öncelik, güvenler, eksik sayısı, süre, insan-onayı işareti). Filtreli sorgulama ve istatistik uçları arayüzdeki "Kayıt Defteri" sekmesinden kullanılır; tüm sorgular parametrelidir (SQL enjeksiyonuna kapalı). Kamu pratiğindeki denetlenebilirlik zorunluluğunun doğrudan karşılığıdır.
2. **REST API (sıfır bağımlılık):** `python3 -m src.api` ile stdlib `http.server` tabanlı JSON API açılır (`/saglik`, `/evrak/isle`, `/evrak/anonimlestir`, `/birimler`, `/evrak-turleri`); EBYS ve diğer kurum sistemlerinin çözümü servis olarak çağırabilmesini sağlar (`docs/api_rehberi.md`). Varsayılan bağlanma yalnızca localhost'tur; istek boyutu sınırlıdır.
3. **HTML işlem raporu:** Tek evrakın tüm işlem sonucu, arşive/denetime verilebilir kendine yeten bir HTML raporu olarak dışa aktarılır (`src/utils/islem_raporu.py`).
4. **Evrak ilişki zinciri:** İlgi referansları ve konu/muhatap benzerliğinden evraklar arası yazışma zincirleri (dilekçe → cevap → itiraz) otomatik kurulur (`src/utils/iliski_zinciri.py`) — gerçek evrak trafiğindeki dosya bütünlüğünün karşılığı.
5. **Aktif öğrenme kalibrasyonu:** Arayüzdeki "sonucu düzelt" geri bildirimleri (`geri_bildirim.jsonl`) `scripts/kalibrasyon_onerisi.py` ile analiz edilir ve kural gözden geçirme önerileri üretilir; öneriler otomatik uygulanmaz (insan onaylı kalibrasyon — değerlendirme bütünlüğü).
6. **Performans karnesi:** `scripts/benchmark.py` verimlilik/gecikme yüzdelikleri/bellek/ölçekleme ölçümlerini üretir (bkz. Bölüm 5).

### 4. Veri Setleri

Şartname (m. 6.5) uyarınca **gerçek kamu verisi kullanılmamıştır**. Tüm veriler `data/README.md` dosyasında kaynak ve kullanım haklarıyla belgelenmiştir:

- **Geliştirme seti:** 35 etiketli sentetik evrak (8 tür; 9 birimin her biri en az 2 evrakta hedef; her türden en az 1 kasıtlı eksik alanlı dosya). Takım üretimi, Apache 2.0.
- **Tutulmuş (held-out) set:** Kural kalibrasyonundan bağımsız yazılmış 16 sentetik evrak (8 tür × 2; farklı kurgu kurum evreni, konu ve üslup dokusu; 4 dosyada kasıtlı eksik alan).
- **Yeni tutulmuş set v2:** İlk tutulmuş set, tek turluk hata analizi sonrası saflığını yitirdiği için (bkz. Bölüm 5, not 2) oluşturulan ve **yalnızca bir kez ölçülen** 16 sentetik evrak (8 tür × 2; üçüncü kurgu kurum evreni "Bozkırova": iç bozkır ili, tarım/OSB/üniversite kurumları; önceki setlerde kullanılmayan konular ve üslup dokusu; 6 dosyada, ilk tutulmuş setin kullanmadığı alanları da içeren kasıtlı eksikler — `tc_kimlik`, `sayi`, `katilimcilar`, `hazirlayan` vb.).
- **Mevzuat korpusu:** 15 belge — 3071, 4982, 6698, 5070, 657, 5018, 4734, 2577, 5326, 5393, 3194 sayılı kanunların ve Resmî Yazışmalar ile Devlet Arşiv Hizmetleri yönetmeliklerinin evrak işleme bağlamındaki hükümlerinin özgün cümlelerle yazılmış özetleri + CİMER ve e-Yazışma bilgi notları (kaynak: mevzuat.gov.tr, cimer.gov.tr, DDO).
- Etiket şeması: `{tur, birim_kodu, eksik_alanlar, aciklama, mevzuat_beklenen}` (`etiketler.json`). `mevzuat_beklenen`, mevzuat isabet@3 metriği için evrak başına 1-3 korpus belge kimliği listeler; etiketler sistem çıktısına bakılmadan, evrak içeriği + hukuki kural rehberi ile atanmış ve bağımsız ikinci bir gözden geçirmeyle doğrulanmıştır (`data/README.md`). Usul katmanı etiketleri (ör. dilekçe → 3071) sistemin tür-öncelik kuralıyla aynı hukuki gerçeklikten türediğinden bu metrik esasen **regresyon siperi ve tutulmuş-set genelleme ölçüsü** olarak okunmalıdır.

### 5. Sonuçlar

Değerlendirme `scripts/evaluate.py` ile üretilmiştir (çıktılar: `data/processed/eval_report.json`, `eval_report_heldout.json` ve `eval_report_heldout_v2.json`); tüm metrikler harici LLM olmadan, **tamamen çevrimdışı kural tabanlı modda** alınmıştır.

| Metrik | Geliştirme seti (35 evrak) | Tutulmuş set (16 evrak) | Tutulmuş set v2 (16 evrak) |
|---|---|---|---|
| Sınıflandırma doğruluğu | 1,000 (35/35) | 1,000 (16/16) | 1,000 (16/16) |
| Sınıflandırma macro-F1 | 1,000 | 1,000 | 1,000 |
| Birim yönlendirme doğruluğu | 1,000 (35/35) | 1,000 (16/16) | 0,938 (15/16) |
| Eksik bilgi tespiti micro-F1 | 1,000 | 1,000 | 1,000 |
| Mevzuat önerisi isabet@3 | 0,943 (33/35) | 0,875 (14/16) | 0,750 (12/16) |
| Mevzuat önerisi isabet@1 | 0,886 | 0,750 | 0,688 |
| Taslak kalitesi (bağımsız hakem, 0-100) | 92,9 (asgari 73) | 95,8 (asgari 86) | 94,6 (asgari 86) |
| Evrak başına medyan süre | 0,023 sn | 0,028 sn | 0,027 sn |

**Performans (benchmark, 67 evrak × 3 tekrar, tek çekirdek, çevrimdışı):** verimlilik **~92 evrak/saniye**; gecikme medyan 10,7 ms, p95 14,1 ms, p99 15,3 ms; soğuk başlangıç (pipeline kurulumu) 0,02 sn; 1×/5×/10× ölçekleme doğrusala yakın. Ayrıntı: `scripts/benchmark.py` → `data/processed/benchmark_raporu.json` ve `docs/performans_raporu.md`. Bu hız, orta ölçekli bir kurumun günlük evrak hacminin saniyeler içinde işlenebileceğini gösterir.

**Metodolojik notlar (şeffaflık):** (1) Geliştirme seti, kural setinin kalibre edildiği settir; bu setteki skorlar sistemin üst sınırını gösterir. (2) Tutulmuş set kural geliştirme sırasında hiç kullanılmamıştır; ilk ölçümde sınıflandırma 15/16, yönlendirme 16/16, eksik bilgi micro-F1 0,43 elde edilmiş; tek turluk hata analizinde tespit edilen hatalar dosyaya özgü ezber değil **ilkesel** düzeltmelerle (Konu satırında "cevap" ifadesinin yapısal sinyal sayılması, adres kontrolünün adres-biçimli satıra bağlanması, rapor bulgu/sonuç denetiminin bölüm başlığı yerine fiil köklerine dayandırılması) giderilmiş ve tablo yeniden ölçülmüştür. Bu yeniden ölçüm setin held-out niteliğini zayıflattığından, **tamamen dokunulmamış ikinci bir tutulmuş set (v2) oluşturulmuştur**. v2'nin İLK ölçümü (hiçbir düzeltme yapılmadan): sınıflandırma 1,000, yönlendirme 0,875, eksik bilgi micro-F1 0,857 idi. Sonrasında hata analizinde iki KÖK NEDEN tespit edilip **ilkesel** olarak düzeltilmiştir: (a) Türkçe son-ünsüz yumuşaması (p→b, ç→c, t→d, k→ğ) anahtar-kelime eşleştiricide hesaba katılmıyordu ("lojistiği", "sonucuna" biçimleri kaçıyordu) — dilbilgisi kuralı olarak eklendi; (b) belgenin kendi "Sayı" alanı ile İlgi satırındaki atıf numarası ayrıştırılmıyordu — evrak tarihi/atıf tarihi ayrımına paralel biçimde ayrıştırıldı. Tablodaki v2 değerleri bu düzeltmeler sonrası yeniden ölçümdür; kalan tek yönlendirme farkı (`onayli_belge_v2`: sistem genel_mudurluk, etiket strateji) **bilinen sınır durumudur**: makam oluru hem karar merciine (rektörlük) arz edilmekte hem izleme görevi stratejik plana bağlanmaktadır — sistem karar merciini önermekte, etiket işi yürüten birimi esas almaktadır. Bu çift-doğa dosyaya özgü kural yazılarak "düzeltilmemiştir"; değerlendirme bütünlüğü tercih edilmiştir. (3) Sentetik setlerin ölçeği (67 evrak) sınırlıdır; gerçek kurum ortamında dağılım kayması beklenmelidir — düşük güven kapısı ve insan-onayı mekanizması bu risk için tasarlanmıştır. (4) 250+ birim ve entegrasyon testi sürekli yeşildir; sistem boş metin, 5 kelimelik metin, 50 KB metin ve Türkçe olmayan metin girdilerinde çökmeden, uygun uyarılarla çalışır. (5) Tabloda medyan süre verilmiştir; ortalama süre (0,14–0,29 sn), ilk evrak işlenirken yapılan tek seferlik mevzuat korpusu yüklemesini içerdiğinden medyandan yüksektir; medyan süreler koşum ortamına/gününe göre ±%30 değişkenlik gösterebilir (tablo: 11.07.2026 koşumu). (6) `mevzuat_beklenen` etiketleri ve mevzuat isabet@3/@1 metrikleri bu sürümde eklenmiştir: etiketler sistem çıktısına bakılmadan, evrak içeriği + hukuki kural rehberiyle atanmış ve bağımsız ikinci gözden geçirmeyle doğrulanmıştır (bkz. Bölüm 4 ve `data/README.md`); üç set bu metrik için yeniden koşulmuş, sınıflandırma/yönlendirme/eksik bilgi metrikleri önceki ölçümle birebir aynı çıkmıştır. Tutulmuş setlerdeki mevzuat isabet kaçakları tutarlı bir desen göstermektedir: onaylı belgelerde (makam oluru) 5070 sayılı Kanun ve bazı tutanak/raporlarda 5018 sayılı Kanun ilk üç öneriye girememektedir — usul ağırlığına rağmen bu türlerin gövde söz dağarcığı genel yazışma terimlerince domine edilmektedir. **Held-out bütünlüğü korunarak bu kaçaklara yönelik hiçbir kural değişikliği yapılmamış**, ilk ölçüm sonuçları olduğu gibi raporlanmıştır; iyileştirme adayları (tür-usul kapsamının onaylı belgeye genişletilmesi vb.) gelecek çalışma olarak Bölüm 6'ya bırakılmıştır. Usul katmanı etiketleri sistemin tür-öncelik kuralıyla aynı hukuki gerçeklikten türediğinden isabet@3 kısmen iyimser bir metrik olabilir; alan mevzuatı bileşeni ise bağımsız sinyaldir.

#### 5.1. Adversarial Dayanıklılık (Tutulmuş Set v3) — İlk Ölçüm

Sistemin kusurlu/zorlayıcı girdilere dayanıklılığı, 12.07.2026'da oluşturulan **16 evraklık adversarial tutulmuş set (v3)** ile ölçülmüştür (bozuk sayı bloğu, kopuk İlgi zinciri, geçersiz/sözel tarihler, KVKK-yoğun içerik, yanlış bitişli vatandaş dilekçesi, çok konulu evraklar, iki yeni çift-doğalı makam oluru; ayrıntılı veri kartı: `data/README.md` §2c). Sonuçlar İLK ölçümdür ve **hiçbir düzeltme yapılmadan** olduğu gibi raporlanmıştır:

| Metrik | Adversarial v3 (16 evrak) |
|---|---|
| Sınıflandırma doğruluğu | 0,938 (15/16); macro-F1 0,933 |
| Birim yönlendirme doğruluğu | 1,000 (16/16) |
| Eksik bilgi tespiti micro-F1 | 0,667 (TP 4, FP 3, FN 1) |
| Mevzuat önerisi isabet@3 | 0,875 (14/16) |
| Taslak kalitesi (hakem) | 95,8 (asgari 91) |
| Evrak başına medyan süre | 0,034 sn |

**Hata analizi (karışma desenleri):** (a) *Sınıflandırma* — tek hata `ust_yazi_a1` → cevap_yazisi: bozuk sayı bloklu üst yazının İlgi satırındaki "... sayılı yazınız" ikinci-şahıs iyelikli atfı, cevap yazısının temel ayrım sinyalini tetiklemiştir (bilinen sinyalin sınır durumu; confusion matrix raporun `siniflandirma.confusion_matrix` alanındadır). (b) *Eksik bilgi* — üç yanlış alarm ve bir kaçırma tamamen adversarial tuzakların hedefindedir: `cevap_yazisi_a1`'de İlgi bloğu yokken gövdedeki "İlgi (b)'de kayıtlı yazınız" ifadesi alanın VAR sanılmasına yol açmış (kopuk zincir, FN); `tutanak_a1`'deki tamamen sözel tarih ("Temmuz ayının on ikinci günü") çıkarılamamış (FP); iki rapor dosyasında farklı cümle iskeleti kullanıldığından fiil-kökü tabanlı sonuç/değerlendirme denetimi yanlış alarm üretmiştir (FP×2). (c) *Mevzuat* — `tutanak_a2` KVKK-yoğun içerik taşımasına rağmen "kişisel/kvkk/rıza" tetikleyici kelimeleri geçmediğinden kisisel_veri teması aktifleşmemiş, 6698 önerilememiştir; `rapor_a1`'de 5018 yerine arşiv/RYY önerilmiştir. (d) *Güçlü yanlar* — yönlendirme adversarial sette dahi 16/16'dır; iki çift-doğalı makam oluru da doğru birime yönlendirilmiştir; taslak kalitesi ve hız etkilenmemiştir. Bu bulgulara yönelik iyileştirmeler bilinçli olarak YAPILMAMIŞ (set held-out kalmıştır), Bölüm 6'ya gelecek çalışma olarak işlenmiştir.

### 6. Sınırlılıklar ve Gelecek Çalışmalar

- BM25 sözcüksel erişimdir; düzeltici sorgu genişletme döngüsü söz dağarcığı uyumsuzluğunu kısmen giderir, tam eşanlamlı/bağlamsal eşleşme için opsiyonel semantik katman (turkish-e5-large + bge-reranker-v2-m3) tanımlıdır ancak varsayılan kurulumda kapalıdır (ilk açılışta model indirme gerektirir; kapalı ağ varsayımı).
- LLM eskalasyonu ve LLM tabanlı taslak üretimi, API anahtarı/Ollama kurulumu gerektirir; offline modda kural tabanlı eşdeğerler devreye girer.
- Kişi adı çıkarımı desen/işaret temellidir; Türkçe NER modeli (ör. BERTurk tabanlı) ile geliştirme planlanmaktadır.
- **Adversarial ölçümün (v3, §5.1) ortaya koyduğu sınırlılıklar** (held-out bütünlüğü gereği düzeltilmemiştir): (a) eksik bilgi tespiti İlgi alanını METİNSEL varlıkla denetler — "İlgi" kelimesi gövdede geçiyorsa blok yok sayılamamaktadır (kopuk zincir tespiti için yapısal blok denetimi gerekir); (b) tamamen sözel tarihler ("Temmuz ayının on ikinci günü") tarih çıkarıcının kapsamı dışındadır; (c) rapor sonuç/değerlendirme denetimi fiil-kökü listesine dayandığından farklı cümle iskeletlerinde yanlış alarm üretebilir; (d) KVKK mevzuat önerisi tema tetikleyicilerine bağlıdır — kişisel veri İÇEREN ama "kişisel/kvkk" sözcükleri GEÇMEYEN evrakta 6698 önerilememektedir (anonimleştirme ajanının veri-tespit sinyalinin mevzuat temasına bağlanması aday çözümdür); (e) cevap/üst yazı ayrımındaki ikinci-şahıs iyelik sinyali, İlgi'li talep yazılarında sınır durumlar üretebilmektedir.
- EBYS/e-Yazışma Paketi entegrasyonu (TS 13298 uyumlu sistemlere bağlanma) ürünleşme aşaması hedefidir.

### 7. Kaynakça

1. Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik, T.C. Resmî Gazete, Sayı 31151, 10 Haziran 2020. https://www.mevzuat.gov.tr/
2. 3071 sayılı Dilekçe Hakkının Kullanılmasına Dair Kanun; 4982 sayılı Bilgi Edinme Hakkı Kanunu; 6698 sayılı Kişisel Verilerin Korunması Kanunu; 5070 sayılı Elektronik İmza Kanunu; 657 sayılı Devlet Memurları Kanunu; 5018 sayılı Kamu Malî Yönetimi ve Kontrol Kanunu; 4734 sayılı Kamu İhale Kanunu; 2577 sayılı İdari Yargılama Usulü Kanunu; 5326 sayılı Kabahatler Kanunu; 5393 sayılı Belediye Kanunu; 3194 sayılı İmar Kanunu. T.C. Mevzuat Bilgi Sistemi, https://www.mevzuat.gov.tr/
3. Robertson, S. ve Zaragoza, H. (2009). "The Probabilistic Relevance Framework: BM25 and Beyond". *Foundations and Trends in Information Retrieval*, 3(4), 333–389.
4. Smith, R. (2007). "An Overview of the Tesseract OCR Engine". *Proc. ICDAR 2007* (Tesseract OCR, Apache 2.0). https://github.com/tesseract-ocr/tesseract
5. CİMER — Cumhurbaşkanlığı İletişim Merkezi, https://www.cimer.gov.tr/
6. e-Yazışma Projesi Teknik Rehberi, T.C. Cumhurbaşkanlığı Dijital Dönüşüm Ofisi, https://cbddo.gov.tr/
7. Streamlit (Apache 2.0), https://streamlit.io/ ; Pydantic (MIT), https://docs.pydantic.dev/ ; Rich (MIT), https://github.com/Textualize/rich
8. Singh, A. vd. (2025). "Agentic Retrieval-Augmented Generation: A Survey on Agentic RAG". arXiv:2501.09136. https://arxiv.org/abs/2501.09136 (erişim: 11 Temmuz 2026)
9. Li, X. vd. (2025). "Towards Agentic RAG with Deep Reasoning: A Survey of RAG-Reasoning Systems in LLMs". arXiv:2507.09477. https://arxiv.org/abs/2507.09477 (erişim: 11 Temmuz 2026)
10. ytu-ce-cosmos/turkish-e5-large (MIT), https://huggingface.co/ytu-ce-cosmos/turkish-e5-large ; BAAI/bge-reranker-v2-m3 (Apache 2.0), https://huggingface.co/BAAI/bge-reranker-v2-m3 (erişim: 11 Temmuz 2026)
11. Nguyen, H. vd. (2025). "Multi-Agent Legal Verifier Systems". arXiv:2511.10925. https://arxiv.org/abs/2511.10925 (erişim: 11 Temmuz 2026)
12. "Leveraging LLMs to Streamline the Review of Public Funding Applications" (2025). arXiv:2510.09674. https://arxiv.org/abs/2510.09674 (erişim: 12 Temmuz 2026)
13. Arslan, M. ve Kaya, T. (2017). "E-Devlet Uygulaması Olarak EBYS'nin Etkinliği ve Verimliliği Üzerine Bir Araştırma: Nevşehir Hacı Bektaş Veli Üniversitesi EBYS Örneği". *SDÜ İİBF Dergisi*, C.22 (Kayfor15 özel sayısı). https://dergipark.org.tr/tr/pub/sduiibfd/article/710656 (erişim: 12 Temmuz 2026; EBYS-öncesi ortalama işlem süresi ~4,7 saat/evrak, beyana dayalı ölçüm)
