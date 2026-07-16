---
name: active-memory-reminder
description: Sıkıştırma (compaction) öncesinde Loopkit, kararları claude-decisions.json içine çıkarır (makine-okunur). Oturum başında onu claude-progress.txt ile birlikte oku — düz metin (prose) insanlar içindir, JSON döngü içindir.
when_to_use: oturum başı, /clear sonrası, sıkıştırma (compaction) sonrası — koda dokunmadan önce; önceki bir oturumdan gelen bir karar, yapmak üzere olduğun şey için belirleyici (load-bearing) olduğunda
---

# Aktif Hafıza Hatırlatıcısı

Loopkit, shift-notes'u bilinçli olarak iki dosyaya böler:

- **`claude-progress.txt`** — serbest biçimli düz metin (prose). Son oturumun ne yaptığına, neyin uçuşta olduğuna, sırada neyin ele alınacağına dair insan-okunur bir anlatı. Bağlam ve niyet için üstündür. Model bir kararın verilip verilmediğine *karar vermek* zorunda kaldığında zayıf kalır.
- **`claude-decisions.json`** — `{ts, decision}` girdilerinden oluşan makine-okunur bir dizi; transkript her sıkıştırılmak üzereyken loopkit `pre-compact` hook'u tarafından eklenir. Belirli seçimlerin kalıcılığı için üstündür ("SQLite yerine Postgres seçildi çünkü…", "polling yaklaşımı reddedildi", "htmx denendi ve Alpine'a geçildi").

Muhakemenin (reasoning) öldüğü yer sıkıştırmadır. Özetleyici, işin biçimini korur ama *neden*ini söküp atar. `claude-decisions.json`, bunu atlatan kalıcı yan-kanaldır (side-channel). Bu, Meta'nın NapMem makalesinin uzun-ömürlü ajanlarda davranışsal-durum-bozunması (behavioral-state-decay) için işaret ettiği desenin aynısıdır: düz metin, yapılandırılmış gerçeklerden daha hızlı bozunur çünkü model düz metni serbestçe yeniden yazar, yapılandırılmış veriyi ise dikkatle düzenler (loopkit'in `feature_list.json` için JSON kullanmasının nedeni de budur; bkz. [[feature-list-json]]).

## Ne zaman uygulanmalı

- **Oturum başı / /clear sonrası / sıkıştırma sonrası.** `claude-decisions.json`'ı, `claude-progress.txt`'nin hemen ardından ve koda bakmadan önce oku. İki dosya çelişiyorsa, JSON belirli bir seçimin daha yeni ve sert kaydıdır; düz metin sana nedenini verir.
- **Bir tasarım seçimini yeniden tartışmaya açmadan önce.** "Y yerine X kullanalım" önermek üzereysen, önce `claude-decisions.json`'ı grep'le. Önceki bir oturum X'i zaten reddetmiş ve yazmışsa, bunu yeniden türetmek için token bütçesini yakma.
- **Yarım kalmış uygulama işini devraldığında.** Kararlar, ilerleme dosyasının yeniden ifade etmeyebileceği kısıtları çerçeveler.

## Dosya sözleşmesi

`claude-decisions.json` bir JSON dizisidir. Her girdi `{ts, decision}`'dır:

```json
[
  {"ts": "2026-07-14T18:22:09Z", "decision": "chose Playwright MCP over Puppeteer because Puppeteer's alert-modal blind spot bit us in run 41"},
  {"ts": "2026-07-14T20:04:11Z", "decision": "rejected the daemon-per-project approach; switched to a single supervisor with per-project subdirs"},
  {"ts": "2026-07-15T09:31:44Z", "decision": "tried and failed to cache the plan across sessions — plan went stale within two sessions, dropped"}
]
```

Kısıtlar:
- Normal işleyişte yalnızca ekleme (append-only). `pre-compact` hook'u ekler; oturumlar okur.
- Hook'un yakalamayacağı bir kararı oturum ortasında verirsen (ör. düz metinde değil, kodda verilen bir karar) elle EKLEYEBİLİRSİN. Aynı biçimi kullan. Mevcut girdileri yeniden yazma veya silme — onlar kalıcı kayıttır.
- Girdiler çelişirse yeni olan kazanır, ancak nedenin kayda geçmesi için çelişkiyi `claude-progress.txt`'ye not düş.

## Hook

`.claude/hooks/pre-compact`, hem manuel (`/compact`) hem de otomatik sıkıştırmada çalışır. Transkripti `decided|chose|rejected|tried and failed|switched from .* to|going with|not going to` ile eşleşen ifadeler için tarar, tekrarları ayıklar (dedupe), sıkıştırma başına 20 ile sınırlar, her birine zaman damgası basar ve ekler. Sessiz-güvenlidir (silent-safe): herhangi bir hata stderr'e loglanır ve 0 ile çıkar, böylece sıkıştırma asla bloklanmaz.

## Anti-desenler

- **`claude-progress.txt`'yi okuyup `claude-decisions.json`'ı atlamak.** Kapanmış soruları yeniden açarsın. Düz metin dosyası çoğu zaman *öbür şeyi neden yapmadığımızı* atlar — JSON tam da bunun içindir.
- **Geçmiş kararları "temizlemek" için düzenlemek veya silmek.** `feature_list.json` adımları ve açıklamalarıyla aynı kural: kalıcı yapılandırılmış kayıtlar belirleyicidir (load-bearing). Onları yeni bir girdide çürüt; eskisini silme.
- **`claude-decisions.json` içinde düz metin saklamak.** O, ikinci bir ilerleme dosyası değildir. Girdiler, zaman damgalı tek kararlardır, başka hiçbir şey değil.
- **Hook'un yakaladığını varsaymak.** regex çoğu kararı yakalar ama hepsini değil. Transkriptin bariz biçimde eşleştirmeyeceği bir karar verdiysen, oturumu bitirmeden önce elle ekle.

## İlgili

- [[progress-reading-protocol]] — oturum-açılış sırası; adım 2b bu dosyayı okur.
- [[feature-list-json]] — loopkit'in dayandığı, düz-metin-yerine-yapılandırma diğer dosyası.
- [[shift-notes]] — bu dosyanın eşleştiği düz metin muadili.
- [[clean-state-contract]] — bu eşleşmeyi kullanılabilir tutan oturum-sonu disiplini.
