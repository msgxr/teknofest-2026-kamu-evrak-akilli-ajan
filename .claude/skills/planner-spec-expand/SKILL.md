---
name: planner-spec-expand
description: 1-4 cümlelik bir ürün özetini (brief); bir tasarım dili, kabul yüzeyi ve sıralı bir özellik listesi içeren tam bir spec'e genişlet.
when_to_use: Herhangi bir generator ajan çalışmadan önce tek satırlık bir prompt'tan bir projeyi başlatma, kapsam kayması hedefi değiştirdikten sonra yeniden planlama, feature-list-json'ın tohumlanacağı girdi belgesini üretme
---

# Planlayıcı Spec Genişletme

Tek satırlık bir özet ("bir claude.ai klonu inşa et", "seri (streak) takipli bir alışkanlık takipçisi") bir kodlama ajanının iyi kararlar vermesi için yeterli yüzey değildir. Tasarım dili yok, kabul kriteri yok, sıralama yok. Generator sonunda oturum ortasında kapsam uydurur ve tutarsız dilimler gönderir.

Planlayıcının işi, özeti; her alt-akış kararının — hangi özelliğin seçileceği, "tamamlandı"nın neye benzediği, düğmenin ne yazması gerektiği — halihazırda yazılı bir cevabının olacağı kadar yoğun bir spec'e genişletmektir. Altta yatan mimari için Prithvi'nin planner/generator/evaluator ayrımı hakkındaki yazısına bakın: https://www.prithvirajrk.com/blog/three-agent-harness.

## Ne zaman uygulanır

- Kullanıcı sana ~200 kelimenin altında bir özet verdi ve gerçek bir ürün bekliyor.
- [[feature-list-json]]'ı tohumlamak üzeresin ve özetin henüz sıralanabilir özelliği yok.
- Proje ortasında kapsam kaydı ve orijinal spec artık hedefi tanımlamıyor — yeniden yaz, yamama.

## Prosedür — bu sırayla genişlet

Bölümleri sırayla yap. Sonraki bölümler öncekilerin kilitlenmiş olmasına bağlıdır.

1. **Özeti tek paragrafta yeniden ifade et.** Kendi sözlerinle, ne inşa ediliyor ve kimin için. Bunu temiz yazamıyorsan, devam etmeden önce kullanıcıya sor — özet yetersiz tanımlanmış.
2. **Bir tasarım dili seç.** Her biri tek cümle: görsel ton (minimal / yoğun / oyuncu), tipografi duruşu (tek sans / serif+sans / mono vurgular), renk duruşu (monokrom + tek vurgu / iki-renk / tam palet), yoğunluk (havadar / kompakt). Bu, sonraki bin mikro-kararı kilitler.
3. **Kabul yüzeyini numaralandır.** Kullanıcı tarafından gözlemlenebilir her yetenek için, kullanıcı tarafından gözlemlenebilir davranışın tek cümlesini VE bir insanın onu doğrulamak için atacağı somut adımları yaz. Bu, [[feature-list-json]]'ın istediği şekildir — şimdi o şekilde yaz.
4. **Özellikleri sırala.** Bağımlılığa göre sırala: hiçbir şey bağımlı olduğu şeyden önce görünmez. Beraberlikler "kullanıcı uygulamayı açtığında ilk neyi görür" ile bozulur. Listenin en üstü tek başına çalıştırılabilir olmalı.
5. **Kapsam dışını adlandır.** Özetin ima edebileceği ama açıkça inşa etmediğin şeylerin kısa bir listesi. Generator'ın başıboş dolaşmasını önler.
6. **Duman yolunu (smoke path) yaz.** Ürünün var olduğunu kanıtlayan tek kullanıcı yolculuğu — uçtan uca 3-6 adım. Bu, başlatıcının duman testi (smoke test) olur.

## Devretmeden önce kontrol listesi

- Her özellik, [[feature-list-json]]'ın beklediği şekilde `description` + `steps` içerir.
- İlk 3 özellik, ileri bağımlılık olmadan sırayla inşa edilebilir.
- Tasarım dili tek ekrana sığar — bir sayfaysa, aşırı tanımlamışsın.
- Kapsam dışı listesi boş değil. Her şey kapsam içindeyse, planlamamışsın, kopya çekmişsin (transcribe).
- Duman yolu çekirdek değer önerisine (value prop) dokunur, auth veya ayarlara değil.

## Anti-desenler

- **Kapsamlı görünmek için özellik listesini şişirme.** 40 gerçek özellik, 200 sahtesini yener. Generator hepsini inşa edecek.
- **Şemayı tasarlama.** O generator'ın işi. Sen kullanıcı tarafından gözlemlenebilir davranışı tanımlarsın; generator veri modelini seçer.
- **Adım yazman gereken yerde düz metin yazma.** "Kullanıcı konuşmaları yönetebilir" bir özellik değildir. "Kenar çubuğu öğesindeki çöp kutusu ikonuna tıklamak o konuşmayı siler ve kenar çubuğundan kaldırır" özelliktir.
- **Önceliği örtük bırakma.** İki özellik beraberse, beraberliği şimdi boz. Generator bozmayacak.

## Ne zaman UYGULANMAZ

Halihazırda kabul-kriteri derinliğinde tanımlanmış özetler için ya da mevcut bir projeye tek-özellik düzenlemeleri için bunu atla — bunun yerine [[shift-notes]] kullan ve mevcut [[feature-list-json]]'dan seç.

İlgili: [[feature-list-json]], [[shift-notes]], [[broken-window-check]].
