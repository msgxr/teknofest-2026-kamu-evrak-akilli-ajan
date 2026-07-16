---
description: Önerilen sonraki işleri, mevcut backlog'a dokunmadan taslak halinde çıkar (ayrı bir öneri dosyasına).
allowed-tools: Read, Write, Bash(git log:*), Bash(cat:*)
---

# /next — backlog'u değiştirmeden yeni iş öner

Backlog kuruduğunda (P0/P1/P2 kalanların hepsi kapandığında) veya spesifikasyon sessizce
mevcut listenin ötesine büyüdüğünde kullan. Bu projenin backlog'u hafızadaki
`p0-backlog-durumu.md` ve `docs/` içindeki yol haritasıdır.

## Adımlar
1. `suggest-next-features` skill'ini `.claude/skills/suggest-next-features/SKILL.md`'den oku.
2. Prosedürünü uçtan uca izle: `git log --oneline -30` oku, son teknik rapor/backlog
   durumunu tara, mevcut yol haritasına karşı farkı çıkar.
3. Projenin dürüstlük ve şartname süzgecinden geçen **5-10 aday** yaz; kök dizinde
   `feature_oneri_taslagi.md` dosyasına (önceki taslağın üzerine).
4. Öneri başına tek satır özet yazdır: `[kategori] açıklama — gerekçe`.
5. Dur. Mevcut backlog/yol haritası dosyalarına dokunma. Öneri dosyasını **commit etme**
   (aşağıdaki oto-commit hook'una rağmen: `.gitignore`'a eklenmediyse elle `git reset` ile
   ayır). Kullanıcı istediği maddeleri elle birleştirir.

## Asla
- Bu komuttan mevcut backlog/yol haritası dosyalarını düzenleme.
- Bir seferde 10'dan fazla öner — uzun listeler okunmaz, göz gezdirilir.
- Şartname/dürüstlük süzgecinden geçmeyen (Türkçe-dışı, held-out sızıntısı, sahte metrik,
  gerçek PII, offline-first bozan) öneri üretme.
