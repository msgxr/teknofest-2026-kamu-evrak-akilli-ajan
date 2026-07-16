---
name: coverage-gaps
description: Yalnızca kapsam yüzdesini değil, gerçekten önemli olan test edilmemiş kod yollarını bulun. Test ekledikten sonra kullanın.
when_to_use: "kapsamı iyileştir", test yazdıktan sonra, birleştirme-öncesi (pre-merge) kalite kontrolü
---
# Kapsam Boşlukları (Coverage Gaps)
Kapsam yüzdesi bir gösteriş metriğidir. Isıran boşlukları avla:
- **Hata yolları** — 500, timeout, boş/null girdi, bozuk yük (payload). Neredeyse her zaman test edilmemiştir.
- **Sınırlar** — 0, 1, maksimum, bir-eksik (off-by-one), boş koleksiyon.
- **Dallar** — sadece mutlu satır değil, her `if/else` ve `catch` çalıştırılmış olmalı.
- **Eşzamanlılık / sıra** — durum tutan (stateful) her şey hem izole HEM DE sırayla test edilmiş olmalı.
Bir yapıcının (constructor) bir özelliği ayarladığını doğrulayan testleri atla — değersiz. Uygulamayı değil davranışı test et. Çıktı: patlama yarıçapına (blast radius) göre sıralanmış, eklenecek testiyle birlikte en yüksek riskli 3-5 test edilmemiş yol.
