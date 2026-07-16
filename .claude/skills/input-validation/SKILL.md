---
name: input-validation
description: Güvenilmeyen girdiyi sınırda (boundary) doğrula ve kısıtla. Harici veri kabul eden her handler üzerinde kullan.
when_to_use: request body'leri, query param'ları, dosya yüklemeleri, webhook payload'ları, form verisi
---
# Input Validation
Sınırda, veri mantığa veya depolamaya dokunmadan önce doğrula.
- **Schema** — tip, zorunlu alanlar, izin verilen değerler. Bilinmeyen alanları görmezden gelmek yerine reddet.
- **Bounds** — string uzunluğu, sayı aralıkları, dizi boyutu. Sınırsız bir girdi bir DoS ve bir bellek bombasıdır.
- **Format** — e-postalar, UUID'ler, tarihler parse edilip yeniden doğrulanmalı, string olarak güvenilmemeli.
- **Files** — boyut limiti, tür allowlist'i (yalnızca uzantı değil, içeriği kontrol et), isimlerde path traversal olmamalı.
- Net bir 4xx ile ve neyin yanlış olduğunu söyleyen — iç detayları sızdırmayan — bir mesajla reddet.
"Bizim kendi frontend'imizden geliyor"a asla güvenme. Request her yerden gelebilir.
