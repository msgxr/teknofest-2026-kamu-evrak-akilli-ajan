---
name: structured-output
description: Modelden güvenilir şekilde JSON al. Prompt'lanmış-JSON yerine schema'lı tool_use tercih et, alınırken doğrula, parse başarısızlığında retry yap. Yanıtı downstream kod parse edecekse kullan.
when_to_use: yapılandırılmış veri çıkarma, ajanlar arası devir (handoff), verifier verdict'leri, bir script'in json.loads yapması gereken her şey
---

# Structured Output

Prompt'lanmış JSON — system prompt'ta "JSON olarak yanıtla" — vahşi doğada çağrıların ~%2-8'inde başarısız olur: nesneden önce başıboş düzyazı, trailing comma'lar, escape'lenmemiş tırnaklar, code fence'ler. Bu başarısızlık oranı bir demo için sorun değil ama bin kez çalışan bir loop için ölümcüldür.

## Hiyerarşi — uyan en güçlüsünü kullan

1. **Schema'lı tool use** (en iyi) — girdisi için bir JSON Schema'ya sahip bir tool tanımla. Modeli o tool'u çağırmaya zorla. API, argümanları sen görmeden önce schema'ya karşı doğrular. Bozuk JSON modelden hiç çıkmaz. Downstream gerçek bir parser olduğunda her zaman bunu kullan.

2. **JSON mode / `response_format`** (iyi) — desteklenen yerlerde. En üst seviyede geçerli bir JSON nesnesi garanti eder; schema uyumunu garanti etmez. Prompt'lanmış-JSON'a göre ucuz bir yükseltme.

3. **Katı kurallarla prompt'lanmış JSON** (fallback) — tool use olmayan modeller/tier'lar için. "SADECE JSON nesnesini çıkar, code fence yok, düzyazı yok" de, bir örnek ver ve alınırken doğrula. ~%5 başarısızlık varsay ve bunu ele al.

## validate-and-retry deseni

```
call → parse → if fail: retry once with the parse error appended → parse → if fail: hard fail
```

- **Bir retry, bir loop değil.** Model iki denemede üretemiyorsa, schema fazla karmaşık ya da prompt yanlış. Logla ve dur.
- **Parse hatasını retry'da olduğu gibi (verbatim) geri besle** — model, genel bir "lütfen tekrar dene"den tahmin edemeyeceği belirli sorunları ("expected string at line 3") düzeltir.
- **Asla sessizce coerce etme.** Zorunlu bir alan eksikse, gürültülü şekilde başarısız ol. Auto-default'lar prompt bug'larını gizler.

## Schema tasarımı — düz tut

- **Düz nesneler nested'a yeğdir.** Her nesting seviyesi bir başka hallucinate şansıdır.
- **Free string yerine enum.** `"severity": "high|medium|low"`, `"severity": "..."` değil.
- **Opsiyonel alanlar schema'da açıkça null'a default'lansın.** Modele "bilinmiyorsa çıkar (omit)" deme.
- **Gerekçesiz `additionalProperties: true` yok.** Model alan ekleyebiliyorsa, ekler ve tutarsız olurlar.

## Free JSON ne zaman kabul edilebilir

- Tek scalar alan, düşük riskli (`{"answer": "yes"}`).
- Human-in-the-loop her çıktıyı gözden geçiriyor.
- Atılacak (throwaway) prototip.

Aksi hâlde tool_use kullan.

## Kırmızı bayraklar

- **Bir code fence'ten JSON çıkarmak için regex.** Bir prompt değişikliği uzağında kırılmaya hazırsın. tool_use kullan.
- **Çıplak `try/except: pass` ile `json.loads`.** Sessiz başarısızlık — saatlerce bir downstream nil'i debug edeceksin.
- **Schema bir `oneOf`/`anyOf` duvarı.** Birden çok tool'a böl ve modelin hangisini çağıracağını seçmesine izin ver.
- **Bir hot loop'ta "system prompt'a sadece 'SADECE JSON' ekle".** Zamanın %95'inde çalışır. Sorun da bu.
- **Aynı girdiyle retry'da farklı structured output.** Çıkarım (extraction) görevleri için temperature'ı 0'a ayarla.

## Loopkit'e bitişik (adjacent)

Loopkit'in `adversarial-verify` çıktısı `{"passes": bool, "failures": [...]}` şeklindedir — bu tam olarak bu skill'in resmileştirdiği (formalize) şekildir. Skill'leri kompoze ederken, makine tarafından tüketilen her hop'u tool_use'lu tut.
