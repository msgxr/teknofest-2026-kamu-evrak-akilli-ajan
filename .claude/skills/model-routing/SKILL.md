---
name: model-routing
description: Planla/Uygula/Doğrula döngüsünü üç model katmanına böl — sınır (frontier) planlayıcı, ucuz uygulayıcı, sınır yargıç — run.sh tarafından okunan env değişkenleri aracılığıyla.
when_to_use: uzun ve gözetimsiz bir döngü maliyet için ayarlanırken veya uygulayıcıdan daha güçlü bir yargıç istediğinde.
---

# Model routing

`run.sh` üç opsiyonel env değişkenini okur ve her `claude` çağrısına `--model` olarak geçirir. Hepsi varsayılan olarak boştur (unset); bu durumda CLI varsayılan modeli kullanılır (çıplak bir koşuma göre davranış değişmez).

## Üç ayar düğmesi

- `CLAUDE_PLANNER_MODEL` — baştan `PROMPT.md` taslağı çıkaran `/spec` iş akışları için ayrılmıştır. Mevcut `run.sh` döngüsü tarafından okunmaz, ancak gelecekteki planlayıcı geçişlerinin buna bağlanması için burada rezerve edilir.
- `CLAUDE_EXECUTOR_MODEL` — "sıradaki adımı yap" çağrısında kullanılır. Bu, iş atıdır; her iterasyonda çalışır. Ucuz ve hızlı bir şey seç.
- `CLAUDE_JUDGE_MODEL` — `/verify` çağrısında kullanılır. Uygulayıcının diff'ini düşmanca denetlemek için iterasyon başına bir kez çalışır. Bir sınır (frontier) modeli seç — zayıf bir yargıç, yargıcın olmamasından beterdir.

## Önerilen şekil

```
planner  = frontier   (Opus-sınıfı, /spec anında bir kez çalışır)
executor = cheap-fast (Haiku-sınıfı, her turda çalışır)
judge    = frontier   (Opus-sınıfı, her turda ama küçük bir diff üzerinde çalışır)
```

## Örnek

```bash
export CLAUDE_PLANNER_MODEL="claude-opus-4-7"
export CLAUDE_EXECUTOR_MODEL="claude-haiku-4-7"
export CLAUDE_JUDGE_MODEL="claude-opus-4-7"
./run.sh
```

## Elvis Uygulayıcı+Yargıç bulgusu

Ucuz bir uygulayıcının bir sınır yargıçla eşleştirilmesi, uzun döngülerde yargıcı olmayan bir sınır uygulayıcıyı geride bırakır. Yargıç, mono-model bir koşumun context'i tükendiğinde mantığa büründürüp geçiştirdiği erken-zafer (premature-victory) iddialarını yakalar. Yargıç yalnızca diff'i, tüm çalışma geçmişini değil, gördüğü için maliyet düşük kalır.
