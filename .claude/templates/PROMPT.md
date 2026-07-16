# Hedef Spesifikasyonu (PROMPT.md)

> Bu dosya `/spec` ile üretilir ve icraatın harici sözleşmesidir. Teslim edileni buna
> uydurmak için sonradan DÜZENLENMEZ — bu sürüklenmedir. Şablon: `.claude/templates/PROMPT.md`.

## Hedef
<!-- Tek cümle, kullanıcı tarafından gözlemlenebilir sonuç. -->

## Tamamlandı sayılır
<!-- Somut, test edilebilir koşullar. Yeşile dönmesi gereken TAM komutu yaz. -->
- [ ] `pytest tests/` yeşil
- [ ] <ör. `python scripts/evaluate.py --veri-dizini data/raw/kurgu_evraklar --rapor-dosyasi data/processed/eval_report.json` metrik hedefi karşılıyor>
- [ ] <uçtan uca senaryo elle doğrulandı>

## Asla dokunma
<!-- Sınır dışı dosya/alanlar. -->
- `data/raw/*_heldout*` (held-out bütünlüğü)
- `data/processed/eval_report*.json` (yalnız evaluate.py üretir)
- <diğer>

## Şu durumda dur
<!-- İptal koşulları. -->
- Kapsam dışı N'den fazla dosya değişiyor.
- Geçen bir test kırmızıya dönüyor.
- Türkçe / offline-first / held-out / gerçek-PII ihlali riski beliriyor.
- <diğer>
