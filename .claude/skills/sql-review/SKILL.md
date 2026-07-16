---
name: sql-review
description: SQL ve ORM sorgularını yayına çıkmadan önce doğruluk, güvenlik ve performans açısından incele.
when_to_use: yeni sorgu, bir migration, N+1 şüphesi, yavaş bir uç nokta (endpoint)
---
# SQL Review
- **Injection** — her zaman parametreli. SQL'e string interpolasyonu yok.
- **N+1** — döngü içinde bir sorgu mu var? Bir join ya da toplu (batched) IN ile değiştir.
- **Eksik index** — WHERE/JOIN/ORDER BY indexli bir kolona mı vuruyor? Vurmuyorsa, ölçek büyüdükçe tablo taraması (table scan) su yüzüne çıkar.
- **Sınırsız (unbounded)** — büyüyen bir tabloda LIMIT'siz SELECT; satırları çoğaltan (fan-out) bir JOIN.
- **Transaction'lar** — çok-yazışlı (multi-write) işlemler, kısmi bir başarısızlık durumu bozamayacak şekilde sarmalanmış.
- **Migration'lar** — geri döndürülebilir (up VE down) ve canlı tabloda güvenli (yoğun bir tabloda tepe (peak) anında bloklayan lock yok).
Çıktı: her sorun, satırı ve düzeltilmiş hâliyle (rewrite). Performans kaygıysa EXPLAIN'i göster.
