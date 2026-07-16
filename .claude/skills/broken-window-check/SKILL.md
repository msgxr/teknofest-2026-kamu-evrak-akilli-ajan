---
name: broken-window-check
description: Yeni iş seçmeden önce, en son "tamamlandı" denen özelliği duman testinden (smoke-test) geçir. Bozuksa, başka bir şeye dokunmadan önce geri al (revert) ve yeniden aç. Oturumlar arası "sevk edilmiş görünüyor, sevk edilmemiş" hatasını öldürür.
when_to_use: çok-oturumlu bir projede herhangi bir oturumun başı, ilerleme notlarını okuduktan ve init.sh çalıştırdıktan hemen sonra
---

# Broken-Window Check

Vardiya-notu odaklı (shift-notes) oturumlar boyunca, ajanlar bazen birim testleri geçtikten sonra bir özelliği tamamlandı olarak işaretler — özellik uçtan uca bozuk olsa bile. Sonraki oturum depoyu açar, yeşil bir git log görür ve bozuk bir temelin üzerine inşa eder. Biri fark ettiğinde, çatlağın üzerine üç özellik yığılmıştır.

**Kontrol:** yeni iş seçmeden önce, en son "tamamlanan" özelliği uçtan uca çalıştır. Başarısız olursa, bu oturumdaki tek işin olarak kabul et.

## Sıra — sırayla çalıştır, atlama yok

1. **Son "done" girdisini oku** — vardiya notlarında / özellik listesinde (proje hangisini kullanıyorsa).
2. **Özelliği uçtan uca sür** — gerçek çalışma zamanı (runtime) yolunu kullanarak: tarayıcı otomasyonu, HTTP isteği, CLI çağrısı. Birim testi değil.
3. **Gözlemlenen davranışı spec ile karşılaştır** — özellikteki `steps` alanı veya spec'teki kabul kriterleri.
4. **Çalışıyorsa** — normal iş seçimine geç. Kontrolü vardiya notlarına düş ("N özelliği hâlâ yeşil doğrulandı").
5. **Başarısız olursa** —
   - Tamamlandığını iddia eden commit'i `git revert` et (force-push yapma).
   - O özelliğin durumunu özellik listesinde `not-done`'a geri al.
   - Vardiya notlarına düş: "N özelliği geri alındı, sebep: <tek satır>".
   - Düzelt. Tüm oturumun bu.

Bozuk bir önceki özelliğin üzerine asla yeni iş seçme. Hiçbir zaman.

## "Uçtan uca" ne demek

Kontrol, kullanıcının gerçekten izlediği yolu çalıştırmalı. Bundan azı tiyatrodur.

| Özellik şekli | Geçerli kontrol | Geçersiz kontrol |
|---|---|---|
| Web UI butonu | Puppeteer/Playwright tıklama → DOM gözlemle | `expect(handler).toHaveBeenCalled()` |
| HTTP endpoint | Route'u `curl`'le → status + body kontrol et | Handler fonksiyonunda birim testi |
| CLI flag | Binary'yi flag ile çağır → çıktıyı gözlemle | Parser'ı import et, AST üzerinde assert et |
| Arka plan işi (background job) | Tetikle → bekle → yan etkiyi assert et | İş fonksiyonunun döndüğünü assert et |

## Kırmızı bayraklar — kontrol işini yapmıyor

- **Özelliği çalıştırmak yerine testleri okuyorsun.** Testler geçerken özellik bozuk olabilir (yanlış route, eksik CORS, config uyumsuzluğu). Runtime'ı sür.
- **Kontrolü geçirmek için bir mock ekliyorsun.** Mock, hatanın kendisi. Kaldır, başarısızlığı izle, gerçek durum budur.
- **Gerçeği yansıtması için özellik listesini düzenleyerek "düzeltiyorsun"** ("aa, X'i hiç desteklemiyormuş"). Hayır. Geri al. Yeniden aç. Defteri değil, kodu düzelt ya da spec'te kapsamı müzakere et.
- **"Dün çalışıyordu" diye kontrolü atlıyorsun.** Dünkü oturum, bugünkü dev sunucusunu çalıştırmaz.

## Maliyet

Kontrol, sağlıklı bir projede oturum başına 30-90 saniyedir. Yoldan çıkmak üzere olan bir projede saatler kazandırır. Kontrol uygulandığında, uygulanmadığına kıyasla erken-tamamlanma oranındaki düşüş kabaca 4 kattır (vardiya-işi tarzı ajan koşularında ölçülmüştür).

## Şununla eşleşir

- `shift-notes` — kontrolün okuduğu ve yazdığı defter.
- `adversarial-verify` — tamamlandı iddia etmeden *önce* bunu mevcut oturumun diff'inde çalıştır, ki sonraki oturumun sana broken-window yapması gerekmesin.
- `verification-before-completion` — "kanıt olmadan iddia etme"nin genel biçimi.

Her oturum kontrolü uygularsa, vardiya-işi ajanlarının bileşik-hata (compounding-error) modu bileşmeyi durdurur.
