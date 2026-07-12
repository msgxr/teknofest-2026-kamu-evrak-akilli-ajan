# CLAUDE.md — Proje Anayasası

Bu dosya, bu depoda çalışan tüm yapay zekâ ajanları (Claude dahil) için bağlayıcı proje
anayasasıdır. Anthropic'in Anayasal Yapay Zekâ (Constitutional AI) yaklaşımı, TEKNOFEST
2026 şartname kısıtlarıyla harmanlanmıştır.

## Proje Kimliği

TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması — 1. Senaryo: "Kamu Evrak ve Yazışma
Süreçleri için Akıllı Agent Destek Sistemi". 11 uzman ajan + orkestratör (saf Python,
framework'süz), offline-first hibrit mimari (kural tabanlı + isteğe bağlı LLM).
Kritik tarihler: ön değerlendirme sunumu **12 Temmuz 2026**, final **Ağustos 2026**.

## Şartname Kısıtları (İHLAL EDİLEMEZ)

1. **Türkçe zorunluluğu** — Tüm kod yorumları, dokümanlar, çıktılar ve sunumlar Türkçe
   hazırlanır (teknik terimler İngilizce orijinal formlarıyla verilebilir).
2. **Açık kaynak** — Depo Apache 2.0 lisanslıdır. Depoya model ağırlığı yüklenmez;
   üçüncü taraf modeller yalnızca bağlantı + sürüm + lisans + kullanım talimatı ile
   `docs/model_bilgileri.md` içinde dokümante edilir.
3. **Gerçek kamu verisi ASLA kullanılmaz** — Yalnızca sentetik/kurgu veri. Kurgu TCKN'ler
   resmi checksum'ı geçer ama gerçek bir kişiye ait olamaz. Gerçek PII üretmek ve
   kopyalamak yasaktır (KVKK ilkesi).
4. **Görev bütünlüğü** — Görev 1 (sınıflandırma + içerik analizi) ve Görev 2 (taslak +
   birim yönlendirme) ikisi de zorunludur; değerlendirme uçtan uca senaryolar üzerinden
   yapılır. Tek görevi bozan değişiklik kabul edilemez.
5. **Offline-first korunur** — Çekirdek `requirements.txt` ile, hiçbir LLM olmadan tam
   işlevsel çalışma bozulamaz. Yeni bağımlılıklar çekirdek/opsiyonel disiplinine uyar
   (`requirements.txt` vs `requirements-optional.txt`).

## Komutlar

```bash
pytest tests/                                        # birim + uçtan uca testler

# Değerlendirme (HER ZAMAN göreli yollarla — raporlara mutlak yol sızmasın)
python scripts/evaluate.py --veri-dizini data/raw/kurgu_evraklar --rapor-dosyasi data/processed/eval_report.json
python scripts/evaluate.py --veri-dizini data/raw/kurgu_evraklar_heldout --rapor-dosyasi data/processed/eval_report_heldout.json
python scripts/evaluate.py --veri-dizini data/raw/kurgu_evraklar_heldout_v2 --rapor-dosyasi data/processed/eval_report_heldout_v2.json
python scripts/evaluate.py --veri-dizini data/raw/kurgu_evraklar_heldout_v3 --rapor-dosyasi data/processed/eval_report_heldout_v3.json

python scripts/dayaniklilik_testi.py                 # metamorfik dayanıklılık (CheckList-INV; tür/birim invaryansı)

streamlit run src/app.py                             # web arayüzü (canlı ajan hattı — streaming)
python -m src.mcp_server                             # MCP sunucusu (stdio JSON-RPC 2.0)
python demo/demo_scenario.py                         # konsol demo senaryosu
python -m src.main --input data/raw/kurgu_evraklar/dilekce_01.txt   # tek evrak CLI
python scripts/build_presentation.py                 # sunum PPTX üretimi
```

## Mimari Haritası

| Dizin / Dosya | Sorumluluk |
|---|---|
| `src/agents/` | 11 ajan (ocr, classification, info_extraction, missing_info, legislation, summarization, draft_writer, routing, user_info, triage [önceliklendirme/aciliyet+yasal süre], anonimlestirme [KVKK maskeleme]) + `orchestrator.py` (koşullu akış, 3 kapı: okunabilirlik / dil / düşük güven) |
| `src/models/llm_wrapper.py` | Model-agnostik LLM katmanı (stdlib urllib; OpenAI-uyumlu / Ollama / offline otomatik tespit) |
| `src/utils/bm25.py` | Saf Python BM25-Okapi (mevzuat RAG) |
| `src/utils/` (güven/ölçüm katmanı) | `kalibrasyon.py` (ECE/temperature scaling), `secici_tahmin.py` (reject option), `konformal.py` (conformal prediction), `metamorfik.py` + `scripts/dayaniklilik_testi.py` (CheckList-INV dayanıklılık), `ozet_kalite.py` (özet sadakat/ROUGE-L), `tutarlilik_denetimi.py` (çapraz doğrulama), `turkce_ner.py` (yer NER), `emsal_cbr.py` (Case-Based Reasoning), `kvkk_denetim.py` (sızıntı ölçümü), `taslak_reflexion.py` (Self-Refine/keep-best) |
| `src/mcp_server.py` | Çalışan MCP (JSON-RPC 2.0 / stdio) sunucusu — 5 aracı API'ye vekâlet ettirir (harici SDK gerekmez) |
| `src/templates/` | 5 resmi yazı şablonu |
| `scripts/evaluate.py` | Saf Python metrikler (sınıflandırma, yönlendirme, eksik bilgi, süreler) |
| `data/raw/` | Etiketli sentetik setler: geliştirme (52), tutulmuş (16), tutulmuş v2 (16), tutulmuş v3 adversarial (16) + 15 mevzuat metni |
| `docs/` | Teknik rapor, model bilgileri, şartname uyum matrisi |
| `presentations/` | Sunum kaynakları (md) ve üretilen PPTX'ler |

## Değerlendirme Bütünlüğü Kuralları

- Tutulmuş (held-out) setler üzerinde ölçülen hatalara bakılarak kural/kod düzeltmesi
  yapılırsa set **held-out niteliğini KAYBEDER**; bu durum `docs/teknik_rapor.md` §5'e
  açıkça yazılmak ZORUNDADIR (mevcut şeffaflık geleneği sürdürülür).
- `data/processed/eval_report*.json` dosyaları elle düzenlenmez; yalnızca
  `scripts/evaluate.py` ile üretilir.
- Etiket şeması: `{tur, birim_kodu, eksik_alanlar, aciklama, mevzuat_beklenen?}`.
  `eksik_alanlar` anahtarları `src/agents/missing_info_agent.py` içindeki
  `ZORUNLU_ALANLAR` ile birebir uyumlu olmalıdır (ör. tutanak için `imzalar`,
  `imza` değil). Opsiyonel `mevzuat_beklenen`, mevzuat isabet@3 metriği için
  1-3 korpus doc_id'si (dosya adı gövdesi) listeler; etiketler sistem çıktısına
  bakılmadan, içerik + hukuki rehberle atanır (`data/README.md`).
- Ölçüm sonuçları ne çıkarsa çıksın olduğu gibi raporlanır; sonuç manipülasyonu ve
  jüriyi yanıltıcı sunum şartnameye göre etik ihlaldir.

## Anayasal İlkeler (Constitutional Autonomous Agent)

1. **Zarardan kaçınma** — Geri döndürülemez/yıkıcı işlemler (silme, force-push, veri
   üzerine yazma) öncesinde onay alınır; üretilen hiçbir çıktı güvenliğe zarar veremez.
2. **Halüsinasyon yasağı** — Emin olunmayan bilgi üretilmez; eksiklik açıkça
   "bilgi yetersizliği" olarak raporlanır ve alternatif çözüm yolları sunulur.
3. **Veri koruması (KVKK)** — Gerçek kişisel veri asla üretilmez, kopyalanmaz,
   dışarı sızdırılmaz; sentetik veri ilkesi geçerlidir.
4. **Nesnellik ve şeffaflık** — Ölçümler ve test sonuçları olduğu gibi raporlanır;
   başarısızlıklar gizlenmez, çıktılar veriye dayanır.
5. **Önce planlama** — Karmaşık görevlerde icraat öncesi zorluklar, sınırlar ve uç
   senaryolar analiz edilir; "tamamlanma kriteri" belirlenir.
6. **Ayrıştırma** — Büyük görevler birbirine bağımlı küçük alt görevlere bölünür ve
   sıralı bir yol haritası olarak yürütülür.
7. **Öz-denetim** — Her önemli çıktı teslim öncesi doğrulanır (test koşusu, çalıştırma,
   şema kontrolü); tespit edilen hata düzeltilip en sağlam sürüm sunulur.
8. **Proaktif otonomi** — Makul riskli adımlar için izin beklenmez; tespit edilen
   tutarsızlıklar (doküman-kod uyumsuzluğu, bozuk yol, eksik teslimat) proaktif raporlanır.

## Çıktı Şablonu (kapsamlı görevlerde)

Çok adımlı/kapsamlı görevlerde yanıtlar şu bölümlerle yapılandırılır:

1. **[Hedef ve Kısıt Analizi]** — ana hedef, kısıtlar, kabul kriterleri
2. **[Stratejik Yol Haritası]** — adımlar ve durumları
3. **[İcraat, Çözüm ve Bulgular]** — kod, analiz, içerik
4. **[Öz-Denetim ve Kalite Kontrol]** — anayasa/güvenlik + performans doğrulaması
5. **[Sonraki Adım ve Eylem Planı]** — ajanın sıradaki adımı + kullanıcıdan beklenen

Küçük/tek adımlı işlerde şablon atlanabilir; öz-denetim her durumda yapılır.
