# Loopkit Döngü Sistemi — Kurulum ve Kullanım

Bu depoya [loopkit](https://github.com/Archive228/loopkit) döngü sistemi (Planla → Uygula →
Doğrula) uyarlanarak kuruldu. Bu belge, neyin nereye kurulduğunu, projeye özgü uyarlamaları
ve opsiyonel hook'ların nasıl etkinleştirileceğini anlatır.

## Loopkit nedir?

Coding ajanları için minimal, dosya-tabanlı bir "harness" (çerçeve) + skill kütüphanesi.
İki yapısal başarısızlığı hedefler: (1) aynı anda çok şey denemek, (2) erken "tamamlandı"
ilan etmek. Çözüm: her oturum **tek özellik**, ve tamamlandı demeden önce **düşmanca
doğrulama** (`/verify`). Çalışan bir daemon yoktur; durum diskte tutulur (`PROMPT.md`,
`IMPLEMENTATION_PLAN.md`).

## Kurulan dosya haritası

```
.claude/
├── CLAUDE.md                     # Claude'a özgü loopkit notları (AGENTS.md + skill routing içe aktarır)
├── settings.json                 # İzin listesi (allow/deny). Otomatik-çalışan hook YOK.
├── settings.local.json           # (MEVCUT — korundu) oto-commit+push Stop hook'u
├── agents/
│   └── verifier.md               # Düşmanca denetçi subagent (haiku, JSON çıktı, Türkçe)
├── commands/
│   ├── spec.md                   # /spec  — icraat öncesi PROMPT.md yaz
│   ├── verify.md                 # /verify — diff'e karşı düşmanca doğrulama
│   ├── polish.md                 # /polish — 6 kalite skill'i tek turda
│   └── next.md                   # /next  — backlog'a dokunmadan öneri
├── hooks/
│   ├── format_edited.py          # (OPSİYONEL) ruff format — elle bağlanır
│   └── pre_compact.py            # (OPSİYONEL) karar kaydı — elle bağlanır
├── templates/
│   ├── PROMPT.md                 # /spec şablonu
│   └── IMPLEMENTATION_PLAN.md    # /spec şablonu
├── docs/checklists/              # definition-of-done, rationalizations, red-flags
└── skills/                       # 53 skill (10 track) — İngilizce referans kütüphanesi

AGENTS.md            # Çapraz-ajan döngü sözleşmesi (Türkçe, projeye uyarlı)
run.sh               # Döngü sürücüsü (bash; Windows'ta: bash run.sh)
MEMORY.md            # Loopkit döngü hafızası (oto-hafızadan ayrı)
.mcp.json.ornek      # OPSİYONEL MCP sunucuları (offline-first: pasif)
```

## Projeye özgü uyarlamalar (loopkit orijinalinden farklar)

| Konu | Orijinal loopkit | Bu depodaki uyarlama | Neden |
|---|---|---|---|
| Dil | İngilizce | Glue dosyaları (CLAUDE/AGENTS/komutlar/döküman) **Türkçe** | Şartname: Türkçe zorunlu. Skill'ler İngilizce kaldı (battle-tested referans kütüphane). |
| Biçimlendirici | `prettier` (JS) | `ruff format` (`format_edited.py`) | Proje Python. |
| Karar kaydı hook'u | bash + `jq` | Python portu (`pre_compact.py`) | Bu makinede `jq` yok. |
| SessionStart enjeksiyonu | çalıştırılabilir hook | `.claude/CLAUDE.md` + kök `CLAUDE.md` içine **statik** routing | Otomatik-çalışan enjeksiyon hook'u güvenlik gereği kurulmadı; aynı hedefe native yükleme ile ulaşıldı. |
| Commit/push | "insan push yapar" | Depodaki **oto-commit+push** Stop hook'u korundu | Depo konvansiyonu. |
| MCP (github/context7) | `.mcp.json` aktif | `.mcp.json.ornek` (pasif) | Offline-first: zorunlu ağ bağımlılığı yok. |

## Günlük kullanım (döngü)

1. **Planla** — Karmaşık bir iş için `/spec` çalıştır. `PROMPT.md` (hedef + "tamamlandı
   sayılır" + "asla dokunma" + "şu durumda dur") ve `IMPLEMENTATION_PLAN.md` üretir.
2. **Uygula** — Tek özellik uygula. Kod yaz, `pytest tests/` çalıştır.
3. **Doğrula** — `/verify` çalıştır. Diff "bozuk" varsayılır; 11 kısayol + projeye özgü
   kırmızı bayraklar (Türkçe/held-out/sahte-metrik/offline/PII) taranır ve `verifier`
   subagent'ı soğuk-bağlam ikinci tur yapar. `passes:false` ise commit yok.
4. **Cila (ops.)** — `/polish` ile mevcut diff'e 6 kalite skill'i uygula.

Otomatik döngü (isteğe bağlı, dikkatli kullan — iç içe ajan oturumları açar):
```bash
bash run.sh                       # PROMPT.md + IMPLEMENTATION_PLAN.md gerektirir
CLAUDE_JUDGE_MODEL=haiku bash run.sh   # yargıç turunu ucuz modele yönlendir
```

## Opsiyonel hook'ları etkinleştirme (kullanıcı kararı)

Otomatik-çalışan kod olduğu için, aşağıdaki iki hook `settings.json`'a **elle** eklenmedikçe
pasiftir. Etkinleştirmek istersen `.claude/settings.json` içindeki `permissions` bloğunun
yanına şu `hooks` bloğunu ekle (mutlak yolları kendi ortamına göre koru):

```jsonc
"hooks": {
  "PostToolUse": [
    {
      "matcher": "Edit|Write",
      "hooks": [
        { "type": "command", "shell": "bash",
          "command": "python \"c:/Users/muham/Projects/teknofest-2026-kamu-evrak-akilli-ajan/.claude/hooks/format_edited.py\"" }
      ]
    }
  ],
  "PreCompact": [
    {
      "matcher": "manual|auto",
      "hooks": [
        { "type": "command", "shell": "bash",
          "command": "python \"c:/Users/muham/Projects/teknofest-2026-kamu-evrak-akilli-ajan/.claude/hooks/pre_compact.py\"" }
      ]
    }
  ]
}
```

- **PostToolUse (format_edited.py)** — her Edit/Write sonrası, düzenlenen `.py` dosyasını
  `ruff format` ile biçimler (yalnız o dosya; ruff yoksa no-op). "Okunabilir diff" ilkesi.
- **PreCompact (pre_compact.py)** — bağlam sıkışmadan önce transcript'ten karar cümlelerini
  çıkarıp `claude-decisions.json`'a ekler.

> `settings.json` içindeki hook'lar `settings.local.json`'daki oto-commit Stop hook'u ile
> **birlikte** çalışır (Claude Code hook dizilerini olay bazında birleştirir).

## Skill kütüphanesi (53 skill, 10 track)

`ls .claude/skills/` ile listelenir. Öne çıkanlar: `spec-first`, `adversarial-verify`,
`verification-before-completion`, `systematic-debugging`, `simplify`, `reduce-nesting`,
`kill-dead-code`, `owasp-review`, `write-failing-test-first`, `clean-commits`. Yönlendirme
tablosu: `.claude/skills/using-loopkit/SKILL.md`.

## Güncelleme

Kaynak depo: https://github.com/Archive228/loopkit — yeni skill'ler eklendiğinde ilgili
`skills/<ad>/SKILL.md` dosyaları `.claude/skills/` altına kopyalanabilir. Glue dosyaları
(Türkçe uyarlamalar) elle sürdürülür.

## Lisans notu

Loopkit MIT lisanslıdır; bu depo Apache 2.0. Uyumlu (MIT → Apache 2.0 içine dahil edilebilir);
skill dosyaları türev olarak Türkçeleştirilirse kaynak atfı korunmalıdır.
