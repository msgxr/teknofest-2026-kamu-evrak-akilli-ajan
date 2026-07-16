---
name: subagent-fanout
description: Bağımsız alt işleri tek bir şişmiş context yerine taze-context'li subagent'lara dağıtarak paralelleştir. Bir hedef çok sayıda bağımsız parçaya dallandığında kullan.
when_to_use: N öğe analiz et, M dosya düzelt, K kaynak ara, utanç verici derecede paralel her şey
---
# Subagent Fan-out
On işlik malzemeyle yüklü tek bir context, tam olarak context rot'u tetikleyen şekildir. On küçük context tetiklemez.
- Her bağımsız birim için bir subagent üret (bir dosya, bir kaynak, bir kontrol). Her biri taze bir context penceresi alır.
- Bir **orkestratör** onların sonuçlarını sentezler — birim başına işi asla kendisi yapmaz.
- Her işçiye dar bir rol ve yalnızca ihtiyaç duyduğu girdiyi ver.
- YALNIZCA parçalar gerçekten bağımsızken kullan. Sıralı bağımlılıklar tek bir zincirde kalır.
Genişlik için fan-out uygula (araştırma, çok-dosyalı düzenlemeler, çok-kaynaklı doğrulama). N. adım N-1. adımın çıktısına ihtiyaç duyduğunda sıralı (serial) tut.
