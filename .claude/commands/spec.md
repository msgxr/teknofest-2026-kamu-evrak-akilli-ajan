---
description: Kod yazmadan önce hedef spesifikasyonunu (PROMPT.md) yaz. loopkit spec-first skill'ini yükler.
argument-hint: "[--force]"
allowed-tools: Read, Write, Bash(ls:*)
---

# /spec — icraat öncesi hedef spesifikasyonunu yaz

Harici bir sözleşme olmadan ajan ~3 iterasyondan sonra sürüklenir ve başarısızlık ilerleme
gibi görünür (kod yazıldı, testler geçti, yanlış hedef çözüldü). Bu, CLAUDE.md Anayasa
İlke 5 (Önce planlama) ve İlke 6 (Ayrıştırma) ile birebir örtüşür.

## Adımlar

1. `PROMPT.md` varsa ve `--force` geçilmediyse dur ve yaz:
   > `PROMPT.md` zaten var. Üzerine yazmak için `/spec --force`, ya da dosyayı elle düzenle.
2. `spec-first` skill'ini `.claude/skills/spec-first/SKILL.md` dosyasını okuyarak yükle.
3. `.claude/templates/PROMPT.md` şablonundan `PROMPT.md` yaz; kullanıcının son mesajından doldur:
   - **Hedef** — tek cümle, kullanıcı tarafından gözlemlenebilir sonuç.
   - **Tamamlandı sayılır** — somut, test edilebilir koşullar. Yeşile dönmesi gereken **tam
     komutu** yaz (ör. `pytest tests/` veya `python scripts/evaluate.py ...`).
   - **Asla dokunma** — sınır dışı dosya/alanlar (ör. `data/raw/*_heldout*`, `eval_report*.json`).
   - **Şu durumda dur** — iptal koşulları (kapsam kayması, geçen testin kırılması, kapsam
     dışı N'den fazla dosya değişimi, Türkçe/offline-first/held-out ihlali riski).
4. `.claude/templates/IMPLEMENTATION_PLAN.md` şablonundan `IMPLEMENTATION_PLAN.md` yaz;
   1. satırda tam olarak `STATUS: not-started` olsun (`run.sh`'ın grep'lediği dizge budur).
5. İki dosya yolunu yazdır ve **DUR**. Aynı turda icraata geçme.

## Şu durumda reddet
- İstek "Tamamlandı sayılır" koşulunu somut yazamayacak kadar belirsizse: 1-3 netleştirici
  soru sor ve dur.
- Görev tek satırlık bir refactor ya da yazım hatasıysa: `/spec` 2 adımdan fazla görevler içindir.

## Asla
- Görev "küçük görünüyor" diye `PROMPT.md`'yi atlama.
- İcraat sonrası `PROMPT.md`'yi teslim edilene uyacak şekilde düzenleme — bu sürüklenmedir,
  spesifikasyon değil.
- `/spec` ile aynı turda kod yazmaya başlama. Kullanıcı önce inceler.
