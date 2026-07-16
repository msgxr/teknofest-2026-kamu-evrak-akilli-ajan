---
name: readme-audit
description: Bir README'nin bir yabancının projeyi gerçekten çalıştırmasına izin verip vermediğini kontrol et. Yayınlamadan önce herhangi bir deponun README'sinde kullan.
when_to_use: bir depo yayınlama, onboarding dokümanları, "README iyi mi"
---
# README Audit
Bir README'nin tek görevi: bir yabancı onu klonlar ve sana sormadan "çalışıyor"a ulaşır.
Sırayla kontrol et:
1. **Tek cümle** — ne olduğu ve kimin için olduğu — kıvrımın üstünde (above the fold).
2. **Install** — temiz bir makinede gerçekten çalışan kopyala-yapıştır komutlar. Zihninde adım adım test et.
3. **Run / quickstart** — en küçük uçtan uca örnek.
4. **Config** — gerekli env var'lar, secret'ların nereye gittiği.
5. **Çürüme yok (no rot)** — hâlâ var olan dosyalara/komutlara/flag'lere mi referans veriyor? Bayat bir README, hiç olmamasından daha kötüdür.
Kes at: uzun felsefe, kimsenin okumadığı rozetler (badge), TODO bölümleri. Çıktı: spesifik boşluklar + düzeltme.
