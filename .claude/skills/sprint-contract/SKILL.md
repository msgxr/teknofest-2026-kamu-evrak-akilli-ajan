---
name: sprint-contract
description: Herhangi bir kod yazılmadan önce "tamamlandı"nın ne anlama geldiğini tanımlayan, generator ve evaluator personaları arasında kod-öncesi bir sözleşme müzakere et. Bulanık spec'leri, değerlendiricinin generator'ı bağlı tutabileceği test edilebilir bir hedefe dönüştürür.
when_to_use: döngüde bir evaluator/reviewer ile tutarlı bir uygulama iş parçasına başlama, planlayıcı çıktısı belirsizken bulanık bir spec'i test edilebilir bir hedefe köprüleme, bir bağlam sıfırlamasından sonra bir oturumu yeniden hidrasyon (rehydrate) edip taze bir kabul hedefine ihtiyaç duyma
---

# Sprint Sözleşmesi

Değerlendiricinin kaldıracı, "tamamlandı" kod var olduktan *sonra* tanımlandığında çöker. Generator bir şey gönderir, değerlendirici onu makul bulur, bulanık spec sessizce inşa edilene uyacak şekilde yeniden şekillenir. Süslenmiş, erken zafer.

Zamanlamayı düzelt: sözleşmeyi, generator tek satır kod yazmadan *önce* yaz. O zaman değerlendiricinin sprint için işi mekaniktir — artefaktı sözleşmeye karşı tut, uçuş ortasında yeniden müzakere yok.

Prithvi'nin çok-ajanlı koşumlar (harnesses) hakkındaki Mart 2026 yazısındaki planner/generator/evaluator ayrımından ilham alınmıştır.

## Ne zaman uygulanır

- Döngüde bir evaluator veya reviewer persona ile bir iş parçasına (bir özellik, bir refactor, bir hata düzeltmesi) başlamak üzeresin.
- Planlayıcı çıktısı veya üst-akış (upstream) spec belirsiz — ikisi de onu "karşılayan" iki makul implementasyon hayal edebilirsin.
- Bir oturum, `shift-notes` / bir ilerleme dosyasından henüz yeniden hidrasyon oldu ve klavyeyi eline almadan önce somut bir kabul hedefine ihtiyaç duyuyor.

## Prosedür

1. **Tek teslimatı adlandır.** Bir özellik, bir cümle, kullanıcı tarafından gözlemlenebilir. Bir cümlede söyleyemiyorsan, sprint çok büyük — böl, ilk dilimi sözleşmeye bağla.
2. **Kabul yüklemlerini (predicates) yaz.** 3-7 madde, her biri ya geçen ya da başarısız olan bir kontrol. "Temiz kod" yok, "iyi UX" yok — bir script'in veya bir tarayıcı tıklamasının karar verebileceği yüklemler yaz.
3. **Çalışma zamanı yolunu adlandır.** Bu uçtan uca nasıl çalıştırılır? Hangi URL, hangi CLI çağrısı, hangi düğme tıklaması? Değerlendirici tam olarak bu yolu sürecek — ikame yok.
4. **Kapsam dışı öğeleri listele.** Generator'ın ayrıca düzeltmeye heves edeceği iki veya üç şey. Yazılı olması = değerlendirici bunları kapsam kayması olarak reddedecek, generator heveslendiğinde bir çapaya sahip olur.
5. **Onu shift notlarında imzala.** Sözleşmeyi, sprint başlangıç zaman damgasıyla birlikte `## Sprint contract` başlığı altında `claude-progress.txt`'e (veya eşdeğerine) yapıştır. Her iki persona da sprint'in geri kalanında tam olarak bu metni referans alır.
6. **Sonra, ve ancak o zaman, kod yaz.**

## Sözleşme şekli

```
## Sprint contract — <ISO timestamp>

Deliverable: <one sentence, user-observable>

Acceptance predicates:
- [ ] <predicate 1 — script-decidable>
- [ ] <predicate 2>
- [ ] <predicate 3>

Runtime path: <exact URL / CLI / click sequence the evaluator will drive>

Out of scope this sprint:
- <tempting adjacent fix>
- <tempting refactor>
```

## Anti-desenler

- **Kontrol değil, düz metin olan yüklemler.** "Hataları zarifçe ele alır" bir yüklem değildir. "`name` yokken `{error: "missing_field"}` ile 400 döndürür" yüklemdir.
- **Sprint ortasında yeniden müzakere.** Generator bir duvara toslarsa, etrafından dolaşmak için sözleşmeyi düzenlemez. Duvarı gün yüzüne çıkarır, *planlayıcı* kapsamı revize eder, yeni bir sözleşme imzalanır. Değerlendirici hoşgörüsü uçuş-ortası düzenlemelerden gelir — onları yapısal olarak blokla.
- **Yalnızca generator tarafından yazılan sözleşme.** Generator, planladığı kodun tesadüfen karşıladığı yüklemler yazacaktır. Kod başlamadan önce değerlendiriciye taslak hazırlat ya da en azından onaylat.
- **Çalışma zamanı yolu yok.** Onsuz, değerlendirici birim testleri okumaya geri döner — bunun nasıl başarısız olduğu için bkz. [[broken-window-check]].
- **Kapsam dışı listesini atlama.** Bu, elindeki en ucuz sapma-önleyici (anti-drift) araçtır. Onu atla ve iki başka özelliği bozan bir "küçük refactor" göndereceksin.

## Yeniden hidrasyon (rehydration) durumu

Taze oturum, öncekinin hiçbir hatırası yok. `shift-notes`'u oku, işaretlenmemiş yüklemleri olan son imzalanmış sözleşmeyi bul. Hedefin odur — yeniden planlama yok, yeniden yorumlama yok. Çalışma zamanı yolunu sür, yüklemleri işaretle, gönder. İnceleme sonucu sözleşme yanlış görünüyorsa, onu düzenleme; planlayıcıya geri dön, yenisini imzalat.

## Maliyet

Koddan önce iki ila beş dakikalık düz metin. Karşılığında: değerlendiricinin katı olacağı bir şey olur, generator'ın kapsam kaymasına karşı bir çapası olur ve sonraki oturum bir hava (vibe) yerine test edilebilir bir hedef devralır.

## İlgili

- [[shift-notes]] — sözleşmenin oturumlar boyunca yaşadığı yer.
- [[broken-window-check]] — değerlendiricinin oturum başlangıcında sözleşmeye *karşı* çalıştırdığı şey.
- [[adversarial-verify]] — her yüklemin gerçekten geçerli olup olmadığına karar veren sprint-sonu tur.

## Ne zaman UYGULANMAZ

Önemsiz düzenlemeler (yazım hatası düzeltmesi, tek satırlık config değişikliği, bağımlılık yükseltme) — sözleşme yükü işi aşar. Döngüde değerlendirici persona olmayan tek başına koşular — bunun yerine kendine tek satırlık bir kabul notu yaz ve devam et.
