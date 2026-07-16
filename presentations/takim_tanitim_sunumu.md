# AGENTRA TECH

- Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi
- TEKNOFEST 2026 — Yapay Zeka Dil Ajanları Yarışması · 1. Senaryo
- Takım Tanıtım Sunumu
- 16 Temmuz 2026

> not: Açılış cümlesi: "Biz AGENTRA TECH'iz; kamu kurumlarına gelen evrağı okuyan, anlayan, eksiğini bulan, mevzuat öneren, resmî yazı taslağı hazırlayıp doğru birime yönlendiren çok ajanlı bir sistem geliştirdik — ve çalışan hâli bugün elimizde." Takım adı, senaryo ve dosyanın "takım tanıtım sunumu" olduğunu net söyle. Şartname: dil Türkçe.

---

# Bir Bakışta AGENTRA TECH

- Kimiz: 4 kişilik öğrenci takımı — yazılım, veri ve değerlendirme odaklı
- Senaryo: 1. Senaryo "Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi"
- Ne yaptık: 11 uzman ajan + orkestratör; iki zorunlu görevi tek uçtan uca akışta çözen çalışan sistem
- Nasıl: framework bağımsız saf Python, çevrimdışı-öncelikli (offline-first), isteğe bağlı LLM
- Kanıt: 500'ü aşkın test yeşil; tamamen çevrimdışı modda ölçülmüş, olduğu gibi raporlanan başarım
- Duruş: Apache 2.0 açık kaynak · KVKK-öncelikli · gerçek kamu verisi kullanılmaz (yalnızca sentetik)

> not: Bu slayt bir "kimlik kartı" — jüri 30 saniyede takımı ve projeyi kavrasın. Detaylar sonraki slaytlarda. "Hedefliyoruz" değil "yaptık" vurgusu.

---

# Takım Kimliği ve Amacımız

- Takım adı: AGENTRA TECH — kimliğimizin merkezinde "agent" (ajan) odağı vardır
- Kuruluş: 2026
- Amaç: Kamu kurumlarındaki evrak ve yazışma süreçlerini okuyan, anlayan, eksiğini bulan, mevzuat öneren, resmî yazı taslağı hazırlayıp doğru birime yönlendiren çok ajanlı, offline-first ve yerli bir yapay zekâ sistemiyle uçtan uca otomatikleştirmek
- Duruşumuz: kara kutu bir kütüphane değil; her kararı izlenebilir, tamamen açık kaynak (Apache 2.0) bir çözüm
- Değerlerimiz: güvenilirlik (her karar bir güven skoruyla), şeffaflık (her öneri gerekçe + madde dayanağı), veri koruması (KVKK), dürüstlük (ölçümler olduğu gibi)

> not: "Neden 'Agentra'?" — agent + Türkçe teknoloji kimliği. Amaç cümlesini yavaş oku; iki zorunlu görevin özünü içeriyor. Değerlerimiz jüri için ayırt edici: bunlar mimariye kodlanmış, slogan değil.

---

# Takım Hikâyemiz

- Nasıl bir araya geldik: [Takıma özel — ör. aynı bölüm/üniversite, ortak bir NLP dersi ya da etkinlik; kendi gerçek hikâyenizi yazın]
- Çıkış noktası: Kamuda basit bir evrağın bile birçok elden geçmesi — tekrarlı, zaman baskılı bir süreç zinciri
- Kıvılcım: "Bu ilk inceleme ve taslak işini bir ajan ekibi yapsa?" sorusu projeyi başlattı
- Yolculuk: Fikirden çalışan sisteme — 11 uzman ajan, saf Python orkestrasyon, 116 sentetik evrak ve ölçülebilir başarı
- Bugün: İki zorunlu görevi uçtan uca çalıştıran, test edilmiş, açık kaynak bir sistem

> not: Hikâye slaytı takımı insanîleştirir — köşeli parantezli "nasıl bir araya geldik" alanını gerçek hikâyenizle doldurun. Yolculuğu "fikir → çalışan sistem" yayı olarak anlat; bu yay bütün sunumun omurgası.

---

# Takım Üyeleri

- Şeyma Nur Çebi — Takım Kaptanı · Yazılım
  - Görev 1 içerik analizi: sınıflandırma, bilgi çıkarımı, mevzuat RAG; değerlendirme ve uçtan uca entegrasyon — [Bölüm / Üniversite]
- Muhammed Sina Gün — Yazılım
  - Mimari ve orkestrasyon; model-agnostik LLM katmanı; Görev 2 taslak üretimi (OCR ve özet dâhil) — [Bölüm / Üniversite]
- Emine Elik — Veri · Test · Doküman
  - Veri seti ve etiketleme; test kapsamı; dokümantasyon; sunum ve demo; şartname uyum takibi — [Bölüm / Üniversite]
- Zeynep Akel — Yazılım
  - Görev 1 eksik bilgi tespiti; Görev 2 yönlendirme ve kullanıcı etkileşimi; triyaj, KVKK anonimleştirme; web arayüzü — [Bölüm / Üniversite]
- Danışman: [Ad Soyad — Unvan / Kurum · varsa ekleyin]

> not: Her üyeyi bir cümleyle tanıt; "kim neyi geliştirdi" nettir. Kaptan Şeyma Nur Çebi. Bölüm/üniversite ve (varsa) danışman bilgisini teslimden önce doldurun. Şartname: takım tanıtımında tüm üyelerin görev tanımları yer almalı — bu slayt + sonraki slayt onu karşılar.

---

# Görev Dağılımı — Şartname m.6.4

- Görev 1 — Sınıflandırma & İçerik Analizi (m.6.4.1)
  - OCR / metin okuma → Sina · Tür belirleme (sınıflandırma) → Şeyma Nur · Bilgi çıkarımı → Şeyma Nur
  - Eksik bilgi tespiti → Zeynep · Mevzuat önerisi (BM25 RAG) → Şeyma Nur · Özet oluşturma → Sina
- Görev 2 — Taslaklama & Yönlendirme (m.6.4.2)
  - Resmî yazı taslağı → Sina · Format öz-denetimi (üslup) → Sina · Birim yönlendirme → Zeynep
  - Kullanıcı bilgilendirme → Zeynep · Eksik bilgi talebi → Zeynep
- Altyapı ve yenilik
  - Orkestratör + 3 koşullu kapı ve LLM katmanı → Sina · Triyaj ve KVKK anonimleştirme → Zeynep
  - Kurum kokpiti, e-Yazışma üstverisi, geri bildirim ve değerlendirme → Şeyma Nur · Veri, test, doküman, sunum, demo → Emine

> not: Bu slayt şartname m.6.4'teki her yeteneğin bir sorumluya VE gerçek bir kod modülüne bağlı olduğunu kanıtlar. "Kim neyi geliştirdi?" sorusunun yanıtı burada net. İki zorunlu görevin tüm yetenekleri kapsandı.

---

# Neden Bu Proje? — Motivasyonumuz

- Ölçülebilir verimlilik: ilk inceleme, taslak ve yönlendirme adımlarında personel zamanı kazanımı
- Veri egemenliği ve KVKK: kişisel veriyi 3. taraf API'ye sızdırmadan, tamamen yerel (offline) çalışabilen yerli çözüm ihtiyacı
- Açık kaynak katkısı: Türkçe dil teknolojileri ekosistemine (TAKP) Apache 2.0 lisanslı, tekrar-üretilebilir katkı
- Kamuya uygun sorumlu otomasyon: emin olunmayan kararda durup insana devreden, gerekçeli ve denetlenebilir tasarım
- Takımın ilgisi: Türkçe NLP ve kamu süreçlerine dair merak ve birikimimiz

> not: Şartname katılım motivasyonunu GEREKÇELERİYLE ister. Beş gerekçeyi tek tek vurgula; KVKK/yerellik ve "insan onayı" jüri için en ayırt edici argümanlar. Kamu senaryosunda "her şeyi otomatikleştiren" değil, "doğru yerde insana devreden" sistem güven verir.

---

# Projemiz: İki Zorunlu Görev, Tek Akış

- Görev 1 — Evrak Sınıflandırma ve İçerik Analizi
  - Metin/PDF/görüntü okuma (OCR) · tür belirleme (8 tür + güven skoru) · bilgi çıkarımı (tarih, sayı, TCKN, ilgi, muhatap…)
  - Türe özgü eksik bilgi tespiti · ilgili mevzuat önerisi (madde referanslı) · kısa özet · KVKK maskeleme
- Görev 2 — Resmî Yazı Taslaklama ve Birim Yönlendirme
  - Üst/cevap/bilgilendirme/eksik-bilgi-talep yazısı taslağı · Resmî Yazışma Yönetmeliği biçim uyumu
  - Gerekçeli birim yönlendirme · kullanıcıya süreç bilgilendirmesi ve eksik bilgi talebi
- İki görev tek orkestratör altında uçtan uca çalışır — değerlendirme de uçtan uca bütünlük üzerinden

> not: Şartname iki görevi de ZORUNLU tutar; tek görev eksikse sistem tamamlanmış sayılmaz. Biz ikisini tek akışta birleştirdik. 6+5 yeteneğin tamamı karşılanıyor. Bu slayt "ne yaptığımızı" anlatır; nasıl yaptığımız bir sonraki slaytta.

---

# Teknik Yaklaşımımız ve Özgünlüğümüz

- 11 uzman ajan + orkestratör: her ajan tek sorumluluk; paylaşılan durum (AgentState) üzerinden koordinasyon
- Framework bağımsız saf Python orkestrasyon — LangChain/LangGraph yok; şeffaf, hafif, denetlenebilir
- 3 koşullu kapı: okunabilirlik (boş/bozuk metinde uydurma yok) · dil sezimi · düşük güven → insan onayı
- Offline-first hibrit: LLM'siz tam işlev + LLM'li eskalasyon aynı mimaride (OpenAI-uyumlu / Ollama / offline)
- Mevzuat-temelli: her taslak kuralı yönetmelik madde/fıkra dayanağıyla denetlenir — halüsinasyon atıf otomatik yakalanır
- Özgün katkı: taslak format öz-denetimi — sistem kendi çıktısını yönetmeliğin kurallarına göre puanlar

> not: Bu slayt "çok ajanlı" iddiasının içini doldurur ve Yöntem/Teknik Yaklaşım (35p) kriterine oynar. Kapılar = halüsinasyon önleme + insan gözetimi. Format öz-denetimi ve saf-Python orkestrasyon en özgün iki noktamız. Takım tanıtımında derinliği özetliyoruz; ayrıntı ön değerlendirme/final sunumunda.

---

# Çalışan Sistem — Bugün

- Uçtan uca çalışıyor: CLI + Streamlit web arayüzü + konsol demo senaryosu
- 500'ü aşkın birim ve entegrasyon testi sürekli entegrasyonda yeşil
- Ölçülebilir başarım (tamamen çevrimdışı mod, kaynak: eval_report*.json):
  - Geliştirme seti (52 evrak): sınıflandırma 1,00 · yönlendirme 0,96 · eksik-bilgi F1 1,00 · mevzuat isabet@3 0,96 · taslak 93,6/100
  - Adversarial tutulmuş set (16 evrak, hiç dokunulmamış): sınıflandırma 0,94 · yönlendirme 1,00 · eksik-bilgi F1 0,83 · mevzuat@3 0,94 · taslak 95,8/100
- Her sette KVKK sızıntısı: 0 · Evrak başına saniye-altı işleme (medyan ~0,1 sn) — gerçek zamana yakın
- 116 etiketli sentetik evrak (52 geliştirme + 64 tutulmuş) + 15 belgelik mevzuat korpusu

> not: En güçlü kartımız: "hedefliyoruz" değil "çalışıyor". Uygulama (35p) kriterine doğrudan oynar. Adversarial sette yönlendirme 16/16; eksik-bilgi F1'i (0,83) düşerse bu tam da adversarial tuzakların hedefidir ve DÜZELTME YAPILMADAN raporlanmıştır — sınır davranışını gizlemiyoruz. Gerçek zamana yakınlık demo puanında avantaj.

---

# Açık Kaynak, KVKK ve Dürüstlük

- Açık kaynak: Apache 2.0 · tüm dokümantasyon Türkçe · model ağırlığı depoya yüklenmez (yalnızca bağlantı+sürüm+lisans)
- Depo: github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan
- KVKK: 9 kategori kişisel veri format-koruyarak maskelenir; sızıntı bağımsız denetçiyle ölçülür (sızıntısız oran 1,00)
- Veri ilkesi: gerçek kamu verisi ASLA kullanılmaz — yalnızca sentetik/kurgu evrak ve kamuya açık mevzuat metinleri
- Dürüstlük: ölçümler ne çıkarsa olduğu gibi raporlanır; tutulmuş setlerdeki hatalar gizlenmez, teknik raporda analiz edilir

> not: Bu slayt şartnamenin etik ve veri kurallarını (gerçek kamu verisi yasağı, açık kaynak/TAKP, Türkçe dokümantasyon) doğrudan karşıladığımızı gösterir. Dürüstlük bizim için bir güç: sınır davranışını raporlamak jüri güvenini artırır. Ödül/derece için değil, doğru iş için.

---

# Yol Haritamız — Finale Kadar

- Türkçe NER modeli entegrasyonu — kişi/kurum/yer adı çıkarımını güçlendirme
- Opsiyonel hibrit semantik katmanın (turkish-e5-large + bge-reranker) GPU'lu makinede kalibrasyonu
- Kullanıcı testleri ve yeni, dokunulmamış tutulmuş setlerde dürüst sürekli ölçüm
- Ürünleşme: belediyeler, il müdürlükleri, üniversite yazı işleri için EBYS (TS 13298) / e-Yazışma entegrasyon yol haritası
- Ölçeklenebilirlik: model-agnostik katman sayesinde kurum kendi yerel modelini (Ollama) veya API'sini takabilir — veri kurumdan çıkmaz

> not: "Sistem bugün çalışıyor; finale kadar hedefimiz onu daha da derinleştirmek." Ticarileşme tarafında en güçlü cümle: "yerinde kurulum + yerel model = veri kurumdan çıkmaz." Yenilikçilik/Özgünlük/Ticarileşme (15p) kriterine oynar.

---

# Teşekkürler — İletişim

- AGENTRA TECH — Şeyma Nur Çebi · Muhammed Sina Gün · Emine Elik · Zeynep Akel
- Proje: Kamu Evrak ve Yazışma Süreçleri için Akıllı Agent Destek Sistemi
- Depo (Apache 2.0): github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan
- İletişim: [takım e-postası]
- Sorularınızı bekliyoruz

> not: Kapanış tek cümle: "Kamuya uygun, dürüst, açık kaynak ve bugün çalışan bir sistem sunuyoruz." İletişim e-postasını doldur. Soru-cevaba güvenle geç — canlı demo hazır.
