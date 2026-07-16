---
name: self-eval-bias
description: Bir ajanın az önce ürettiği işi eleştirel biçimde incelemek yerine kendinden emin bir şekilde övdüğü deseni tespit et ve kes. Aynı-bağlam içinde notlandırma inceleme değildir — rasyonalizasyondur.
when_to_use: onu üreten aynı bağlamda üretilmiş çıktıyı notlandırmak veya kabul etmek üzere, denetçi kararı somut kanıt gösterilmeden yüksek-güvenli olumlu, ayrı bir denetçi persona başlatmaya karşı öz-inceleme arasında karar verme
---

# Öz-Değerlendirme Yanlılığı (Self-Eval Bias)

Az önce bir plan, bir diff veya bir rapor üretmiş bir ajan, onu aynı bağlamda adilce notlandıramaz. Onu yazmayı haklı çıkaran akıl yürütme hâlâ yüklü — her şüphe zaten göndermeden yana çözülmüştü. İncelemesi istendiğinde, aynı bağlam güvenilir biçimde "iyi görünüyor, gönder" döndürür. Bu inceleme değildir. İncelemenin üniformasını giymiş rasyonalizasyondur.

Desen en çok, değerlendiricinin uzun koşularda hoşgörüye kaydığı planner/generator/evaluator mimarilerinde ortaya çıkar — okuduğu prompt'lar generator'ın akıl yürütmesiyle dolar ve şüphecilik aşınır. (Üç-ajan koşumu (three-agent harness) hakkında Prithvi'nin Mart 2026 yazısına bakın: https://blog.anthropic.com/three-agent-harness-march-2026.)

## Ne zaman uygulanır

- Az önce kod, bir plan veya bir iddia yazdın ve sonraki adım "doğru olduğunu teyit et".
- Bir denetçi kararı, gösterilen satır numaraları olmadan, keşfedilmiş başarısız bir vaka olmadan, denenmiş bir karşı örnek olmadan olumlu döner.
- Bir özelliği `passes: true` işaretlemek, bir issue kapatmak veya sonraki oturuma devretmek üzeresin.
- Çok-ajanlı bir döngüdeki değerlendirici persona, son N generator çıktısıyla arka arkaya hemfikir oldu.

## Prosedür

1. **Aynı-bağlam işaretini fark et.** İnceleme kararı üç cümlenin altında gelir ve gösterilen bir artefakt olmadan "doğru görünüyor", "bu çalışmalı" veya "sorun bulunamadı" içeriyorsa — kararı yazılmamış say.
2. **Taze bir persona zorla.** Üretim bağlamını bırak. Yeni bir subagent aç ya da en azından yalnızca artefakt (diff, plan, çıktı) ve kabul kriterleriyle yeniden prompt'la — akıl yürütme izi yok, öz-gerekçelendirme yok.
3. **Karar değil, somut kanıt talep et.** Denetçi şunları göstermeli: incelediği file:line, çalıştırdığı girdi, gözlemlenen çıktı ve karşılaştırdığı kriter. Bunlar olmadan "LGTM" boş bir incelemedir — at gitsin.
4. **Düşmanca yokla.** Denetçiden artefaktın başarısız olduğu en güçlü vakayı iste. Üretemiyorsa, inceleme gerçekleşmedi — denetçi sadece hemfikir oldu.
5. **Artefaktı çalıştır.** Kod için, onu uçtan uca çalıştır (bkz. [[broken-window-check]]). Bir plan için, ilk iki adımı somut olarak yürü. Aynı-bağlam güveni bir çalışma zamanına karşı hızla çöker.
6. **Denetçiyi periyodik olarak döndür.** Uzun çok-ajanlı döngülerde, değerlendiriciyi ~5 sprint'te bir sıfırdan yeniden prompt'la — hoşgörü kayması sessizce birikir.

## Anti-desenler

- **Aynı turda öz-inceleme.** "İşimi bir kez daha kontrol edeyim"i hemen ardından gelen onay izler. Şüphenin gerçek olması için bir bedeli olmalı.
- **Kanıt olarak övgü.** "Bu temiz, iyi yapılandırılmış bir implementasyon" bir hava (vibe)dır, bir bulgu değil. Bulgular satır gösterir.
- **Olumlu karar, boş failure_scenario.** Denetçi bir başarısızlığın nasıl görüneceğini tanımlayamıyorsa, bir tane aramadı demektir.
- **Bir koşu boyunca lastik damga (rubber-stamping).** Aynı değerlendiriciden tek bir ret olmadan gelen N ardışık "onaylandı" kararı bir kırmızı bayraktır, bir sicil değil.
- **Artefakt yerine kriteri düzeltme.** Denetçi bir boşluk fark eder, sonra boşluğun kapsam dışı olduğunu söylemek için spec'i düzenler. Boşluk artefaktta. Onu düzelt.

## Ne zaman UYGULANMAZ

- Çıktı önemsiz ve yanlışsa yeniden yapması ucuz (tek satırlık bir yeniden adlandırma, bir config anahtarı).
- Taze bir bağlama sahip ayrı bir denetçi zaten çalıştı ve somut kanıt gösterdi — kontrol yapıldı, üzerinde döngüye girme.

## İlgili

- [[broken-window-check]] — "son iddiaya güvenme"nin çalışma zamanı güdümlü sürümü.
- [[adversarial-verify]] — "en güçlü başarısızlık vakasını bul"un yapısal biçimi.
- [[shift-notes]] — taze-persona incelemesinin gerçekte ne bulduğunu kaydettiğin yer.
