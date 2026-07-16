---
description: Mevcut diff üzerinde toplu kalite turu — simplify → reduce-nesting → kill-dead-code → a11y-pass → loading-empty-error-states → readme-audit.
argument-hint: "[--dry-run]"
allowed-tools: Read, Edit, Grep, Bash(git diff:*), Bash(git status:*), Bash(git log:*), Bash(ls:*)
---

# /polish — mevcut diff üzerinde tek seferlik kalite turu

Çalışma ağacındaki mevcut değişikliklere altı kalite skill'ini sabit sırayla uygula, sonda
tek özet. Yeni özellik yok. Her skill'in yetki verdiğinin ötesinde davranış değişikliği yok.

## Kapsam
**Bu komut YALNIZCA mevcut git diff'ine uygulanır.** Emin değilsen önce `git diff` çalıştır.
Çalışma ağacı temizse dur ve kullanıcıya cilalanacak bir şey olmadığını söyle.

## Adımlar
1. Diff'i yükle: `git diff HEAD` ve `git status --short`. Tüm oturum boyunca bu değişen dosya
   kümesine sabitlen; dokunulmamış koda dalma.
2. Aşağıdaki her skill'i sırayla uygula. Her biri için: skill dosyasını
   `.claude/skills/<ad>/SKILL.md`'den oku, kontrol listesini diff'e karşı yürüt, yetki verdiği
   düzeltmeleri uygula. Skill bu diff'e uymuyorsa (ör. backend değişikliğine `a11y-pass`),
   tek satır gerekçeyle `atlandı` kaydet ve devam et.

   1. **simplify** — gereksiz dolaylılığı topla.
   2. **reduce-nesting** — erken dönüşler, koruma cümleleri.
   3. **kill-dead-code** — ulaşılamazlığı kanıtla, sonra sil (Chesterton çiti: nedenini önce anla).
   4. **a11y-pass** — anlambilim + klavye + kontrast (yalnız UI diff'leri: `app.py` / `src/app.py` / Streamlit).
   5. **loading-empty-error-states** — dört durumun hepsi, yalnız mutlu yol değil (yalnız asenkron/UI görünümleri).
   6. **readme-audit** — soğuk-onboarding kontrolü (yalnız README veya genel arayüz değiştiyse).

3. Sonda tam olarak TEK özet, tablo halinde:
   ```
   | skill                      | yapilan_islem                         | hüküm             |
   |----------------------------|---------------------------------------|-------------------|
   | simplify                   | <tek satır>                           | uygulandı/atlandı |
   | reduce-nesting             | <tek satır>                           | uygulandı/atlandı |
   | kill-dead-code             | <tek satır>                           | uygulandı/atlandı |
   | a11y-pass                  | <tek satır>                           | uygulandı/atlandı |
   | loading-empty-error-states | <tek satır>                           | uygulandı/atlandı |
   | readme-audit               | <tek satır>                           | uygulandı/atlandı |
   ```

## Asla
- Cila turuyla ilgisiz yeni özellik ekleme veya hata düzeltme. Gerçek bir hata görürsen özete
  not düş ve dur — kullanıcıya devret, kapsamı sessizce genişletme.
- 1. adımda yüklediğin diff dışındaki dosyalara dokunma.
- Mevcut testleri zayıflatma/silme. Cila sonrası test kırılırsa ilgili cila düzenlemesini geri
  al — test kazanır.
- Özeti atlama. Tek diff, tek tablo, skill başına tek hüküm.

## Hatırlatma
Bu komut YALNIZCA mevcut git diff'ine uygulanır. Emin değilsen önce `git diff` çalıştır.
