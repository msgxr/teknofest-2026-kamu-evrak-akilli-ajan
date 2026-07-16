---
name: using-loopkit
description: loopkit-etkin bir projede herhangi bir konuşmaya başlarken kullan — loopkit'in 53 skill'inin nasıl bulunup kullanılacağını belirler; açıklayıcı sorular dahil HERHANGİ bir yanıttan önce skill çağrısı gerektirir.
---

# Loopkit Kullanımı

<EXTREMELY-IMPORTANT>
Yaptığın işe bir loopkit skill'inin uyma ihtimali %1 bile olsa, onu ÇAĞIR.

BİR SKILL UYGUNSA, SEÇME HAKKIN YOK. ONU KULLANMAK ZORUNDASIN.

Bu, "hızlıca yanıtla" içgüdülerini geçersiz kılar. Pazarlık konusu değil.
</EXTREMELY-IMPORTANT>

## Kural

**İlgili skill'leri herhangi bir yanıt veya eylemden ÖNCE çağır** — açıklayıcı sorular, kod tabanını keşfetme veya dosya okuma dahil. Durum için yanlış çıkarsa, bırak.

Ardından "[amaç] için [skill] kullanılıyor" diye duyur ve skill'i aynen izle. Bir kontrol listesi varsa, her madde için bir todo oluştur.

## Skill'ler nerede yaşar

Skill'ler `.claude/skills/<name>/SKILL.md` konumundaki dosyalardır. Her birinin `name` ve `description` içeren YAML frontmatter'ı vardır (description bir tetikleyici ifadedir, özet değil). Tetiği görevinle eşleştiğinde SKILL.md'sini okuyarak bir skill yükle.

## Skill yönlendirme (53 skill, 10 hat)

| Görev şekli | İlk skill |
|---|---|
| "Bu hatayı düzelt" / test başarısız / çökme | `systematic-debugging`, sonra `read-the-trace` |
| "İki commit arasında bozuldu" | `bisect-regression` |
| "Kararsız test (flaky test)" | `flaky-hunter` |
| "Özellik ekle" / yeni bir şey yaz | `spec-first`, sonra `write-failing-test-first` |
| "Refactor" / ölü kod / derin iç içelik | `kill-dead-code`, `simplify`, `reduce-nesting` |
| Tamamlandı demek / commit / PR açmak üzere | `adversarial-verify` + `verification-before-completion` + `self-eval-bias` |
| Bir diff'i incele | `adversarial-verify`, `pr-from-diff` |
| Frontend / UI işi | `design-system`, `a11y-pass`, `loading-empty-error-states` |
| Güvenliğe dokunuş | `owasp-review`, `authz-check`, `input-validation`, `secret-scan`, `dependency-audit` |
| Veri / SQL / göçler (migrations) | `sql-review`, `migration-writer`, `schema-diff` |
| Dokümanlar / changelog / README | `changelog-from-diff`, `decision-record`, `readme-audit` |
| Git işlemleri | `clean-commits`, `pr-from-diff`, `rebase-safely`, `revert-surgical` |
| Test paketi boşlukları | `coverage-gaps`, `contract-test` |
| Bağlam tükeniyor | `context-budget`, `tool-restraint` |
| Paralel iş | `subagent-fanout` |
| Yeni proje / büyük özellik başlatma | `planner-spec-expand`, sonra `feature-list-json`, sonra `init-script-contract` |
| Mevcut çok-oturumlu bir projeye giriş yapma | `progress-reading-protocol` |
| Bir uygulama sprint'ine girme | `sprint-contract` |
| Bir denetçi / değerlendirici kalibre etme | `evaluator-calibration` |
| Yeni Claude/Sonnet/Opus modeli geldi | `harness-stripping` |

Tam liste: `ls .claude/skills/`.

## Kırmızı Bayraklar — DUR ve bir skill olup olmadığını kontrol et

| Düşünce | Gerçek |
|---|---|
| "Bu sadece basit bir soru" | Sorular görevdir. Önce kontrol et. |
| "Önce kod tabanını keşfedeyim" | Skill'ler sana NASIL keşfedeceğini söyler. Önce kontrol et. |
| "Bu skill'i hatırlıyorum" | Skill'ler evrilir. Güncel SKILL.md'yi oku. |
| "Skill fazla kaçar" | Basit şeyler karmaşıklaşır. Kullan. |
| "Önce şu tek şeyi yapayım" | Herhangi bir şey yapmadan ÖNCE kontrol et. |
| "Testler geçiyor, iyiyiz" | `verification-before-completion` der ki: tam komutu çalıştır, çıktıyı oku, sonra iddia et. |
| "Buradayken iki özelliği de yaparım" | `single-feature-discipline` der ki: oturum başına bir tane. Asla iki. |
| "Denetçi bunu görmezden gelir" | `self-eval-bias` der ki: kendinden emin bir şekilde öveceğini varsay. Önce kalibre et. |

## Birden fazla skill uyduğunda öncelik

Önce süreç skill'leri (spec-first, systematic-debugging, planner-spec-expand, sprint-contract), sonra uygulama skill'leri (design-system, sql-review, vb.), sonra bitiriciler (adversarial-verify, verification-before-completion, self-eval-bias, clean-commits).

- "X'i inşa edelim" → `planner-spec-expand` → `feature-list-json` → `sprint-contract` → alan skill'leri → `adversarial-verify`.
- "Y hatasını düzelt" → `systematic-debugging` → `read-the-trace` → düzeltme → `verification-before-completion`.
- "Mevcut projede oturum açık" → `progress-reading-protocol` → `sprint-contract` → iş.

## Skill yayın (release) kuralı

loopkit'teki her yeni skill, dört zorunlu dosya içeren bir klasör olarak yayınlanır. İstisna yok — bunlar olmayan bir skill taslaktır, yayın (release) değil.

```
skills/<skill-name>/
  SKILL.md            # the skill itself (frontmatter + procedure)
  POST.md             # ~200-word X-thread-shaped explainer
  evidence/
    before.md         # verbatim transcript WITHOUT the skill loaded
    after.md          # same prompt WITH the skill loaded
```

- `SKILL.md` — frontmatter `description`'ına göre yönlendirilir. Gövde ~150 satırın altında.
- `POST.md` — duyuru dizisi (thread). `template/POST.md`'den kopyala, yayınlamadan önce her yer tutucuyu (placeholder) doldur.
- `evidence/before.md` + `evidence/after.md` — bir gerçek görev, her iki transkript. before/after çifti, skill'in davranışı gerçekten değiştirdiğinin makbuzudur. Üretemiyorsan, skill hazır değildir; taslak olarak indir (land) ve kanıt gerçek olduğunda birleştir (merge).

Yeni bir skill'i `template/`'i aynen kopyalayarak başlat:

```
cp -r template skills/<skill-name>
```

Ardından SKILL.md'yi düzenle, POST.md yaz ve before/after çiftini yakala.

## Kullanıcı talimatları kazanır

CLAUDE.md, AGENTS.md ve doğrudan kullanıcı istekleri loopkit skill'lerini geçersiz kılar. Bir skill iş akışını yalnızca kullanıcı açıkça söylediğinde atla.
