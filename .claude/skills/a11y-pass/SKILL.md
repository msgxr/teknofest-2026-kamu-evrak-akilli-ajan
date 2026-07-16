---
name: a11y-pass
description: Neredeyse her yapay zeka ile üretilen arayüzde (UI) sevk edilen erişilebilirlik (accessibility) hatalarını yakala. Herhangi bir etkileşimli bileşen inşa ettikten sonra kullan.
when_to_use: formlar, butonlar, modaller, görseller, renk seçimleri, klavye etkileşimi
---
# Accessibility Pass
- **Klavye** — her etkileşimli öğeye Tab/Enter/Esc ile ulaşılabilir ve işletilebilir olmalı. Modaller odağı (focus) tuzaklar ve kapanışta geri yükler.
- **Etiketler** — her input'un gerçek bir `<label>`'ı var; yalnızca ikonlu butonlarda `aria-label` var.
- **Görseller** — anlamlı `alt`; dekoratif görsellerde `alt=""`.
- **Kontrast** — metin ≥ 4.5:1 (büyük için 3:1). Anlamı yalnızca renkle kodlama.
- **Semantik** — tıklanabilir bir `<div>` değil, gerçek `<button>`/`<a>`. Başlıklar sırayla.
- **Odak (focus)** — görünür odak halkası (focus ring). Yerine bir şey koymadan asla `outline: none`.
Çıktı: her hatayı öğe + düzeltmesiyle ver. Yalnızca Tab ile, fare olmadan test et.
