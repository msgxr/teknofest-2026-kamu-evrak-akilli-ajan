---
name: kill-dead-code
description: Ulaşılamayan/kullanılmayan kodu güvenle bul ve kaldır. Temizlik sırasında veya bir refactor öncesinde kullan.
when_to_use: temizlik, "kullanılmayanı kaldır", refactor öncesi, ölü dallar
---
# Kill Dead Code
1. **Ölü olduğunu kanıtla** — referans yok (sembolü depo genelinde grep'le; dinamik/string kullanımı ve testler dahil). Kullanılmayan export ≠ ölü, eğer bir public API ise.
2. Feature-flag ile kapatılmadığından emin ol (bugün ölü, flag açılınca canlı).
3. Onu VE artık öksüz kalan testlerini, importlarını ve config'ini sil.
4. Tüm test paketini (suite) + bir build çalıştır. Ölü kod kaldırma, davranışı tam olarak sıfır şekilde değiştirmelidir.
Silmeye eğilimli ol: birinin okumak zorunda olduğu her satır bir maliyettir. Ama ulaşılamaz olduğunu kanıtlayamadığını asla silme — tahmin etmek yerine "Sanırım X kullanılmıyor, onaylıyor musun?" de.
