---
name: authz-check
description: Bir endpoint'in yalnızca kimlik doğrulamayı (authentication) değil, sahipliği de kontrol ettiğini doğrula. Kullanıcı verisini okuyan veya değiştiren her handler üzerinde kullan.
when_to_use: yeni/değişmiş endpoint, "kullanıcı X'in verisini getir", bir mutation, bir admin eylemi
---
# Authz Check
En yaygın güvenlik açığı: kod giriş YAPTIĞINI kontrol eder, ama o şeyin SAHİBİ olduğunu kontrol etmez.
- Her kaynak erişimi için: mevcut kullanıcının BU belirli kayda izinli olduğunu doğruluyor mu? `WHERE id = ? AND owner_id = current_user` — yalnızca `WHERE id = ?` değil.
- IDOR testi: request'teki ID'yi başka bir kullanıcınınkiyle değiştir. Sızdırıyor/izin veriyor mu?
- Admin/ayrıcalıklı eylemler: rol her seferinde sunucu tarafında mı kontrol ediliyor, yoksa sadece UI'da mı gizli?
- Default deny: yeni endpoint'ler gözden kaçmayla açık kalmamalı, açık (explicit) yetkilendirme gerektirmeli.
Kimlik doğrulayan ama yetkilendirmeyen her handler'ı, eksik kontrolüyle birlikte çıktı ver.
