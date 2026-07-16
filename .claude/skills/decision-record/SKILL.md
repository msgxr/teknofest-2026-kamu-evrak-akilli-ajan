---
name: decision-record
description: Bir mimari kararı, bir sonraki oturumun (veya mühendisin) NEDEN'ini bilmesi için kaydedin. Herhangi bir aşikâr olmayan teknik seçimden sonra kullanın.
when_to_use: bir kütüphane/desen/şema seçildi, bir ödünleşim (tradeoff) yapıldı, geri alması zor bir seçim
---
# Karar Kaydı (ADR)
Kısa bir dosya yaz `docs/decisions/NNN-<slug>.md`:
- **Bağlam (Context)** — kararı zorlayan neydi. Kısıtlar.
- **Seçenekler (Options)** — 2-3 gerçek aday, her biri tek satır.
- **Karar (Decision)** — ne seçtin, tarihiyle.
- **Neden (Why)** — ödünleşim. Neyden vazgeçtin. "Mongo yerine Postgres'i seçtik çünkü gerçek join'lere ihtiyacımız var; daha ağır operasyonu kabul ediyoruz."
- **Sonuçlar (Consequences)** — bunun artık neyi kolay, neyi zor kıldığı.
Geri alması zor seçimler (şema, kimlik doğrulama (auth), veri deposu) MUTLAKA bir tane almalı. Gelecekteki sen "bunu da neden yaptık ki" diye soracak — şimdi yanıtla.
