# AGENTS.md — loopkit döngü sözleşmesi (TEKNOFEST 2026)

Bu depo uzun-ömürlü ajan oturumları çalıştırır. Her oturum tek bir sözleşmeyi paylaşır:
**Planla → Uygula → Doğrula**, oturum başına tek özellik, sonda temiz durum.

Bu dosya çapraz-ajan sesidir (Claude Code, Cursor, Codex CLI, Gemini CLI). Claude'a özgü
eklentiler `.claude/CLAUDE.md`'dedir (`@../AGENTS.md` ile bu dosyayı içe aktarır). Bağlayıcı
proje kuralları için kök `CLAUDE.md` (Proje Anayasası) esastır ve bu dosyayı geçersiz kılar.

## Üç adımlı döngü

Her oturum, sırayla:

1. **Planla.** `PROMPT.md` (hedef), `IMPLEMENTATION_PLAN.md` (durum) ve `git log --oneline -20`
   (geçmiş) oku. Son oturum bir özelliği tamamlandı iddia ettiyse, yeni iş seçmeden önce
   duman testi (smoke-test) yap. Karmaşık işte `/spec` ile başla.
2. **Uygula.** Tam olarak bir özellik. İki değil. "Bir de küçük bir tane" değil.
3. **Doğrula.** Tamamlandı demeden veya commit'lemeden ÖNCE `/verify` (diff'e karşı düşmanca
   tur) çalıştır. `/verify`'dan sıfır-olmayan çıkış tamamlanma iddiasını bloklar.

`IMPLEMENTATION_PLAN.md` ile git log çelişiyorsa git log'a güven. Git append-only'dir; plan
her tur yeniden yazılır.

## Tek-özellik kuralı

Oturum başına bir özellik. Birden çok özellik paketleyen oturumlar hepsini yarım gönderir.
Sıradaki oturum sıradaki özelliği alır. Bir oturumda daha fazla bitirmenin ödülü yoktur;
yarım bırakmanın gerçek bir bedeli vardır.

## Temiz-durum sözleşmesi (her oturum sonu)

- Tüm kod git'e commit'lenmiş. (Bu depoda `settings.local.json`'daki **Stop hook'u** her
  durakta otomatik `git add -A` + commit + push yapar — güvenlik ağı niteliğinde anlık kayıt.)
- `IMPLEMENTATION_PLAN.md` güncel: ne yapıldı, sıradaki ne, bilinen açık sorunlar.
- Başlatılan servisler kapatıldı (ör. Streamlit süreci).
- Bir özellik yalnızca uçtan uca doğrulamadan (`/verify`) sonra "tamamlandı"dır; tek başına
  birim testleri yeterli değildir.

## Şartname & dürüstlük süzgeci (İHLAL EDİLEMEZ — kök CLAUDE.md)

- **Türkçe** — üretilen kod yorumu, doküman, çıktı, sunum Türkçe.
- **Offline-first** — çekirdek akış hiçbir LLM/ağ olmadan tam işlevsel kalır.
- **Held-out bütünlüğü** — `data/raw/*_heldout*` üzerine bakılarak kural/kod düzeltilirse set
  niteliğini kaybeder; `docs/teknik_rapor.md` §5'e yazılmak ZORUNDA.
- **Sahte metrik yok** — `eval_report*.json` elle düzenlenmez; yalnız `scripts/evaluate.py`
  üretir. Ölçülmemiş değer gerçekmiş gibi sunulmaz.
- **Gerçek PII yok** — yalnız sentetik/kurgu veri.

## Skill'ler vs kurallar

- **Skill'ler** (`.claude/skills/*/SKILL.md`) — `description`'daki tetik ifadeyle talep üzerine
  çağrılır. Eşleşen bir görevde önce skill'in SKILL.md'sini oku.

Tam skill yönlendirme tablosu: `.claude/skills/using-loopkit/SKILL.md`.

## Slash-komut giriş noktaları

- `/spec` — icraat öncesi `PROMPT.md` yaz. `--force` olmadan varsa çalışmaz.
- `/verify` — mevcut diff'e karşı düşmanca tur. Sıfır-olmayan çıkış tamamlanmayı bloklar.
- `/polish` — mevcut diff'e altı kalite skill'i.
- `/next` — backlog'a dokunmadan yeni iş önerisi.

## Asla

- Kırmızıyı yeşile çevirmek için test zayıflatma/silme. Test yanlışsa, gerekçesiyle kendi
  commit'inde düzelt.
- `/verify` çalıştırmadan işi tamamlandı işaretleme.
- Held-out set üzerine bakarak kural/kod düzeltip §5'e yazmama.
- Özelliğin kendisi "bağımlılık yükselt" değilken `pip install -U` / bağımlılık yükseltme
  yapma. Yeni bağımlılığı commit gövdesinde gerekçelendirmeden ekleme.
- Çekirdek akışa zorunlu LLM/ağ bağımlılığı ekleyip offline-first'ü bozma.

## Kullanıcı talimatı ile bu dosya çelişince

Kullanıcı talimatı kazanır. Ardından kök `CLAUDE.md` (Anayasa). Bu dosya, aksi söylenmediğinde
geçerli olan varsayılandır.

## Doğrulamadan commit'leme

Yapımcının kafasındaki denetçi kendisiyle her zaman hemfikirdir. `/verify` ayrı, düşmanca bir
turdur. Her kod değişikliği bundan geçer. "Tamamlandı"yı sahteleyen 11 kısayol için
`.claude/skills/adversarial-verify/SKILL.md`.

## Model yönlendirme

`run.sh`, `CLAUDE_EXECUTOR_MODEL` (tur başına işçi çağrısı) ve `CLAUDE_JUDGE_MODEL` (tur başına
`/verify` çağrısı) değişkenlerini okur. Boş = CLI varsayılanı. Ucuz-işçi + sınır-yargıç deseni
için `.claude/skills/model-routing/SKILL.md`.
