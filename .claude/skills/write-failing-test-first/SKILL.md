---
name: write-failing-test-first
description: Herhangi bir hatayı düzeltmeden önce, onu yeniden üreten bir test yazın ve başarısız olmasını izleyin. Her hata düzeltmesi için kullanın.
when_to_use: bir hatayı düzeltme, "X'i çalıştır", raporlanmış bir kusur (defect)
---
# Önce Başarısız Testi Yaz (Write the Failing Test First)
Bir hatayı düzelttiğinin tek kanıtı, önce başarısız olan sonra geçen bir testtir.
1. Raporlanan davranışı yeniden üreten en küçük testi yaz.
2. Çalıştır. **Başarısız olmasını izle** ve doğru nedenden dolayı olduğunu gör (sadece kırmızıya değil, doğrulamaya (assertion) bak).
3. Şimdi kodu düzelt.
4. Testi çalıştır. Geçiyor. TÜM paketi (suite) çalıştır — başka bir şeyi bozmadın.
Testi kolayca yazamıyorsan, mimari sana bir şey söylüyordur (sıkı bağlılık — tight coupling). Bunu belirt.
Asla: önce düzeltip sonra test yazma (nasıl olsa geçen bir test yazarsın). Asla: başarısız-olmasını-izle adımını atlama.
