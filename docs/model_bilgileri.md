# Üçüncü Taraf Model Bilgileri

Bu projede kullanılan/kullanılabilen üçüncü taraf modellerin erişim bağlantıları, sürüm bilgileri ve lisans detayları aşağıda belirtilmiştir.

> **Not 1:** Şartname gereği, açık ağırlık (open-weight) veya kısıtlı lisanslı modeller doğrudan depoya yüklenmemiştir. Aşağıda sadece erişim bilgileri ve kullanım talimatları yer almaktadır.
>
> **Not 2 (offline-first tasarım):** Sistemin çekirdeği **tamamen kural tabanlıdır ve hiçbir LLM olmadan uçtan uca çalışır**. LLM'ler yalnızca **opsiyonel** iyileştirme katmanıdır (düşük güvenli sınıflandırmada eskalasyon, yakın skorlu yönlendirmede ayrıştırma, taslak zenginleştirme). LLM erişimi yoksa tüm ajanlar kural tabanlı yollarla tam işlevli kalır (`src/models/llm_wrapper.py` → `offline` backend).

## LLM Modelleri (opsiyonel)

LLM çağrıları harici SDK olmadan, Python standart kütüphanesi (`urllib`) ile yapılır. İki backend desteklenir ve otomatik tespit edilir:

### 1. OpenAI-uyumlu API — varsayılan model: gpt-4o-mini
- **Erişim:** https://platform.openai.com/docs/models/gpt-4o-mini (veya OpenRouter, Groq, Together, vLLM, LM Studio gibi herhangi bir OpenAI-uyumlu uç nokta)
- **Kullanım:** `OPENAI_API_KEY` (ve gerekirse `LLM_BASE_URL`) tanımlandığında etkinleşir
- **Lisans:** Sağlayıcının hizmet koşullarına tabidir (model depoya dahil edilmez, yalnızca API üzerinden çağrılır)
- **Rolü:** Düşük güvenli sınıflandırmada eskalasyon, yönlendirme ayrıştırması, taslak iyileştirme

### 2. Ollama (yerel) — varsayılan model: Qwen2.5 7B Instruct
- **Erişim:** https://ollama.com/library/qwen2.5 — https://huggingface.co/Qwen/Qwen2.5-7B-Instruct
- **Sürüm:** Qwen2.5, 7B Instruct (`qwen2.5:7b`)
- **Lisans:** Apache 2.0
- **Kullanım:** Yerel Ollama sunucusu (http://localhost:11434) çalışıyorsa otomatik tespit edilir; internet bağlantısı gerektirmez
- **İndirme:** `ollama pull qwen2.5:7b`

### Alternatif LLM'ler (aynı arayüz üzerinden kullanılabilir)

Sistem model-bağımsızdır; OpenAI-uyumlu veya Ollama arayüzü sunan her model `LLM_MODEL_NAME` / `LLM_OLLAMA_MODEL` ayarlarıyla takılabilir. Denenebilecek açık ağırlıklı alternatifler:

| Model | Erişim | Lisans |
|-------|--------|--------|
| Meta Llama 3.1 8B Instruct | https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct | Llama 3.1 Community License |
| Mistral 7B Instruct v0.3 | https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3 | Apache 2.0 |

### Bütünlük ve güvenli model yükleme (tedarik zinciri güvenliği)

Üçüncü taraf model ağırlıkları **yalnızca doğrulanmış resmî kaynaktan** indirilmelidir.
Güvenli yükleme ilkeleri:

- **safetensors tercih edin.** Mümkün olduğunda `.safetensors` biçimini kullanın;
  `.bin`/`.pt` (pickle) ağırlıklar yüklenirken rastgele kod çalıştırabilir (CWE-502).
  `transformers` ile: `from_pretrained(..., use_safetensors=True)`.
- **Sürümü sabitleyin.** HuggingFace deposundan çekerken belirli bir revizyon/commit
  kullanın (`from_pretrained(..., revision="<commit_sha>")`); böylece deponun
  ileride değişmesi kurulumu sessizce etkilemez.
- **Bütünlüğü doğrulayın.** İndirilen ağırlığın yayınlanan `sha256` özetini
  kontrol edin. Ollama imajları çekilirken (`ollama pull`) sürüm etiketini sabit tutun.
- Bu ilkeler **yalnızca opsiyonel** yerel model yolu için geçerlidir; kural tabanlı
  çekirdek hiçbir model ağırlığı indirmez.

> **Not (ChromaDB gömme modeli):** ChromaDB araması hibritleşmeyle birlikte
> YEDEK yoldur: yalnızca BM25 indeksi kurulamadığında (`chromadb` kuruluysa)
> denenir. Bu yolda `LegislationAgent` koleksiyona açık bir embedding fonksiyonu
> geçirmez; ChromaDB **kendi varsayılan gömme modelini** ilk kullanımda ağdan
> indirir — üçüncü taraf model olarak şartname m.7 gereği belgelenmiştir:
>   - **Model:** `all-MiniLM-L6-v2` (ChromaDB varsayılanı, ONNX quantize)
>   - **Erişim:** https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2
>   - **Sürüm:** ChromaDB `ONNXMiniLM_L6_V2` gömülü varsayılanı (`chromadb>=0.5.0`)
>   - **Lisans:** Apache 2.0 (model kartı `license` alanından doğrulandı)
>
> Yukarıda belgelenen
> `paraphrase-multilingual-MiniLM-L12-v2` yalnızca `EMBEDDING_MODEL_NAME` ile açık
> bir embedding fonksiyonu tanımlanırsa kullanılır. Her iki modelin de indirilmesi
> başarısız olursa sistem BM25'e düşer ve tam işlevli kalır.

## Bilgi Getirimi (Hibrit Mevzuat RAG)

Mevzuat önerici, **hibrit** bir geri getirme hattı kullanır: çekirdek BM25
her zaman çalışır; aşağıdaki opsiyonel katmanlar kuruluysa VE ortam
değişkeniyle açıkça etkinleştirilmişse BM25 sonuçlarıyla puan birleşimine
girer. Opsiyonel katmanlar bilinçli olarak **varsayılan kapalıdır**: ilk
kullanımda model indirme gerektirdiklerinden kapalı ağda sürpriz ağ
trafiği oluşturmazlar (offline-first ilkesi).

### BM25-Okapi (model değildir — saf Python)
- **Konum:** `src/utils/bm25.py` (takım tarafından yazılmıştır, harici bağımlılık yok)
- **Kullanım:** Mevzuat korpusunda birincil arama yöntemi; her ortamda, tamamen çevrimdışı çalışır

### Semantik arama modeli (opsiyonel) — turkish-e5-large
- **Erişim:** https://huggingface.co/ytu-ce-cosmos/turkish-e5-large
- **Sürüm:** commit `02e2362` (son güncelleme 2025-12-01; ~560M parametre)
- **Lisans:** MIT (model kartı `license` alanından doğrulandı)
- **Taban model:** `intfloat/multilingual-e5-large-instruct` (instruct varyantı)
- **Kullanım:** `pip install -r requirements-optional.txt` sonrası
  `EMBEDDING_SEMANTIK_AKTIF=1` ile etkinleşir (`src/utils/semantik_arama.py`).
  Model kartına uygun olarak sorgular `Instruct: {görev}\nQuery: {sorgu}`
  biçiminde, pasajlar öneksiz ve `normalize_embeddings=True` ile kodlanır.
  Model erişilemezse sistem uyarı verip BM25 ile tam işlevli kalır.

### Yeniden sıralama modeli (opsiyonel) — bge-reranker-v2-m3
- **Erişim:** https://huggingface.co/BAAI/bge-reranker-v2-m3
- **Sürüm:** commit `953dc6f` (2024-06-24; ~568M parametre, XLM-R tabanlı çapraz kodlayıcı)
- **Lisans:** Apache 2.0 (model kartı `license` alanından doğrulandı)
- **Kullanım:** `EMBEDDING_RERANK_AKTIF=1` ile etkinleşir;
  `sentence_transformers.CrossEncoder("BAAI/bge-reranker-v2-m3")` deseniyle
  yüklenir (sbert.net resmî model listesinden doğrulanmıştır), logit çıktısı
  sigmoid ile [0-1] aralığına taşınır. Erişilemezse bu adım sessizce atlanır.

### Embedding modeli (eski/alternatif; yalnızca opsiyonel `chromadb` yolunda)
- **Model:** paraphrase-multilingual-MiniLM-L12-v2
- **Erişim:** https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- **Sürüm:** v2
- **Lisans:** Apache 2.0
- **Kullanım:** ChromaDB yedek yolunda kullanılabilecek gömme modeli.
  Hibritleşmeyle birlikte ChromaDB araması artık birincil yolu ÖNCELEMEZ;
  yalnızca BM25 indeksi kurulamadığında yedek yol olarak denenir.

## OCR (yalnızca taranmış PDF / görüntü girdiler için, opsiyonel)

### Tesseract OCR
- **Erişim:** https://github.com/tesseract-ocr/tesseract
- **Sürüm:** 5.x
- **Lisans:** Apache 2.0
- **Kullanım:** Görüntülerden Türkçe metin çıkarımı (`pytesseract` üzerinden)
- **Kurulum:** `apt install tesseract-ocr tesseract-ocr-tur` (Linux) veya `brew install tesseract tesseract-lang` (macOS)
- **Not:** Metin dosyaları ve metin katmanlı PDF'ler için OCR gerekmez (`pypdf` ile okunur)

### EasyOCR
- **Erişim:** https://github.com/JaidedAI/EasyOCR
- **Sürüm:** >=1.7.0 (`requirements-optional.txt` ile uyumlu)
- **Lisans:** Apache 2.0
- **Kullanım:** Görüntü/taranmış PDF için Tesseract'a alternatif OCR motoru; `OCRAgent(engine="easyocr")` ile etkinleşir (`easyocr.Reader(['tr'], gpu=False)`).
- **Kurulum:** `pip install easyocr` (yalnızca opsiyonel; çekirdek işlev gerektirmez)
- **Not:** `easyocr.Reader` İLK çağrıda CRAFT metin-tespit + Türkçe tanıma ağırlıklarını `~/.EasyOCR` altına ağdan indirir → çevrimdışı ilk kullanımda tek seferlik ağ trafiği. Kurulu değilse sistem `RuntimeError` ile zarifçe düşer; varsayılan motor Tesseract / `pypdf` ile tam işlevsel kalır (offline-first korunur). Ağırlık deposu depoya YÜKLENMEZ.

## Yerli LLM Karşılaştırma Protokolü (P2-10)

Opsiyonel eskalasyon katmanı için model seçimi, `scripts/llm_karsilastirma.py`
protokolüyle yapılır (LLM-only tür doğruluğu + JSON uyumu + gecikme; aynı
tutulmuş set). **Henüz koşulmamıştır; koşulmadan hiçbir karşılaştırma sayısı
rapora/sunuma yazılamaz.** GPU'lu ekip makinesinde kurulum ve koşum komutları
betiğin docstring'indedir. Adaylar (tümü opsiyonel; ağırlık depoya YÜKLENMEZ,
yalnızca yerel eskalasyon için indirilir):
- `qwen2.5:7b` — mevcut varsayılan; Erişim: https://ollama.com/library/qwen2.5 ; etiket `7b`; Lisans: Apache-2.0.
- `ytu-ce-cosmos/Turkish-Llama-8b-Instruct-v0.1-GGUF` — Erişim: https://huggingface.co/ytu-ce-cosmos/Turkish-Llama-8b-Instruct-v0.1-GGUF ; etiket `Q4_K_M`; Lisans: Llama 3 Community (OSI-onaylı DEĞİL; yalnızca opsiyonel yerel eskalasyon adayı).
- `ytu-ce-cosmos/Turkish-Gemma-9b-T1-GGUF` — Erişim: https://huggingface.co/ytu-ce-cosmos/Turkish-Gemma-9b-T1-GGUF ; etiket `Q4_K_M`; Lisans: Gemma (OSI-onaylı DEĞİL; opsiyonel).
