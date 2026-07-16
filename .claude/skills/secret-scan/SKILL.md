---
name: secret-scan
description: Hardcode edilmiş secret'ları, key'leri ve token'ları commit'lenmeden önce yakala. Her commit'ten önce ve credential içeren her dosyada kullan.
when_to_use: commit'ten önce, API key'leri olan dosyalar, .env işleme, config, connection string'leri
---
# Secret Scan
Diff'i şunlar için grep'le: `api[_-]?key`, `secret`, `token`, `password`, `BEGIN PRIVATE KEY`, `AKIA[0-9A-Z]{16}`, `sk-`, `ghp_`, bearer değerleri ve uzun base64/hex blob'ları.
Her eşleşme için: gerçek bir secret mı yoksa bir placeholder mı? Gerçek secret'lar:
1. Env'e / bir secrets manager'a taşınmalı — asla repo'ya değil.
2. Zaten commit'lenmişse, COMPROMISED (ele geçmiş) sayılır. Onu rotate et, sadece satırı silme.
3. Pattern'i `.gitignore`'a / bir pre-commit secret scanner'a ekle.
Çıktı: her gerçek secret'ın file:line'ı + rotation adımı. Git geçmişinde silinmiş bir secret hâlâ sızmıştır.
