---
name: revert-surgical
description: Alakasız işi yok etmeden kötü bir değişikliği geri alın. Belirli bir commit veya değişiklik bir şeyi bozduğunda kullanın.
when_to_use: "bunu geri al", kötü bir dağıtım (deploy), tek commit prod'u bozdu, diğer işi kaybetmeden geri alma
---
# Cerrahi Geri Alma (Surgical Revert)
Tek bir kötü commit'i geri almak için üç iyi commit'i `git reset --hard` ile yok etme.
- **Tek commit** — `git revert <sha>` ters bir commit oluşturur; geçmiş bütün kalır ve paylaşılan dal için güvenlidir.
- **Bir commit'ten tek dosya** — `git checkout <good-sha> -- path/to/file`.
- **Hunk düzeyinde** — belirli değişiklikleri geri almak, gerisini korumak için `git checkout -p`.
- **Bir merge** — `git revert -m 1 <merge-sha>` (ana hat (mainline) ebeveynini seç).
Paylaşılan bir dalda her zaman geri al (ileriye doğru), asla geçmişi yeniden yazma. DOĞRU şeyi geri aldığından emin olmak için bozulmayı önce yeniden üret, sonra geri almanın gerçekten düzelttiğini doğrula.
