---
name: eval-harness
description: Ajan çıktısını bir LLM yargıçla (judge) notlandıran tekrarlanabilir bir eval döngüsü kur, böylece prompt/skill değişiklikleri gözle bakılıp geçilmek yerine bir temele (baseline) karşı skorlansın. Notlandırıcı (grader) olarak loopkit'in verifier subagent'ını yeniden kullan — yenisini kurma.
when_to_use: bir prompt'u ayarlama, bir skill'i değiştirme, iki modeli karşılaştırma, bir iş akışını (workflow) regresyon-testi yapma, "bu gerçekten daha mı iyi çalışıyor?"
---

# Eval Harness

Uzun süre çalışan bir ajandaki her prompt ince ayarı, o anda bir iyileştirme gibi görünür. Bilmenin tek yolu, sabit girdilere karşı notlandırılmış (graded) bir koşudur. Loopkit zaten `.claude/agents/verifier.md` ile geliyor — notlandırıcın (grader) odur. Yeniden inşa etme.

## Üç-aşamalı döngü

```
inputs.jsonl  →  runner  →  outputs.jsonl  →  verifier (per row)  →  verdicts.jsonl  →  diff vs baseline
```

Her aşama diske yazar. Hiçbir aşama tüm koşuyu bağlamda tutmaz.

## Aşama 1 — inputs.jsonl

Satır başına bir JSON nesnesi: `{"id": "case-01", "input": "...", "expected": "..."}`.

- 20-100 vaka bir sinyal için yeterlidir. Daha fazlası hoştur, zorunlu değil.
- Bilinen-zor vakaları, uç (edge) vakaları ve akıl-sağlığı çıpası (sanity anchor) olarak birkaç önemsiz (trivial) vaka ekle.
- Dosyayı dondur. Değiştirdiğinde eval'i bir sonek (suffix) ile revizyonla (`inputs-v2.jsonl`). Asla yerinde düzenleme — temeli (baseline) kaybedersin.

## Aşama 2 — runner

Aptal bir döngü: her satır için modeli mevcut prompt/skill ile çağır, çıktıyı yakala, `{"id": ..., "output": ...}`'ı `outputs.jsonl`'e yaz. Burada notlandırma yok — yalnızca yakalama.

- Her koşuda aynı sıcaklık (temperature) (eval'ler için genelde 0).
- Aynı tohum (seed) / model sürümü.
- Test edilen prompt/skill'in git SHA'sını dosya başlığına (header) logla.

Runner akıllıysa eval'i yanlı (bias) hale getirir. Aptal tut.

## Aşama 3 — verifier

Satır başına bir subagent'e dağıt (fan out) (bkz. `subagent-fanout`). Her biri şunu alır:
- Girdi.
- Beklenen çıktı (ya da şartname).
- Gerçek çıktı.
- `.claude/agents/verifier.md`'deki verifier sistem prompt'u.

Verifier katı JSON döndürür: `{"pass": bool, "why": "..."}`. `verdicts.jsonl`'de topla.

## Diff vs baseline

Aynı eval'in iki prompt sürümü üzerindeki iki koşusu → vaka başına geçme oranlarını karşılaştır. Önemli olan:

- **Genel geçme oranı (pass rate)** — manşet (headline).
- **Regresyonlar** — yeşilken kırmızıya dönen vakalar. Bunlar göndermeyi (ship) bloklar.
- **Yeni geçmeler** — kırmızıyken yeşile dönen vakalar. Bunlar göndermeyi gerekçelendirir.
- **Çırpınan (flappy) vakalar** — yeniden koşular arasında tutarsız. Araştır; gerçek model belirsizliği (nondeterminism) ya da kötü bir vaka olabilir.

Ortalamayı yükselten ama regresyon ekleyen bir değişiklik genelde bir kayıptır — yeni başarısızlıklar, zaten çalıştığını bildiğin vakalardır.

## Kırmızı bayraklar (Red flags)

- **Notlandırıcı, çıktıyı üreten modelle aynı, aynı prompt ile.** Kendi-kendini-notlandırma (self-grading) hoşgörülüdür. En azından farklı bir persona; ideali farklı bir model kademesi (tier) kullan.
- **Eval ilk gün %100 geçiyor.** Vakalar çok kolay ya da notlandırıcı bir lastik damga (rubber stamp). Düşmanca (adversarial) vakalar ekle.
- **Eval 30 dakikadan uzun sürüyor.** Dağıt (fan out). Seri 100-vakalık bir eval, seri 100-vakalık bir darboğazdır (bottleneck).
- **Notlandırıcı test edilen prompt'unu görüyor.** Ne olduğunu değil, ne istediğini notlandırır. Ona yalnızca şartname (spec) + girdi + çıktı ver.
- **Temel (baseline) kayboldu.** Temel olmadan "iyileşme" havadan (vibes) ibarettir. `verdicts.jsonl`'i git'e commit'le.

## Ne zaman yapılmaz

- Tek-seferlik betik — harness değil, bir kontrol listesi (checklist) kur.
- Günlük değişen ve oturmayacak (won't stabilize) prompt — eval'ler sabit bir hedefe ihtiyaç duyar.
- "Doğru"nun kontrol edilebilir olmadığı görev (açık uçlu yaratıcı yazım) — geçti/kaldı değil, insan eval'i ya da rubrik-tabanlı bir notlandırıcı kullan.

Verifier zaten senin. Harness, onun etrafındaki 100 satır yapıştırıcıdır (glue).