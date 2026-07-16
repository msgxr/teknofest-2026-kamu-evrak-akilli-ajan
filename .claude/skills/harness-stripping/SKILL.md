---
name: harness-stripping
description: Karmaşıklığını artık hak etmeyen iskeleyi (scaffolding) öldürerek, her seferinde bir harness bileşenini sistematik olarak kaldır ve etkisini ölç.
when_to_use: bir model yükseltmesi sonrası hangi geçici çözümlerin (workaround) artık geçersiz olduğunu görmek için harness'ı denetleme, bir bileşen yeniden-test etmeye değer bir model zayıflığı varsayımını kodluyor, ya da harness organik olarak büyümüş ve ölü/gereksiz mekanizmadan şüpheleniyorsun
---

# Harness Soyma (Harness Stripping)

Her harness bileşeni, belirli bir model başarısızlığını telafi etmek için eklendi. Modeller gelişir. Bileşenler kendilerini emekliye ayırmaz. Sonnet 4.5'te seni kurtaran iskele, Opus 4.6'da ölü ağırlık — ya da aktif olarak zararlı — olabilir. Onu kasıtlı olarak, her seferinde bir parça soy ve neyin hâlâ ekmeğini çıkardığını (earns its keep) eval'lerin söylemesine izin ver.

Prithvi'nin Mart 2026 harness yazısındaki değerlendirici-üretici (evaluator-generator) ayrımından ve genel "her model sıçramasında varsayımlarını yeniden test et" disiplininden ilham alındı.

## Ne zaman uygulanır

- Yeni bir model yükseltmesi geldi ve harness'ın önceki nesle göre ayarlanmıştı.
- Bir bileşenin gerekçesi "bunu ekledik çünkü model eskiden X yapardı" — ve hâlâ X yapıp yapmadığını kontrol etmedin.
- Harness aylar boyunca birikti (accreted) ve mekanizmanın yarısının ne işe yaradığını kimse hatırlamıyor.
- Maliyet ya da gecikme (latency) tırmanıyor ve gereksiz kemer-ve-askı (belt-and-suspenders) katmanlarından şüpheleniyorsun.

## Prosedür

1. **Bileşenleri envanterle.** Her ayrı iskele parçasını listele: prompt bölümleri, araç sarmalayıcıları (tool wrappers), sonradan (post-hoc) doğrulayıcılar, yeniden-deneme (retry) döngüleri, değerlendirici personaları, yapılandırılmış-çıktı (structured-output) dayatıcıları, sandbox kuralları. Bileşen başına bir satır. Her birinin önlemek için eklendiği başarısızlık modunu not et.

2. **Şüpheye göre sırala.** Geçersiz olma olasılığı en yüksek bileşenleri en üste koy: son iki model sıçramasından önce eklenen her şey, son zamanlarda görmediğin bir başarısızlık modunu hedefleyen her şey, orijinal gerekçesi artık folklor olan her şey.

3. **Bir temel eval (baseline) seç.** Hiçbir şeye dokunmadan önce tekrarlanabilir bir metriğe ihtiyacın var. Varsa mevcut bir eval setini yeniden kullan; yoksa üretim işini temsil eden 20–60 görev seç. Temel skoru, maliyeti ve duvar-saatini (wall-clock) kaydet.

4. **Bir bileşeni soy.** Yalnızca bir tane. Yorum satırı yap ya da bir bayrağın (flag) arkasına al — henüz silme. Eval'i yeniden çalıştır.

5. **Temele (baseline) karşı karşılaştır.**
   - Skor gürültü (noise) içinde, maliyet/gecikme düşük → bileşen ölü ağırlıktır. Sil.
   - Skor ölçülebilir biçimde düşüyor → bileşen karmaşıklığını hâlâ hak ediyor. Geri koy ve *hangi başarısızlık modunun* geri döndüğünü not et.
   - Skor *iyileşiyor* → bileşen aktif olarak zararlıydı. Sil ve nedenini araştır (çoğunlukla: artık yetenekli olan bir modeli aşırı-kısıtlama).

6. **Farkı (delta) commit'le.** Soymayı (ya da not-ile-geri-koymayı) kendi commit'i olarak indir. Birden çok soymayı tek değişiklikte toplama — skor hareketini atfetme (attribute) yeteneğini kaybedersin.

7. **Sonraki bileşen için tekrarla.** Her turda temeli (baseline) orijinalden değil, *yeni* durumdan yeniden kur. Bileşik (compounding) soymaların bileşik etkileri vardır.

## Anti-desenler (Anti-patterns)

- **Aynı anda iki bileşeni soyma** — hangisinin önemli olduğunu söyleyemezsin. Sinyali yarıya indir, kafa karışıklığını ikiye katla.
- **Eval'i "kaldırılması bariz güvenli olduğu için" atlama** — harness sebeplerle birikti. Bazıları hâlâ gerçek. Ölç.
- **İlk geçişte gate'lemek (bayraklamak) yerine silme** — inceleme (review) ortasında A/B yapmak isteyeceksin. Önce bayrakla, eval onayladıktan sonra sil.
- **Eval yerine anekdotlara güvenme** — "onsuz daha iyi hissettiriyor", yük taşıyan (load-bearing) bileşenlerin böyle kaldırıldığı yoldur. Eval göstermiyorsa, orada değildir.
- **Güvenliği, sandbox'lamayı ya da maliyet sınırlarını (cost caps) koruyan bileşenleri soyma** — onlar model zayıflığını telafi etmiyor. Bırak.
- **Bunu prod trafiğinde yapma** — gerçek kullanıcılara değil, bir eval setine karşı çalıştır. Yeniden-yokladığın (re-probing) başarısızlık modları, tam da kullanıcılara zarar verenlerdir.

## Önce ne soyulmalı

Pratikte en yüksek getirili (yield):

- Artık doğal olarak (natively) geçerli JSON üreten modellerin üzerine katmanlanmış yapılandırılmış-çıktı dayatıcıları.
- Modelin artık tek-atışta (one-shot) çözdüğü görevlerdeki çok-adımlı "önce planla sonra uygula" (plan then execute) sarmalayıcıları.
- Artık takılmayan (flake) araç çağrıları etrafındaki yeniden-deneme (retry) döngüleri.
- Eleştirilerini üreticinin artık kendi başına öngördüğü değerlendirici personaları.
- X'in artık varsayılan davranış olduğu ayrıntılı (verbose) "X yapmayı unutma" prompt bölümleri.

## Ne zaman uygulanmaz

Uzun süredir devam eden canlı bir koşunun ortasında proje ortasında soyma yapma — uçuş halindeki (in flight) oturumları bozarsın. Projeler arasında ya da bir çatal (fork) dalında yap. Ayrıca güvendiğin bir eval'in yoksa atla; ölçüm olmadan soyma, tahmin etmektir.

## İlgili

- [[shift-notes]] — hangi bileşenlerin ne zaman soyulduğunu kaydet ki sonraki denetim aynı parçayı yeniden-soyup yeniden-geri-koymasın.
- [[adversarial-verify]] — daha yeni modellerde kendisi bir soyma adayı olabilecek değerlendirici-üretici deseni.
- [[broken-window-check]] — bir bileşeni soyup eval belirli bir şekilde geriliyorsa (regress), avlanacağın yeni kırık pencere odur.