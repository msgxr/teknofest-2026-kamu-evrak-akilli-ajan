---
name: migration-writer
description: Bu deponun geleneklerine uygun, güvenli ve geri döndürülebilir veritabanı migration'ları yaz. Herhangi bir şema değişikliği için kullan.
when_to_use: bir tablo, kolon, index veya kısıt (constraint) ekle/değiştir
---
# Migration Writer
1. Önce mevcut şemayı oku. Deponun migration aracını ve adlandırmasını (`NNN_<verb>_<noun>`) izle.
2. HEM up HEM down yaz. Geri alamadığın bir migration, güvenle deploy edemeyeceğin bir migration'dır.
3. **Canlıda güvenli (live-safe)**: yoğun bir tabloda, varsayılansız (default) bir NOT NULL kolon eklemek ya da CONCURRENTLY olmadan bir index eklemek bloklayan bir lock alır. Adımlara böl: nullable ekle → geri doldur (backfill) → kısıt ekle.
4. Büyük tabloları tek bir ifadeyle değil, gruplar (batch) hâlinde geri doldur.
5. Zaten merge edilmiş bir migration'ı asla düzenleme — yenisini ekle.
Commit'lemeden önce dry-run ile test et. Çıktı: migration + tam deploy sırası.
