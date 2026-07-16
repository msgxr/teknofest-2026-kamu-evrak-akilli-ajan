---
name: evaluator-calibration
description: Şüpheciliğin tutarlı kalması ve uzun koşularda hoşgörülüye (lenient) kaymaması için, bir inceleyici (reviewer) personasını az-atışlı (few-shot) rubrik örnekleriyle kalibre et.
when_to_use: çok-ajanlı bir harness için bir değerlendirici/eleştirmen (evaluator/critic) ajanı ayağa kaldırma, değerlendirici skorlarının birçok iterasyon boyunca yukarı kaydığını fark etme, skill/PR/diff çıktısını bir LLM ile notlandırıp (grade) tekrarlanabilir kararlar (verdict) isteme
---

# Değerlendirici Kalibrasyonu (Evaluator Calibration)

Üreticinin (generator) gerekçesini okuyan bir değerlendirici (evaluator) ajanı hoşgörülüye (lenient) kayar. Üretici, kodun neden iyi olduğunu açıklar; değerlendirici, o düz metne (prose) önlem alarak (priming) baş sallamaya başlar. 8. sprint'e gelindiğinde "şüpheci eleştirmen" bir lastik damgadır (rubber stamp). Prithvi bunu Mart 2026 planlayıcı/üretici/değerlendirici yazısında işaretledi — değerlendirici hoşgörüsü, üç-ajanlı harness'ın başarısızlık modudur.

Çözüm "değerlendiriciye daha katı ol de" değildir. Bu, bir iterasyon için işe yarar. Çözüm, **rubriği, değerlendiricinin her çağrımda yeniden okuduğu somut geçti/kaldı (pass/fail) örnekleriyle demirlemek** ve **sabit bir kadansda sıfırdan yeniden-prompt'lamak**, böylece kaymanın (drift) birikememesidir.

## Ne zaman uygulanır

- Çok-ajanlı bir döngüde bir eleştirmen/değerlendirici/yargıç (critic/evaluator/judge) ajanı kuruyorsun.
- Skill'ler, PR'lar, diff'ler ya da ajan çıktısı için notlandırıcı (grader) olarak bir LLM kullanıyorsun.
- Çıktı kalitesi değişmediği halde — ya da daha kötüsü, düştüğü halde — geçme oranlarının (pass rate) yukarı süründüğünü fark ettin.
- Aynı değerlendiricinin aynı artefakt üzerindeki iki koşusunun aynı kararı döndürmesini istiyorsun.

## Prosedür

1. **Rubriği düz metin değil, skorlanmış bir kontrol listesi (checklist) olarak yaz.** Her kriter bir ad, tek-satırlık bir tanım ve ikili (binary) ya da 1-3 skor alır. Düz metin rubrikler ("kodun iyi tasarlanıp tasarlanmadığını değerlendir") kayar; kontrol listeleri kaymaz.

2. **Her kriteri 2 somut örnekle demirle — biri geçti, biri kaldı.** Uydurma değil, önceki koşulardan gerçek örnekler. Değerlendirici bunları her çağrımda okur. Kalibrasyon budur; bu olmadan yalnızca umudu prompt'luyorsun.

3. **Skorlamadan önce üreticinin gerekçesini okumayı yasakla.** Değerlendirici artefaktı (kod, diff, çıktı) ve rubriği görür. Üreticinin "işte bunun neden iyi olduğu" düz metnini görmez. Önce skorla, sonra isteğe bağlı olarak eleştiriyi (critique) yazmak için gerekçeyi oku.

4. **Değerlendiricinin her kararda artefaktı alıntılamasını (quote) zorunlu kıl.** "Kriter 3'ten kaldı çünkü <alıntılanmış satır>" — "kriter 3'ten kaldı" değil. Alıntı, temellendirmeyi (grounding) zorlar ve kararı denetlenebilir (auditable) kılar.

5. **Her N iterasyonda sıfırdan yeniden-prompt'la.** Ampirik olarak N=5 işe yarar. Değerlendiricinin bağlamını öldür, sistem prompt'unu + rubriği + örnekleri taze yeniden yükle. Sıkıştırma (compact) yapma; sıkıştırma kaymayı korur.

6. **Karar dağılımlarını logla.** Sprint başına kriter başına geçme oranını takip et. Şartname (spec) değişikliği olmadan %40 geçmeden %90 geçmeye giden bir kriter, iyileşme değil, kaymadır (drift).

7. **Tutulmuş (held-out) bir kaldı örneğiyle nokta-kontrolü (spot-check) yap.** Her ~10 sprint'te, örnek setinden kaldığını bildiğin bir artefaktı değerlendiriciye ver. Geçerse, kalibrasyon çürümüştür (decayed) — örnek setini yakın gerçek koşulardan yeniden üret.

## Anti-desenler (Anti-patterns)

- **Sistem prompt'unda örneksiz "şüpheci ol".** Kelimeler kalibre etmez. Örnekler kalibre eder.
- **Değerlendiricinin planlayıcının (planner) planını okumasına izin verme.** Üreticinin gerekçesini okumakla aynı kayma mekanizması — niyete (intent) önlem almak (priming) eleştiriyi yumuşatır.
- **Birçok notlandırma boyunca tek bir paylaşılan bağlam.** Her notlandırma temiz bir rubrik okumasıyla başlamalı. Tek bağlamda toplu-notlandırma (batch-grading), hoşgörünün en hızlı biriktiği yerdir.
- **Uydurma örnekler.** Sahte geçti/kaldı örnekleri, değerlendiricinin gerçekte gördüğü artefakt dağılımına demirlemez. Gerçek koşulardan çek.
- **1-10 ölçeğinde skorlama.** Değerlendirici 7'de kümelenir. İkili (binary) ya da 1-3 kullan.

## İlgili

- [[adversarial-verify]] — tek-atışlık (single-shot) biçim; evaluator-calibration ise duran-ajan (standing-agent) biçimidir.
- [[shift-notes]] — değerlendirici kararları deftere aittir ki kayma oturumdan oturuma görünür olsun.
- [[broken-window-check]] — "son karara güvenme"nin mekanik bir sürümü; güvensizlik duyulan şey değerlendiricinin kendisi olduğunda iyi eşleşir.

## Ne zaman uygulanmaz

Her çağrıda taze bağlamla tek-atışlık notlandırma — önlenecek bir kayma yoktur ve örnekler ek yüktür (overhead). Ayrıca değerlendiricinin yalnızca 2-3 kez çalıştığı ~1 saatin altındaki görevler için de atla.