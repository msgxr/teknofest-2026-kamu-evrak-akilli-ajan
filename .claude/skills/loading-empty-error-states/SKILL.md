---
name: loading-empty-error-states
description: Her veri arayüzünün (UI) unuttuğu üç durumu tasarla. Veri çeken (fetch) veya listeleyen herhangi bir bileşen için kullan.
when_to_use: bir liste, bir fetch, bir dashboard, arayüzdeki herhangi bir asenkron şey
---
# Loading / Empty / Error States
Yapay zeka ile üretilen arayüzler mutlu yolu (happy path) ele alır ve diğer üçünde çöker. Dördünü de tasarla:
- **Loading** — nihai düzene uyan iskeletler (skeleton) (her şeyi kaydıran ortalanmış bir spinner değil).
- **Empty** — gerçek bir ilk-çalıştırma (first-run) durumu: ne olduğu ve onu doldurmak için tek eylem. Boş bir kutu değil.
- **Error** — neyin başarısız olduğu, insani terimlerle, artı bir yeniden dene (retry). Asla ham bir stack trace veya sessiz bir hiçlik.
- **Partial** — yavaş/streaming veri, geri alınabilen (roll back) iyimser güncellemeler (optimistic updates).
Diff'teki her fetch için dördünün de var olduğunu doğrula. Ürünlerin bozuk hissettirdiği yer empty ve error durumlarıdır.
