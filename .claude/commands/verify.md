---
description: "Tamamlandı" demeden önce mevcut diff üzerinde düşmanca (adversarial) doğrulama çalıştır. loopkit adversarial-verify skill'ini yükler ve verifier subagent'ını görevlendirir.
argument-hint: "[--summary]"
allowed-tools: Read, Grep, Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(pytest:*)
---

# /verify — düşmanca doğrulama turu

Diff'in bozuk olduğunu varsay. Bozuk olmadığını kanıtla. (Anayasa İlke 7: Öz-denetim.)

## Adımlar

1. Hedef spesifikasyonu yükle:
   - `PROMPT.md` varsa oku. Yoksa `IMPLEMENTATION_PLAN.md`'yi oku.
   - İkisi de yoksa dur ve kullanıcıya önce `/spec` çalıştırmasını söyle. Sözleşme yokken
     doğrulama yapma.
2. Mevcut diff'i yükle:
   - `git diff HEAD` — commit'lenmemiş değişiklikler.
   - `git log --oneline -5` — yakın bağlam.
3. `adversarial-verify` skill'ini `.claude/skills/adversarial-verify/SKILL.md` okuyarak
   çağır. 11 kısayol listesini diff'e karşı **kelimesi kelimesine** yürüt, ayrıca
   `.claude/docs/checklists/red-flags.md` içindeki 4 çevresel işareti kontrol et.
4. **Bu projeye özgü ek denetim** (şartname/dürüstlük süzgeci):
   - Türkçe çıktı zorunluluğu ihlali var mı?
   - Held-out set (`data/raw/*_heldout*`) üzerine bakılarak kural/kod düzeltildi mi? (öyleyse
     `docs/teknik_rapor.md` §5'e yazılmalı)
   - `eval_report*.json` elle mi düzenlendi? (yalnızca `scripts/evaluate.py` üretmeli)
   - Offline-first bozuldu mu? Çekirdek akışa zorunlu LLM/ağ eklendi mi?
5. `verifier` subagent'ını (`.claude/agents/verifier.md`) aynı diff üzerinde ikinci, soğuk-bağlam
   turu için görevlendir.
6. Tek bir JSON hükmü döndür, başka hiçbir şey değil:
   ```json
   {"passes": true, "failures": [{"file": "src/x.py", "line": 12, "shortcut": "...", "why": "..."}]}
   ```
7. `passes` false ise: **commit ETME**, görevi tamamlandı **işaretLEME**, hata listesini yazdır ve dur.

## Asla
- Bu turda düzeltme önerme. Doğrulama ve onarım ayrıdır; karıştırmak modelin kendini
  rasyonelleştirmesine yol açar.
- Uygulama kodunu çalıştırma (test koşusu `pytest` hariç, ama değiştirme). Salt-okunur araçlar.
- Nazik olma. Nezaket, "sahte tamamlandı"nın gemiye bindiği yoldur.
- "Diff küçük" diye kısayol listesini atlama.

## Çıkış sözleşmesi
Herhangi bir başarısızlıkta sıfır-olmayan çıkış. `run.sh` döngüsü bunu "tamamlanmadı" sayıp
sonraki turda yeniden çalışır.
