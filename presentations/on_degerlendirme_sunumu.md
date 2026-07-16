# Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi

- TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması (1. Senaryo)
- Ön Değerlendirme Sunumu
- [TAKIM ADI]
- 12 Temmuz 2026

> not: Açılış: takımı ve proje adını tanıt. Tek cümlelik özet: "Kamu kurumlarına gelen evrakı okuyan, anlayan, eksiklerini bulan, mevzuat öneren, resmî yazı taslağı hazırlayıp doğru birime yönlendiren çok ajanlı bir sistem geliştirdik — ve çalışan hali şu an elimizde."

---

# Takım Yapısı

- Muhammed Sina Gün — [Takım Kaptanı / Mimari ve Backend Geliştirme]
- Şeymanur Çebi — [Veri Setleri, Ajan Geliştirme ve Değerlendirme]
- [ÜYE 3] — [NLP / Mevzuat RAG]
- [ÜYE 4] — [Arayüz ve Demo]
- [Danışman: VARSA EKLEYİN]

> not: Her üyenin projedeki somut sorumluluğunu bir cümleyle anlat. Köşeli parantezli alanlar teslimden önce doldurulacak.

---

# Motivasyon ve Gerekçeler

- Kamu kurumlarında evrak akışı: çok adımlı, tekrarlı, manuel ve personele dağılmış bir süreç zinciri
- Gerekçe 1 — Ölçülebilir verimlilik: ilk inceleme, taslak ve yönlendirme adımlarında personel zamanı kazanımı
- Gerekçe 2 — Veri egemenliği: KVKK gereksinimlerine uygun, tamamen yerel (offline) çalışabilen yerli çözüm ihtiyacı
- Gerekçe 3 — Açık kaynak katkısı: Türkçe dil teknolojileri ekosistemine (TAKP) Apache 2.0 lisanslı katkı
- Gerekçe 4 — Takımın Türkçe NLP ve kamu süreçleri alanındaki ilgi ve birikimi

> not: Şartnamenin ön değerlendirme beklentisi: motivasyonu GEREKÇELERİYLE sunmak. Dört gerekçeyi tek tek vurgula; KVKK/yerellik vurgusu jüri için ayırt edici.

---

# Hedeflenen Proje: İki Zorunlu Görev, Tek Akış

- Görev 1 — Evrak Sınıflandırma ve İçerik Analizi:
  - OCR veya doğrudan metin okuma (TXT, PDF, görüntü)
  - Evrak türü belirleme (9 tür) + güven skoru
  - Önemli bilgi unsurlarını çıkarma (tarih, sayı, T.C. kimlik, ilgi, muhatap...)
  - Eksik bilgi tespiti (türe özgü zorunlu alanlar)
  - İlgili mevzuat ve yazışma kuralı önerisi
  - Kısa ve öz özet üretimi
- Görev 2 — Resmî Yazı Taslaklama ve Birim Yönlendirme:
  - Üst yazı / cevap yazısı / bilgilendirme / eksik bilgi talep yazısı taslağı
  - Resmî üslup ve Yönetmelik biçim uyumu
  - Gerekçeli birim yönlendirme önerisi
  - Kullanıcıya süreç bilgilendirmesi ve eksik bilgi talebi

> not: Şartname m.6.4'teki 6+5 yeteneğin TAMAMININ karşılandığını vurgula. İki görev tek orkestratör altında uçtan uca çalışıyor — değerlendirme kriteri de uçtan uca bütünlük.

---

# Teknik Mimari: 11 Uzman Ajan + Orkestratör

- Her ajan tek sorumluluk üstlenir: OCR, Sınıflandırma, Bilgi Çıkarımı, Eksik Bilgi, Mevzuat (RAG), Önceliklendirme/Triyaj (aciliyet + yasal süre), Özet, KVKK Anonimleştirme (PII maskeleme), Taslak Yazımı, Yönlendirme, Bilgilendirme
- Framework bağımsız, saf Python orkestrasyon; ajanlar paylaşılan durum nesnesi (AgentState) üzerinden haberleşir
- Akış düz zincir değil — 3 koşullu kapı:
  - Okunabilirlik kapısı: boş/bozuk metinde uydurma çıktı üretilmez
  - Dil sezimi kapısı: Türkçe olmayan metinde taslak üretimi durdurulur
  - Düşük güven kapısı: güven < 0,6 ise "insan onayı gerekli" + alternatif adaylar
- Her adımın süresi ve durumu ölçülür (izlenebilirlik / denetlenebilirlik)

> not: "Çok ajanlı" iddiasının içini doldur: her ajanın tek sorumluluğu var, orkestratör koşullu akış yürütüyor. Kapılar = halüsinasyon önleme + insan gözetimi. Bu slayt Yöntem/Teknik Yaklaşım (35p) kriterinin merkezi.

---

# Yöntem — Görev 1

- Sınıflandırma: ağırlıklı anahtar kelime + 20'den fazla yapısal sinyal ("İlgi:" bloğu, TUTANAK/GENELGE/OLUR başlıkları, kurumsal antet-dilekçe ayrımı) → softmax ile kalibre güven skoru
- Bilgi çıkarımı: doğrulamalı desen eşleştirme — T.C. kimlik resmî checksum ile doğrulanır; evrak tarihi, atıf tarihlerinden ayrıştırılır
- Eksik bilgi: türe özgü zorunlu alan setleri (ör. dilekçede 3071 sayılı Kanun unsurları) + öncelik (kritik/önemli) + giderme önerisi
- Mevzuat önerisi: 15 belgelik kamuya açık korpus üzerinde saf Python BM25-Okapi RAG + evrak türüne koşullu yeniden sıralama
- Özet: skorlamalı extractive özet (konum + anahtar kelime örtüşmesi + işaret ifadeleri)
- LLM erişilebilirse: düşük güvenli kararlarda yapılandırılmış (JSON şemalı) LLM eskalasyonu

> not: Derinlik vurgusu: checksum doğrulaması, tarih ayrıştırma, türe koşullu yeniden sıralama gibi ayrıntılar yüzeysel keyword-matching olmadığını gösteriyor. BM25'in saf Python ve bağımlılıksız olduğunu söyle.

---

# Yöntem — Görev 2

- Taslak üretimi iki katmanlı: LLM istemli üretim (varsa) / şablon + kural tabanlı gövde kurulumu (her zaman)
- Resmî Yazışmalar Yönetmeliği'ne uygun biçim öğeleri: antet, sayı, tarih, konu, muhatap, ilgi, imza bloğu, dağıtım
- Format öz-denetimi: üretilen her taslak 9 kurallı yönetmelik kontrol listesinden geçer, format skoru raporlanır
- Hitap-kapanış uyumu: üst makama "arz ederim", alt/eş makama "rica ederim", kişiye "saygılarımla"
- Yönlendirme: 9 birimlik organizasyon şeması, Türkçe ek çekimine dayanıklı eşleştirme, gerekçe metniyle açıklanabilir öneri
- Kritik eksik içeren başvurularda otomatik eksik bilgi talep yazısı; kurum içi evrakta iade/ikmal notu
- LLM katmanı: SDK'sız (stdlib), OpenAI-uyumlu API / Ollama (yerel) / offline — otomatik tespit

> not: Format öz-denetimi özgün bir katkı: sistem kendi çıktısını yönetmeliğe göre puanlıyor. Offline-first vurgusu: LLM yoksa bile HER yetenek çalışıyor.

---

# Uygulama Durumu: Çalışan Sistem

- Uçtan uca çalışır durumda: CLI + Streamlit web arayüzü + konsol demo senaryosu
- 632 birim ve entegrasyon testi sürekli yeşil (`pytest tests/`, 16.07.2026)
- Bağımlılık disiplini: çekirdek kurulum minimal; OCR/semantik arama/LLM opsiyonel katman
- Değerlendirme aracı (scripts/evaluate.py): sınıflandırma, yönlendirme, eksik bilgi ve süre metriklerini otomatik raporlar
- 100 etiketli sentetik evrak (52 geliştirme + 16 tutulmuş v1 + 16 tutulmuş v2 + 16 adversarial v3) + 15 belgelik mevzuat korpusu
- Apache 2.0 açık kaynak; tüm dokümantasyon Türkçe; model ağırlığı depoya yüklenmez

> not: "Hedefliyoruz" değil "çalışıyor" — ön değerlendirmede en güçlü kart. Uygulama (35p) kriterine doğrudan oynuyor. Sentetik veri ve lisans uyumu şartname m.6.5 ve m.7'yi karşılıyor.

---

# Ölçülebilir Başarım (Tamamen Çevrimdışı Modda)

- Geliştirme seti (52 evrak): sınıflandırma 1,000 - yönlendirme 0,962 - eksik bilgi F1 1,000 - mevzuat isabet@3 0,962
- Tutulmuş set v1 (16 evrak): sınıflandırma 1,000 - yönlendirme 1,000 - eksik bilgi F1 1,000
- Tutulmuş set v2 (16 evrak): sınıflandırma 1,000 - yönlendirme 0,938 - eksik bilgi F1 1,000
  - İlk ölçümü 1,000 / 0,875 / 0,857 idi; hata analizinde bulunan İKİ kök neden
    (Türkçe ünsüz yumuşaması + belge "Sayı"sı ↔ İlgi atıf no ayrımı) DOSYAYA ÖZGÜ
    ezber olmadan İLKESEL düzeltilip yeniden ölçüldü. Bu düzeltme v2'nin saflığını
    zayıflattığı için, ↓ tamamen dokunulmamış v3 oluşturuldu.
- **Adversarial set v3 (16 evrak, HİÇ DOKUNULMAMIŞ, TEK SEFER ölçüldü):**
  sınıflandırma 0,938 - **yönlendirme 1,000** - eksik bilgi F1 0,667 - mevzuat isabet@3 0,875 - taslak kalitesi 95,8
- Evrak başına medyan işleme süresi ~0,011-0,012 sn (kaynak: `eval_report*.json`) — gerçek zamana yakın
- Şeffaflık: geliştirme seti üst sınırı gösterir; v3 sonuçları hiçbir düzeltme yapılmadan olduğu gibi raporlanmıştır

> not: Dürüstlük burada güç: "v1 ve v2'de hata analizi sonrası İLKESEL düzeltmeler yaptık, ama bu setlerin saflığını zayıflattığı için dördüncü bir kurgu evrende (Puslupınar/Kavakdüzü) ZORLAYICI/adversarial yepyeni bir set yazıp TEK SEFER ölçtük ve sayıları olduğu gibi koyduk — bozuk sayı bloğu, kopuk İlgi zinciri, sözel tarih ve KVKK-yoğun içeriğe rağmen yönlendirme 16/16." Jüri v3 eksik-bilgi F1'ini (0,667) sorarsa: bu tam da adversarial tuzakların (gövdede olmayan İlgi'ye atıf, tamamen sözel tarih) hedefidir ve DÜZELTME YAPMADAN raporlanmıştır — sınır davranışı gizlenmedi.

---

# Demo Planı

- Streamlit arayüzünde canlı uçtan uca akış:
  - Evrak yükle (TXT/PDF/görüntü) veya metin yapıştır
  - Tür + güven skoru → çıkarılan bilgiler → eksik alanlar (öncelikli)
  - Mevzuat önerileri → özet → resmî yazı taslağı + format skoru
  - Gerekçeli birim yönlendirme + süreç bilgilendirmesi
- Adım adım süre tablosu ekranda: gerçek zamana yakın işleme canlı gösterilir
- Yedek plan: internet kesilse dahi sistem offline modda TAM işlevsel — demo garantisi
- Demo verisi: kaynağı ve kullanım hakları belgelenmiş sentetik evrak setleri

> not: Şartname demo kriterleri: gerçek zamana yakınlık avantaj, internet kesintisine yedek plan tavsiyesi, veri kaynağı beyanı zorunlu. Üçünü de tek slaytta cevaplıyoruz. Jüri canlı çalıştırma isterse: her şey yerel, riski yok.

---

# Yenilikçilik, Özgünlük ve Ticarileşme

- Özgün: framework bağımsız saf Python çok ajanlı orkestrasyon — kara kutu agent kütüphanesi yok, her karar izlenebilir
- Özgün: taslak format öz-denetimi — sistem kendi çıktısını Yönetmelik'in 9 kuralına göre puanlar
- Özgün: offline-first hibrit tasarım — LLM'siz tam işlev + LLM'li eskalasyon aynı mimaride
- Yenilikçi: düşük güven kapısı + insan onayı — kamu gerçekliğine uygun sorumlu otomasyon
- Ticarileşme: belediyeler, il müdürlükleri, üniversite yazı işleri — EBYS (TS 13298) / e-Yazışma entegrasyon yol haritası
- Ölçeklenebilirlik: model-agnostik katman sayesinde kurum kendi yerel modelini (Ollama) veya API'sini takabilir

> not: Yenilikçilik/Özgünlük/Ticarileşme (15p). "Yerinde kurulum + yerel model = veri kurumdan çıkmaz" cümlesi ticarileşme tarafında en güçlü argüman.

---

# Yol Haritası ve Kapanış

- Finale kadar: Türkçe NER modeli entegrasyonu (kişi adı çıkarımını güçlendirme)
- Finale kadar: opsiyonel hibrit semantik katmanın (turkish-e5-large + bge-reranker-v2-m3; hâlihazırda kurulu, varsayılan kapalı) GPU'lu makinede kalibrasyonu ve varsayılan açılması
- Finale kadar: kullanıcı testleri ve yeni/dokunulmamış tutulmuş setler üzerinde dürüst sürekli ölçüm
- Ürünleşme: EBYS/e-Yazışma Paketi uyumluluğu, pilot kurum çalışması
- Kod deposu: github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan (Apache 2.0)
- Teşekkürler — Sorularınızı bekliyoruz
- İletişim: [E-POSTA]

> not: Kapanışta tek cümle: "Sistem bugün çalışıyor; finale kadar hedefimiz onu daha da derinleştirmek." Soru-cevaba güvenle geç — canlı demo hazır.
