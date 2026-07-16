---
name: progress-reading-protocol
description: Herhangi bir yeni işe dokunmadan önce sabit 6-adımlı oturum-açılış dizisini çalıştır — pwd, ilerlemeyi oku, git log, kalan özellikleri say, init.sh, son özelliği duman-testi. Temiz-bağlam (fresh-context) oturumlarının proje durumunu bir dakikanın altında yeniden kurmasını sağlayan yönelim (orientation) ritüeli.
when_to_use: herhangi bir temiz-bağlam kodlama-ajanı oturumunun ilk araç çağrıları, proje ortasında bir bağlam sıfırlaması ya da çökme sonrası yeniden nemlendirme (rehydrate), yeni işe geçmeden önce gönderildiği iddia edilen bir özelliği doğrulama
---

# İlerleme-Okuma Protokolü (Progress-Reading Protocol)

Önceki oturuma dair hafızan yok. Depoda (repo) var. Sabit bir açılış dizisi izlemedikçe her yeni oturum, durumu yeniden kurmak için 5-10 dakika yakar — dizi ile bu, 30-60 saniyeye düşer. Maliyet, her oturumun başında 2-4k token'dır; getiri (payoff), aynı proje üzerinde dört oturumu geçince ödemesini yapar (crosses over).

Adımları atlamak, başarısızlık modudur. Duman-testi adımını (6) atlayan oturumlar, güvenilir biçimde yeni özellikleri sessizce bozuk olanların üzerine inşa eder. Bkz. "gönderilmiş görünüyor, gönderilmemiş" (looks shipped, isn't shipped) hatası (aslen vardiya-işi harness deseninde belgelenmiştir).

## Ne zaman uygulanır

- Çok-oturumlu bir projedeki herhangi bir kodlama-ajanı oturumunun ilk araç çağrıları.
- Bir bağlam sıfırlaması, sıkıştırma (compaction) ya da proje ortasında çökme sonrası — devam ettirilen bağlamı yeni bir oturum gibi ele al.
- Tek satır yeni kod yazmadan önce. "Hızlı düzeltmeler" için istisna yok.

## Prosedür — sırayla çalıştır, atlama yok

1. **`pwd`** — proje dizininde olduğunu doğrula. Yalnızca bu yolun altındaki dosyaları düzenleyebilirsin.
2. **`claude-progress.txt`'i oku** (ya da projenin shift-notes dosyası her ne adlanıyorsa). Bu, önceki oturumun düz metin (prose) devir teslimidir.
2b. **`claude-decisions.json`'ı oku** — loopkit `pre-compact` hook'unun her sıkıştırmadan önce çıkardığı, makine-okunabilir karar defteri. `claude-progress.txt` içindeki düz metin sana son oturumun *ne yaptığını* söyler; `claude-decisions.json` içindeki JSON sana *neyin seçilip neyin reddedildiğini* söyler. İkisi belirli bir seçimde çelişirse, kalıcı kayıt JSON'dur. Bkz. [[active-memory-reminder]].
3. **`git log --oneline -20`** — gerçekte neyin commit'lendiğini gör. İlerleme dosyası ile git log çelişirse, git log'a güven. İlerleme dosyası çökmüş bir yazma (crashed write) tarafından kırpılabilir (truncated); log yalnızca-ekleme (append-only) niteliğindedir.
4. **Kalan özellikleri say** — `cat feature_list.json | jq '[.[] | select(.passes==false)] | length'`. Alan adını projenin şemasına göre uyarla. Bu, seni tamamlanma durumunun (completion state) doğruluk kaynağına (source of truth) demirler.
5. **`./init.sh`** — dev sunucusunu ayağa kaldır. Bu başarısız olursa, bu oturumdaki tek işin onu düzeltmektir. Bozuk bir ortamla özellik işine atlama.
6. **En son "tamamlanmış" özelliği duman-testi yap** — tarayıcı-otomasyonu aracıyla, `curl` ile ya da gerçek CLI ile uçtan uca sür. Birim testleri değil. Başarısız olursa [[broken-window-check]]'i çağır: kusurlu commit'i geri al (revert), özelliği `passes: false`'a geri çevir ve yeni işe dokunmadan önce düzelt.

Yalnızca altı adımın hepsi geçtikten sonra yeni iş seç (seçim sezgisel yöntemleri için bkz. [[shift-notes]]).

## Anti-desenler (Anti-patterns)

- **"Bu depoyu zaten biliyorum, okumayı atlarım."** Bilmiyorsun. Sahip olduğun bağlam, önündeki bağlamdır.
- **İlerleme dosyasını okuyup git log'u okumama.** Düz metin yalan söyler; log söylemez.
- **`init.sh`'i çalıştırıp bir özelliği duman-testi yapmadan başarı varsayma.** Dev sunucusu temiz başlarken her rota bozuk olabilir.
- **Birim testleriyle duman-testi.** Birim testleri geçerken özellik uçtan uca bozuk olabilir — yanlış rota, eksik header, config uyumsuzluğu. Çalışma zamanı (runtime) yolunu sür.
- **6 adımı "hele bir yönlenip alayım" diye toplama (batching).** Adımlar sabit oldukları için ucuzdur. Yönelimi doğaçlamak, token'ın sızdığı yerdir.

## Maliyet/fayda

Her oturumun başında kabaca 2-4k token ve 30-60 saniye duvar-saati (wall-clock). Getiri (payoff), aynı proje üzerinde ~4 oturumu geçince ödemesini yapar; altında, ritüel ek yüktür (overhead). Projen tek-atışlıksa (one-shot), bunun yerine [[verification-before-completion]] kullan.

## İlgili

- [[shift-notes]] — bu protokolün okuyup yazdığı düz metin (prose) defteri.
- [[active-memory-reminder]] — adım 2b'de okunan eşlenik (paired) JSON kararlar defteri.
- [[broken-window-check]] — duman testi başarısız olduğunda adım 6 için alt-protokol.
- [[single-feature-per-session]] — yönelim tamamlandığında ne yapılacağı.
- [[clean-state-contract]] — bu protokolü sonraki oturum için ucuz kılan, oturum-sonundaki ayna (mirror) disiplini.

Ne zaman uygulanmaz: önceki durumu (prior state) olmayan tek-atışlık oturumlar ya da bir projenin ilk oturumu (henüz okunacak bir şey yok — bunun yerine başlatıcıyı (initializer) çalıştır).