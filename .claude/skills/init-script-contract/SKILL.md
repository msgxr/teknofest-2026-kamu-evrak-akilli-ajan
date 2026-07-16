---
name: init-script-contract
description: Harness'ın güvendiği sabit adlarla, 120 saniyenin altında idempotent init.sh ile birlikte kardeş test.sh, stop.sh, reset.sh, serve.sh betiklerini yaz.
when_to_use: başlatıcı (initializer) ajanın gelecekteki oturumlara devredeceği yeni bir projeyi iskeleleme (scaffolding), kurulum 120 saniyeyi aşıyor ve init artı serve olarak bölünmesi gerekiyor, her kodlama oturumu dev sunucusunu nasıl ayağa kaldıracağını yeniden keşfederek token yakıyor
---

# Init Betiği Sözleşmesi (Init Script Contract)

Çok-oturumlu bir projedeki her kodlama oturumu, dev sunucusunu ayağa kaldırarak başlar. Giriş noktası her seferinde farklı adlandırılıyorsa, ya da dört dakika sürüyorsa, ya da girdi istiyorsa (prompt), her tek oturumda token ve duvar-saati (wall-clock) yakarsın. Çözüm, sıkı bir sözleşmeyle proje kökünde sabit bir betik adları kümesidir. Başlatıcı ajan bunları bir kez yazar; sonraki her oturum bunlara güvenir.

Adlar yük taşır (load-bearing) — [[shift-notes]] ve [[broken-window-check]] her ikisi de onlara adlarıyla atıfta bulunur. Kendi adını uydurma.

## Ne zaman uygulanır

- Sen, yeni bir projeyi iskeleleyen başlatıcı (initializer) ajansın.
- Kurulumun 120 saniyeyi aştığını yeni keşfettin ve temiz bir şekilde bölmen gerekiyor.
- Oturumları uygulamayı nasıl başlatacağını sürekli yeniden keşfeden mevcut bir projeyi denetliyorsun.

## Beş betik

| Betik | Sözleşme |
|---|---|
| `init.sh` | Temiz klon → `localhost` üzerinde dev sunucusu ayakta. Idempotent. 120 saniyenin altında. Sıfır girdi istemi (prompt). |
| `serve.sh` | Yalnızca dev sunucusunu başlat. `init.sh` 120 saniyenin altına sığamadığında yazılır. |
| `test.sh` | Tüm test paketini çalıştır. Herhangi bir başarısızlıkta sıfır-olmayan çıkış. |
| `stop.sh` | Dev sunucusunu temiz bir şekilde öldür. Oturumlar çıkmadan önce bunu çalıştırır. |
| `reset.sh` | Yerel DB'yi ve geçici (ephemeral) durumu sil. Kodu dokunulmadan bırak. [[broken-window-check]] tarafından kullanılır. |

## Prosedür

1. **Şartnamenin (spec) ima ettiği yığını (stack) seç.** Şartnamenin gerektirmediği Docker, CI veya lint yapılandırmalarını iskeleleme.
2. **`init.sh`'i** boş bir klondan uçtan uca çalışacak şekilde yaz. Her bağımlılığı sabitle (lockfile, `==`, `Pipfile.lock`). Her istemi etkileşimsiz (non-interactive) cevapla (`-y`, `--yes`, `DEBIAN_FRONTEND=noninteractive`).
3. **Süresini ölç.** Temiz bir klonda `time ./init.sh` çalıştır. 120 saniyeyi aşarsa böl — tek-seferlik kurulumu `init.sh`'e, sunucu başlatmayı `serve.sh`'e taşı. Tek-komut başlatma hâlâ çalışsın diye `init.sh`'in sonda `serve.sh`'i çağırmasını sağla.
4. **Idempotent yap.** `./init.sh`'i art arda iki kez çalıştır. İkinci koşu hata verir ya da durumu çoğaltırsa (duplicate), her adımı varlık kontrolleriyle koru (`if [ ! -d node_modules ]`, `createdb --if-not-exists`, vb.).
5. **`stop.sh`'i** süreç adı grep'iyle değil, PID dosyası veya port ile öldürecek şekilde yaz. Grep, paylaşımlı sandbox'larda kardeş ajanları öldürür.
6. **`test.sh`'i** `init.sh`'in servis veren bir uygulama ürettiğini kanıtlayan tek bir uçtan uca duman testiyle (smoke test) yaz. Özellik testi yok — onlar gelecekteki oturumlara aittir.
7. **`reset.sh`'i** DB'yi düşürüp yeniden oluşturacak, önbellekleri temizleyecek, `/tmp` artefaktlarını silecek şekilde yaz. İzlenen (tracked) dosyalara asla dokunma.
8. **Boş durumdan doğrula.** `git clean -fdx && ./init.sh && ./test.sh && ./stop.sh`. Her betik 0 ile çıkar.

## Anti-desenler (Anti-patterns)

- **`bootstrap.sh`, `setup.sh`, `dev.sh` olarak adlandırma.** Sonraki oturumlar sabit adları grep'ler. Şirin bir takma ad (alias), harness'ı sessizce devre dışı bırakır.
- **Etkileşimli istemler (prompts).** Peer bağımlılıklarını soran `yarn install`, parola soran `createdb`, girdi bekleyen `npm audit`. Her istem, oturumun cevaplayamayacağı bir tıkanmadır (stall).
- **Sabitlenmemiş bağımlılıklar.** Lockfile olmadan `npm install foo`, sonraki oturumun farklı bir geçişli (transitive) grafik almasına yol açar. Bir ajanın `npm update --save` çalıştırıp on iki oturumu bozduğu Şubat 2026 olayına bkz.
- **Sunucuyu `pkill node` ile öldürme.** Sandbox'taki her node sürecini öldürür. `serve.sh` tarafından yazılan bir PID dosyası kullan.
- **`init.sh`'in proje dizini dışında dosya oluşturmasına izin verme.** Sandbox bunu reddeder ve hata modu şeffaf değildir (opaque).
- **"DB zaten iyi" diye `reset.sh`'i atlama.** [[broken-window-check]] kötü bir commit'i bayat (stale) durumdan izole etmek için ona ihtiyaç duyar.

## Kırmızı bayraklar (Red flags)

- `init.sh` çıktısında herhangi bir yerde "Press Y to continue" yazdırıyor.
- Zamanlama koşudan koşuya çılgınca değişiyor — bazı bağımlılık, sıcak yolda (hot path) ağdan çekiliyor.
- `init.sh`'i iki kez çalıştırmak migration'ları ikiye katlıyor ya da portları bağlı bırakıyor.
- `stop.sh` 0 ile çıkıyor ama `lsof -i :3000` hâlâ sunucuyu gösteriyor.

## Ne zaman uygulanmaz

Tek-oturumluk betikler ve tek-atışlık demolar. Sözleşme, kurulum maliyetini birçok oturuma yaymak (amortize) için vardır; tek-seferlik bir koşu buna ihtiyaç duymaz.

## İlgili

- [[shift-notes]] — sonraki oturumların `init.sh` başarılı olduktan sonra okuduğu notlar.
- [[broken-window-check]] — kötü bir özelliği geri alırken (revert) `init.sh`'i sonra `reset.sh`'i çalıştırır.
- [[single-feature-per-session]] — oturum başlangıcını ucuz tutarak bu sözleşmenin mümkün kıldığı disiplin.

İlham: Prithvi'nin Mart 2026 planlayıcı/üretici/değerlendirici (planner/generator/evaluator) yazısı; orada sabit harness giriş noktaları, değerlendirici (evaluator) personasının başlatma prosedürünü yeniden öğrenmeden herhangi bir üretici oturumunu sıfırdan yeniden doğrulamasına imkân tanıdı.