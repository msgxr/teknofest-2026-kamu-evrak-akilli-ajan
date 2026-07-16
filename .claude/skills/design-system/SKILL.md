---
name: design-system
description: Frontend çıktısının AI-üretimi değil, kasıtlı görünmesini sağla. Herhangi bir UI işi için kullan — bileşenler (components), sayfalar, yerleşimler (layouts).
when_to_use: UI, bir bileşen, bir sayfa inşa etme, "bunu güzel göster"
---
# Tasarım Sistemi (Design System)
Varsayılan AI UI'ı gri, ortalanmış ve çekingendir. Onu gönderme.
- **Tipografi (Type)** — bir ayırt edici başlık yüzü (display face) + bir temiz gövde yüzü (body face). Gerçek bir ölçek (ör. 12/14/16/20/28/40), her şey 16px değil.
- **Renk (Color)** — bir güçlü vurgu (accent), gerçek bir nötr rampa, kasıtlı kontrast. 5 rakip marka rengi olmasın.
- **Boşluk (Space)** — bir boşluk ölçeği (4/8/12/16/24/32...). Cömert beyaz boşluk (whitespace). Bir ızgaraya (grid) hizala.
- **Hareket (Motion)** — yalnızca amaçlı: eylemde geri bildirim, durum değişiminde geçişler. Dekoratif zıplama (bounce) olmasın.
- **Hiyerarşi (Hierarchy)** — her ekranda bir net odak noktası. İşi boyut, ağırlık ve boşluk yapar, her yerdeki kenarlıklar (borders) değil.
Bitmeden önce: kıdemli bir tasarımcı bunu gönderir miydi, yoksa varsayılan bir Tailwind şablonu gibi mi görünüyor? İkincisiyse, kontrastı ve tipografiyi ileri it.
