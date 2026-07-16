---
name: clean-commits
description: Dağınık WIP'i, nedenini açıklayan mesajlarla temiz ve atomik commit'lere dönüştürün. PR açmadan önce kullanın.
when_to_use: PR öncesi, dağınık geçmiş, "bunu squash'la", commit mesajı yardımı
---
# Temiz Commit'ler (Clean Commits)
- **Atomik** — commit başına tek mantıksal değişiklik. Yeniden düzenleme (refactor) ve davranış değişikliği ayrı commit'lere gider.
- **Mesaj** — konu satırı NE yapıldığını emir kipiyle söyler ("Kullanıcı aramasındaki null pointer'ı düzelt"), gövde NEDEN'i söyler. "Hata düzeltildi" işe yaramaz.
- **Spesifik** — "E-postada büyük harf olunca başarısız olan girişi düzelt" bir sonraki kişiye tam olarak ne olduğunu anlatır.
- WIP ve "yazım hatası düzeltildi" commit'lerini gerçek değişikliklere yeniden sırala/squash'la (`git rebase -i`).
- Alakasız bir düzeltmeyi asla bir özellik commit'ine karıştırma.
İyi bir geçmiş, bir hata ayıklama aracıdır: `git bisect` ve `git blame` yalnızca commit'ler atomik ve mesajlar niyeti açıklıyorsa çalışır.
