---
name: contract-test
description: İki sistem arasındaki sınırı uygulamaya göre değil sözleşmeye (contract) göre test edin. API'ler, entegrasyonlar ve paylaşılan arayüzler için kullanın.
when_to_use: bir API uç noktası (endpoint), bir servis entegrasyonu, bir webhook, paylaşılan bir şema
---
# Sözleşme Testi (Contract Test)
İki tarafın ÜZERİNDE ANLAŞTIĞI şeyi test et, böylece iki taraf da diğerini bozmadan iç yapısını değiştirebilsin.
- **Biçimi (shape)** doğrula: zorunlu alanlar, tipler, durum kodları, hata biçimi — iç mantığı değil.
- Sözleşmenin kenar durumlarını kapsa: eksik opsiyonel alanlar, dokümante edilmiş hata yanıtları, sayfalama sınırları (pagination bounds), sürümleme (versioning).
- Tüketiciler (consumers) için: kendi varsayımlarına uydurmak için yazdığın bir mock'a değil, gerçek sözleşmeye (kaydedilmiş/gerçek yanıtlar) karşı test et — o mock kayar (drift) ve yalan söyler.
- Şema için tek bir doğruluk kaynağı (source of truth); iki taraf da ona karşı doğrulama yapar.
Yanlış mock'lu yeşil bir birim testi, hiç test olmamasından beterdir. Sözleşmeyi sabitle (pin).
