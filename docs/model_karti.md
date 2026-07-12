# Model Kartı — Kamu Evrak Akıllı Agent Sistemi

> Bu kart, Mitchell vd. (2019) "Model Cards for Model Reporting" biçimini
> izler. Amaç: sistemin ne olduğu, nasıl değerlendirildiği ve sınırlarının
> şeffaf ve tekrarlanabilir biçimde belgelenmesi.

## 1. Model Detayları
- **Sistem:** 11 uzman ajan + saf Python orkestratör (framework bağımsız),
  çevrimdışı-öncelikli (offline-first) hibrit mimari.
- **Sürüm:** 0.4.0 · **Lisans:** Apache 2.0 · **Dil:** Türkçe
- **Yaklaşım:** Kural tabanlı çekirdek (BM25, Naive Bayes ensemble, desen
  eşleştirme) + isteğe bağlı LLM eskalasyonu (OpenAI-uyumlu / Ollama).
  Çekirdek, hiçbir LLM olmadan tam çalışır.
- **Üçüncü taraf modeller:** yalnızca isteğe bağlı katmanlarda ve depoya
  ağırlık yüklenmeden, bağlantı+sürüm+lisansla dokümante (`docs/model_bilgileri.md`).

## 2. Amaçlanan Kullanım
- **Birincil:** Kamu kurumlarına gelen evrağın sınıflandırılması, içerik
  analizi, mevzuat önerisi, resmî yazı taslağı ve birim yönlendirmesi (karar
  DESTEK; nihai karar insandadır — düşük güvende insan onayı kapısı).
- **Kapsam dışı:** Otonom hukuki karar, gerçek kişisel veri işleme, e-imza/
  şifreleme, resmî tebligat üretimi.

## 3. Değerlendirme Verisi ve Metrikler
- **Veri:** 100 etiketli SENTETİK evrak (52 geliştirme + 16/16/16 tutulmuş) +
  15 belgelik kamuya açık mevzuat korpusu. Ayrıntı: `docs/veri_seti_datasheet.md`.
- **Metrikler:** sınıflandırma doğruluğu/F1, birim yönlendirme, eksik bilgi
  micro-F1, mevzuat isabet@k + MRR/nDCG, taslak kalitesi (bağımsız hakem),
  kalibrasyon (ECE), conformal kapsama, dayanıklılık invaryansı, KVKK sızıntı.
  Tüm metrikler **%95 güven aralığıyla** (Wilson + bootstrap) raporlanır.
- **Sonuçlar:** `data/processed/eval_report*.json` (yalnızca `scripts/evaluate.py`
  ile üretilir; her rapor bir **tekrarlanabilirlik mührü** taşır: git commit +
  platform + veri seti içerik hash'i).

## 4. Sınırlılıklar
- Sentetik veri ölçeği sınırlıdır (n=16 tutulmuş setlerde geniş güven aralıkları).
- OCR kural katmanı düz metin içindir; taranmış/eğik görüntüde ön-işleme gerekir.
- Mevzuat erişimi sözcükseldir (BM25); opsiyonel semantik katman varsayılan kapalı.
- Kural tabanlı bileşenler dağılım kaymasına duyarlıdır; düşük güven kapısı +
  insan onayı bu risk için tasarlanmıştır.

## 5. Etik ve Adalet
- **KVKK:** kişisel veriler maskelenir; sızıntı nicel ölçülür (0 kaçak hedefi).
- **Adalet:** kimlik değişiminin kararı değiştirmediği `tests/test_adillik.py`
  ile doğrulanır (yanlılık testi).
- **Şeffaflık:** her karar açıklanabilir gerekçe + güven skoru + (düşük güvende)
  insan onayı taşır. Ölçümler olduğu gibi raporlanır; başarısızlıklar gizlenmez.
