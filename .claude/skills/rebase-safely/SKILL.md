---
name: rebase-safely
description: İşi kaybetmeden veya paylaşılan dalları (branch) bozmadan rebase yapın, squash'layın ya da geçmişi yeniden yazın. Herhangi bir geçmiş yeniden yazımından önce kullanın.
when_to_use: rebase, squash, "dalımı güncelle", interaktif rebase, force-push
---
# Güvenli Rebase (Rebase Safely)
1. **Önce yedekle** — herhangi bir yeniden yazımdan önce `git branch backup/<name>`. Bedava geri alma.
2. En güncel tabanın üzerine rebase yap: `git fetch; git rebase origin/main`.
3. Çatışmaları (conflict) commit commit çöz. Rebase'ten sonra test et, sadece "tamamlandı" olmasına değil.
4. **Paylaşılan geçmişi asla yeniden yazma** — başkaları dalı çektiyse (pull), onu rebase'lemek onları acıya sokar. Yalnızca kendi push'lanmamış/paylaşılmamış commit'lerini yeniden yaz.
5. `--force-with-lease` ile push'la, asla çıplak `--force` ile değil (lease, başkası push'ladıysa reddeder).
Bir şey ters giderse: `git reflog` rebase-öncesi durumu bulur; `git reset --hard backup/<name>` onu geri yükler.
