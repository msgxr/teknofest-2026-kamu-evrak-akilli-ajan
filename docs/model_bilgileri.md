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

> **Not (ChromaDB gömme modeli):** Opsiyonel semantik arama etkinleştirilirse
> (`chromadb` kurulu), `LegislationAgent` koleksiyona açık bir embedding fonksiyonu
> geçirmez; bu durumda ChromaDB **kendi varsayılan modelini** (`all-MiniLM-L6-v2`,
> ONNX) ilk kullanımda ağdan indirir. Yukarıda belgelenen
> `paraphrase-multilingual-MiniLM-L12-v2` yalnızca `EMBEDDING_MODEL_NAME` ile açık
> bir embedding fonksiyonu tanımlanırsa kullanılır. Her iki modelin de indirilmesi
> başarısız olursa sistem BM25'e düşer ve tam işlevli kalır.

## Bilgi Getirimi (Mevzuat RAG)

### BM25-Okapi (model değildir — saf Python)
- **Konum:** `src/utils/bm25.py` (takım tarafından yazılmıştır, harici bağımlılık yok)
- **Kullanım:** Mevzuat korpusunda birincil arama yöntemi; her ortamda, tamamen çevrimdışı çalışır

### Embedding modeli (yalnızca opsiyonel `chromadb` kuruluysa)
- **Model:** paraphrase-multilingual-MiniLM-L12-v2
- **Erişim:** https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- **Sürüm:** v2
- **Lisans:** Apache 2.0
- **Kullanım:** BM25'e ek vektör tabanlı semantik arama; yalnızca `pip install -r requirements-optional.txt` ile `chromadb` + `sentence-transformers` kurulursa devreye girer. Kurulu değilse sistem BM25 ile tam işlevli çalışır.

## OCR (yalnızca taranmış PDF / görüntü girdiler için, opsiyonel)

### Tesseract OCR
- **Erişim:** https://github.com/tesseract-ocr/tesseract
- **Sürüm:** 5.x
- **Lisans:** Apache 2.0
- **Kullanım:** Görüntülerden Türkçe metin çıkarımı (`pytesseract` üzerinden)
- **Kurulum:** `apt install tesseract-ocr tesseract-ocr-tur` (Linux) veya `brew install tesseract tesseract-lang` (macOS)
- **Not:** Metin dosyaları ve metin katmanlı PDF'ler için OCR gerekmez (`pypdf` ile okunur)
