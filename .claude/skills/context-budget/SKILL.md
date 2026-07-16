---
name: context-budget
description: Ajanın context'ini yalın tut ki doğruluk çökmesin. Uzun oturumlarda, büyük dosyalarda veya ajan halüsinasyon görmeye başladığında kullan.
when_to_use: uzun oturum, devasa dosya dökümü, ajan önceki adımları unutuyor, doğruluk düşüyor
---
# Context Budget
Daha fazla context daha iyi değildir. Bir eşiğin ötesinde, doğruluk uçurumdan düşer (context rot).
- **Tüm dosyaları dökme** — 2000 satırlık modülü değil, ilgili fonksiyonu/bölümü oku.
- **Biriktirme, özetle** — 200K token'lık bir transcript'i, yük taşıyan gerçeklerin 4K'lık bir özetiyle değiştir.
- **Ölü context'i at** — bir alt görev bitince, ayrıntısı pencereden çıkar. Kararı tut, izi (trace) at.
- **Durum diskte olsun, context'te değil** — ilerleme, sürekli büyüyen bir prompt'a değil, bir sonraki turun yeniden okuduğu bir dosyaya gider.
Şişmiş bir kalıcı context (CLAUDE.md) her turu vergilendirir. Haftalık kırp. Ajan kendinden emin bir şekilde yanılıyorsa, modelden önce context'ten şüphelen.
