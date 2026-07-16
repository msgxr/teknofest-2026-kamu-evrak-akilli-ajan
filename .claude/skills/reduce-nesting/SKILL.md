---
name: reduce-nesting
description: Derinlemesine iç içe geçmiş koşulları okunabilir, erken-dönüşlü (early-return) koda düzleştir. 3+ girinti seviyesi olan herhangi bir fonksiyonda kullan.
when_to_use: ok-şeklinde (arrow-shaped) kod, 3+ iç içe if, takip etmesi zor bir fonksiyon
---
# Reduce Nesting
Derin iç içe geçme, okumadığın dallardaki hataları gizler.
- **Guard clause'lar** — geçersiz/kenar durumları önce ele al ve erken dön. Mutlu yol (happy path) sol marja iner.
- **Koşulları tersine çevir** — tüm gövdeyi `if (valid) {...}` içine sarmak yerine `if (!valid) return;`.
- **Ayır (extract)** — tek bir iş yapan iç içe blok, adlandırılmış bir fonksiyona dönüşür.
- **Flag-sonra-dallan'ı değiştir** — sonra döndürmek için bir değişken atamak yerine sonucu doğrudan döndür.
Hedef: hiçbir fonksiyon 2-3 seviyeden derin olmasın. Hâlâ daha fazlasına ihtiyacın varsa, fonksiyon çok fazla iş yapıyordur — böl.
