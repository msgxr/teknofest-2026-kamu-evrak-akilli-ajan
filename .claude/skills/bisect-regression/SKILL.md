---
name: bisect-regression
description: Bir hatayı ortaya çıkaran tam commit'i bulun. Daha önce çalışan bir şey bozulduğunda ve hangi değişikliğin buna yol açtığını bilmediğinizde kullanın.
when_to_use: "geçen hafta çalışıyordu", bir regresyon, hangi commit'in bozduğu belirsiz
---
# Regresyonu İkiye Böl (Bisect the Regression)
1. Bilinen bir iyi commit ve bilinen bir kötü commit bul. Her ikisini de gerçekten checkout edip test ederek doğrula.
2. `git bisect start; git bisect bad <bad>; git bisect good <good>`.
3. Her adımda, iyiyi kötüden ayıran EN KÜÇÜK testi çalıştır. `git bisect good/bad` ile işaretle.
4. git ilk kötü commit'i adlandırdığında, onun diff'ini oku. Hata o satırlardadır — başka yeri tahmin etme.
5. `git bisect reset`. Raporla: commit, satır, tek cümlelik neden.
Otomatikleştir: hata durumunda sıfır-olmayan çıkış veren bir betiğin varsa `git bisect run ./repro.sh`.
