# Şartname Uyum Matrisi

TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması (1. Senaryo) Teknik Şartnamesi'ndeki
her gereksinimin projede nasıl karşılandığını gösteren kanıt haritasıdır.
Şartname madde numaraları parantez içinde verilmiştir.

## Görev 1 — Evrak Sınıflandırma ve İçerik Analizi (m. 6.4.1)

| Şartname gereksinimi | Kanıt (dosya) | Durum |
|---|---|---|
| Evrakı OCR veya doğrudan metin olarak okuyabilme | `src/agents/ocr_agent.py` (TXT/MD doğrudan; PDF PyPDF2; görüntü/taranmış PDF için opsiyonel Tesseract/EasyOCR) | ✅ |
| Metni anlamlandırarak evrak türünü belirleme | `src/agents/classification_agent.py` (9 tür; anahtar kelime + 20+ yapısal sinyal + softmax güven; LLM eskalasyonu) | ✅ |
| İçerikte geçen önemli bilgi unsurlarını çıkarma | `src/agents/info_extraction_agent.py` (tarih, sayı, checksum doğrulamalı T.C. kimlik, İlgi, konu, muhatap, kurum, kişi, IBAN, iletişim) | ✅ |
| Eksik olan bilgileri tespit edebilme | `src/agents/missing_info_agent.py` (türe özgü `ZORUNLU_ALANLAR` + öncelik + giderme önerisi) | ✅ |
| İlgili mevzuat / yazışma kurallarını önerebilme | `src/agents/legislation_agent.py` + `src/utils/bm25.py` (15 belgelik korpus üzerinde BM25 RAG + türe koşullu yeniden sıralama) | ✅ |
| Kısa ve öz özet oluşturabilme | `src/agents/summarization_agent.py` (skorlamalı extractive özet; LLM varsa üretken özet) | ✅ |

## Görev 2 — Resmî Yazı Taslaklama ve Birim Yönlendirme (m. 6.4.2)

| Şartname gereksinimi | Kanıt (dosya) | Durum |
|---|---|---|
| Üst yazı / cevap yazısı / bilgilendirme veya alternatif tür için taslak | `src/agents/draft_writer_agent.py` + `src/templates/` (üst yazı, cevap, bilgilendirme, eksik bilgi talep, iade/ikmal notu) | ✅ |
| Taslağın resmî üsluba uygunluğu | `src/agents/draft_writer_agent.py` — 9 kurallı Yönetmelik kontrol listesi + format skoru; hitap-kapanış uyumu | ✅ |
| İçeriğe göre doğru birime yönlendirme önerisi | `src/agents/routing_agent.py` (9 birimlik şema, gerekçeli ve alternatifli öneri) | ✅ |
| Kullanıcıya açık ve anlaşılır süreç bilgilendirmesi | `src/agents/user_info_agent.py` (durum, uyarılar, sonraki adımlar) | ✅ |
| Gerekli durumlarda eksik bilgi talep edebilme | `src/agents/user_info_agent.py` (soru üretimi) + `src/templates/eksik_bilgi_talep.txt` (otomatik resmî talep yazısı) | ✅ |

## Sistem Bütünlüğü ve Yöntem (m. 6.3, 6.6, 9)

| Şartname gereksinimi | Kanıt (dosya) | Durum |
|---|---|---|
| Uçtan uca evrak işleme ve yazışma hazırlama akışı | `src/agents/orchestrator.py` + `src/pipelines/end_to_end_pipeline.py` (iki görev tek akışta; 3 koşullu kapı) | ✅ |
| Çok ajanlı mimari / agent orkestrasyonu | `src/agents/` — 9 uzman ajan + orkestratör, paylaşılan `AgentState` | ✅ |
| Model eğitimi zorunlu değil; hazır/açık kaynak model kullanımı | `src/models/llm_wrapper.py` (OpenAI-uyumlu / Ollama / offline otomatik tespit; eğitim yok) | ✅ |
| Performans ölçümü (sınıflandırma, yönlendirme, özet, eksik bilgi) | `scripts/evaluate.py` + `data/processed/eval_report*.json` (3 set: geliştirme, tutulmuş, tutulmuş v2) | ✅ |
| Gerçek zamana yakın sonuç üretimi | `docs/teknik_rapor.md` §5 — evrak başına medyan ~0,02 sn; arayüzde adım adım süre tablosu | ✅ |

## Veri Kullanımı (m. 6.5)

| Şartname gereksinimi | Kanıt (dosya) | Durum |
|---|---|---|
| Gerçek kamu verisi kullanılmaması | `data/README.md` (tamamı sentetik; kurgu TCKN'ler yalnızca checksum geçer) | ✅ |
| Kurgu evrak örnekleri ve yapay resmî yazışma taslakları | `data/raw/kurgu_evraklar/` (35), `data/raw/kurgu_evraklar_heldout/` (16), `data/raw/kurgu_evraklar_heldout_v2/` (16) — tümü etiketli | ✅ |
| Kamuya açık mevzuat metinleri | `data/raw/mevzuat_metinleri/` (15 belge; kaynak: mevzuat.gov.tr) | ✅ |
| Veri seti çeşitliliği | 8 evrak türü × 3 farklı kurgu kurum evreni ve üslup dokusu | ✅ |
| Demo verisinin kaynağı ve kullanım haklarının beyanı | `data/README.md` (kaynak + Apache 2.0), `src/app.py` "Hakkında" sekmesi | ✅ |

## Dokümantasyon, Lisans ve Teslim (m. 7)

| Şartname gereksinimi | Kanıt (dosya) | Durum |
|---|---|---|
| Tüm belgelerin Türkçe hazırlanması | `README.md`, `docs/teknik_rapor.md`, `data/README.md`, kod yorumları | ✅ |
| Bilimsel atıf kurallarına uygun kaynak gösterimi | `docs/teknik_rapor.md` §7 Kaynakça | ✅ |
| Açık kaynak lisansla paylaşım (Apache/MIT/GNU) | `LICENSE` (Apache 2.0) | ✅ |
| Uygun lisanslı olmayan model ağırlıklarının depoya yüklenmemesi; bağlantı+sürüm+lisans+talimat dokümantasyonu | `docs/model_bilgileri.md` | ✅ |
| Teknik rapor teslimi | `docs/teknik_rapor.md` | ✅ |

## Sunum ve Demo (m. 8)

| Şartname gereksinimi | Kanıt (dosya) | Durum |
|---|---|---|
| Ön değerlendirme sunumu (proje, mimari, takım, motivasyon) | `presentations/on_degerlendirme_sunumu.md` + `.pptx` (üretim: `scripts/build_presentation.py`) | ✅ (takım bilgisi alanları doldurulacak) |
| Sunum PDF ve PPTX formatında | PPTX script ile üretilir; PDF PowerPoint'ten dışa aktarılır (`presentations/README.md`) | ⚠️ PDF elle alınacak |
| Uçtan uca çalışan demo | `demo/demo_scenario.py` (konsol) + `src/app.py` (Streamlit) | ✅ |
| Türkçe metinler üzerinde gözlemlenebilir çıktılar | Demo, sentetik Türkçe evrak setleri üzerinde çalışır | ✅ |
| İnternet kesintisine karşı yedek plan | Offline-first mimari — LLM'siz tam işlev (`demo/README.md`, `docs/teknik_rapor.md` §1) | ✅ |

## Etik ve Değerlendirme Bütünlüğü (m. 13)

| Şartname gereksinimi | Kanıt (dosya) | Durum |
|---|---|---|
| Veri sahteciliği / sonuç manipülasyonu yasağı | `docs/teknik_rapor.md` §5 metodolojik notlar (şeffaf held-out geçmişi; v2 tek sefer ölçüm) + `CLAUDE.md` değerlendirme bütünlüğü kuralları | ✅ |
| KVKK / kişisel verilerin korunması | Gerçek PII yok; sentetik veri ilkesi (`data/README.md`, `CLAUDE.md`) | ✅ |
| İntihal yasağı / özgünlük | Framework bağımsız özgün orkestrasyon; üçüncü taraf bileşen lisansları belgelendi | ✅ |
