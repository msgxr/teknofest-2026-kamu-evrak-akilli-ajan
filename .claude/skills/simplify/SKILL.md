---
name: simplify
description: Bir değişikliği, sorunu çözen en küçük hale indir. Kod aşırı mühendislik ürünüyse ya da bir diff şişkinse kullan.
when_to_use: aşırı soyutlama, küçük bir istek için 200 satırlık diff, erken genellik
---
# Simplify
Aşırı mühendislik (over-engineering) varsayılan başarısızlık modudur. Kes at:
- **Erken soyutlama (premature abstraction)** — tek çağıran için bir class/strategy/factory. Satır içine al (inline). ÜÇÜNCÜ kullanımda soyutla, ilkinde değil.
- **Spekülatif config** — hiç değişmeyen bir şey için parametre/flag/env var. Gerçek bir sebep çıkana kadar sabit kodla (hardcode).
- **Ölü esneklik** — tek implementasyonu olan bir interface, tek tipi olan bir generic. Dolaylılığı sil.
- **Savunmacı gürültü** — null olamayacak değerlerde null kontrolleri, olamayacak hatalar için try/except. Yalnızca gerçek başarısızlık modlarını ele al.
Test: değişen her satırı, istenenle doğrudan bir bağ üzerinden gerekçelendirebilir misin? Bir satır "hazır oradayken" diye eklenmişse, geri al (revert).
