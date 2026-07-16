@../AGENTS.md

# Loopkit — Claude'a özgü notlar

Bu dosya, loopkit döngü sistemine Claude Code'a özgü eklentidir. Bağlayıcı proje
kuralları için kök `CLAUDE.md` (Proje Anayasası) ve `AGENTS.md` (döngü sözleşmesi)
esastır — burada tekrarlanmaz. Sıralama: **Kullanıcı talimatı > Anayasa (kök CLAUDE.md)
> AGENTS.md > loopkit skill'leri.**

## Giriş noktaları (slash komutları)

- `/spec` — icraat öncesi `PROMPT.md` yaz. `PROMPT.md` varsa `--force` olmadan çalışmaz.
- `/verify` — mevcut diff'e karşı düşmanca doğrulama; `verifier` subagent'ını görevlendirir.
- `/polish` — mevcut diff'e altı kalite skill'ini tek turda uygular.
- `/next` — backlog'a dokunmadan yeni iş önerileri taslağı çıkarır.

## Skill yönlendirme

Skill'ler `.claude/skills/<ad>/SKILL.md` dosyalarıdır. Her birinin frontmatter `description`'ı
bir tetikleyici ifadedir (özet değil). Görevine uyan bir tetik varsa, **başka bir eylemden
önce** o skill'in SKILL.md'sini oku. Tam yönlendirme tablosu aşağıda içe aktarılmıştır.

@skills/using-loopkit/SKILL.md

## verifier subagent

`.claude/agents/verifier.md` — `/verify` tarafından görevlendirilen, haiku üzerinde çalışan
düşmanca denetçi. Diff'i "bozuk" varsayarak 11 kısayolu + projeye özgü kırmızı bayrakları
(Türkçe ihlali, held-out sızıntısı, sahte metrik, offline-first, gerçek PII) tarar. Bir eval
grader olarak da yeniden kullanılabilir.

## Opsiyonel hook'lar (elle etkinleştirilir)

`.claude/hooks/format_edited.py` (ruff biçimlendirme) ve `.claude/hooks/pre_compact.py`
(karar kaydı) betikleri, otomatik çalıştırılan kod oldukları için `settings.json`'a **elle**
bağlanmadıkça pasiftir. Bağlama talimatı: `docs/loopkit_kurulum.md`. Mevcut oto-commit+push
Stop hook'u (`settings.local.json`) korunur.

<!-- 300 satır altında tut. Her paragraf her turda bir vergidir. -->
