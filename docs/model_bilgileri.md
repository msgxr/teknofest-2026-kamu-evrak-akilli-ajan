# Üçüncü Taraf Model Bilgileri

Bu projede kullanılan üçüncü taraf modellerin erişim bağlantıları, sürüm bilgileri ve lisans detayları aşağıda belirtilmiştir.

> **Not:** Şartname gereği, açık ağırlık (open-weight) veya kısıtlı lisanslı modeller doğrudan depoya yüklenmemiştir. Aşağıda sadece erişim bilgileri ve kullanım talimatları yer almaktadır.

## LLM Modelleri

### Meta Llama 3.1 8B Instruct
- **Erişim:** https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct
- **Sürüm:** Llama 3.1
- **Lisans:** Llama 3.1 Community License Agreement
- **Kullanım:** Evrak sınıflandırma, özet oluşturma, yazı taslağı üretme
- **İndirme:** `huggingface-cli download meta-llama/Llama-3.1-8B-Instruct`

### Mistral 7B Instruct v0.3 (Alternatif)
- **Erişim:** https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3
- **Sürüm:** v0.3
- **Lisans:** Apache 2.0
- **Kullanım:** Genel amaçlı metin üretimi

## Embedding Modelleri

### paraphrase-multilingual-MiniLM-L12-v2
- **Erişim:** https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- **Sürüm:** v2
- **Lisans:** Apache 2.0
- **Kullanım:** Mevzuat vektör veritabanı için metin gömme (embedding)

## OCR Modelleri

### Tesseract OCR
- **Erişim:** https://github.com/tesseract-ocr/tesseract
- **Sürüm:** 5.x
- **Lisans:** Apache 2.0
- **Kullanım:** Görüntülerden Türkçe metin çıkarımı
- **Kurulum:** `apt install tesseract-ocr tesseract-ocr-tur` (Linux) veya Windows installer

## Türkçe NLP

### BERTurk
- **Erişim:** https://huggingface.co/dbmdz/bert-base-turkish-cased
- **Sürüm:** Base (cased)
- **Lisans:** MIT
- **Kullanım:** Türkçe NER ve metin sınıflandırma (isteğe bağlı)
