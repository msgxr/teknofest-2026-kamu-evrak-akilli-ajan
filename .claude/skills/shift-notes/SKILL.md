---
name: shift-notes
description: Hafızası olmayan yeni bir ajanın, bağlamı yeniden türetmeden bir öncekinin bıraktığı yerden devam edebilmesi için oturumlar-arası devir (handoff) dosyasını yaz ve oku. Yapılandırılmış düz metin (prose), JSON değil — model düz metni daha iyi yazar.
when_to_use: çok-oturumlu bir projede herhangi bir oturumun sonu, bir sonrakinin başı; broken-window-check ve feature-list durum dosyalarıyla eşleşir
---

# Vardiya Notları (Shift Notes)

Uzun-ömürlü ajanlardaki zor problem, bir oturumda iş yapmak değildir — oturumlar arasındaki bağlam boşluğunu köprülemektir. Her yeni ajan sıfır hafızayla başlar. Proje durumunu koddan yeniden inşa etmek zorunda kalırsa, tek satır yazmadan önce 5-10 dakika ve bir yığın bağlam yakar. İyi biçimlenmiş bir devir dosyası varsa, bu 30-60 saniyeye düşer.

O devir dosyası `claude-progress.txt`'dir (veya muadili). Düz metin, JSON değil. Model düz metni daha doğal yazar ve okuması ucuzdur.

## Biçim — bu şekle yaz

```
# Project: <name>
# Last updated: <ISO timestamp> by session <id>

## What's done
- <feature> [feature-list index: N]
- ...

## What's in progress
- <feature> [feature-list index: N]
  Status: <one paragraph — what works, what doesn't>
  Files touched this session: <list>
  Known open issues: <list>

## What's next (recommended)
- <feature> [feature-list index: N]
  Reason: <why this one>

## Notes for the next session
<free-form prose: gotchas, flaky tests, environment quirks>
```

Doğrulamayla değil, prompt tarafından yumuşakça dayatılır. Serbest metin işin özüdür — notlar bölümü, önceki vardiyanın başka hiçbir yerde kayda geçmeyen şey hakkında sonrakini uyardığı yerdir.

## Notları yazma — oturum sonunda

- **Tamamlanan özelliği** "devam eden"den "bitti"ye taşı.
- **Sonraki özelliği** "sırada ne var" bölümünde tek satırlık bir gerekçeyle öner (N'i-açar, düşük-risk, M-için-önkoşul).
- **Sonraki-oturum-için-notlar** en yüksek kaldıraçlı alandır. Şunlar için kullan: karşılaştığın kararsız (flaky) testler, seni şaşırtan bağımlılıklar, tek bir şekilde çözdüğün spec belirsizlikleri (böylece sonraki ajan yeniden tartışmaz), ayarlanması gereken env var'lar.
- **"Bitti" girdilerini silme.** Onlar denetim izidir (audit trail). Bölüm uzarsa, bu, proje ortasında budamak için değil, tüm notlar dosyasını v0.2 kilometre taşlarında sıkıştırmak için bir sinyaldir.

## Notları okuma — oturum başında

- Tüm dosyayı oku. Küçüktür.
- **Vardiya notları ile git log çelişirse, git log'a güven.** Notlar, çöken bir oturum tarafından kesilebilir (truncated); log kesilemez. Bu, belirleyici (load-bearing) bir kuraldır.
- "Ne yapıldı"yı feature list'e karşı çapraz-kontrol et. Notlar bitti diyor ama feature list bitmedi diyorsa, `broken-window-check` çalıştır.
- Bayatlamadıkça (yeni bir oturum onu zaten aldıysa) işi "sırada ne var"dan seç.

## Kırmızı bayraklar

- **Notların her oturumda sıfırdan yeniden yazılması.** Geçmişi kaybedersin, denetim izini kaybedersin. Ekle ve yerinde düzenle, üzerine yazma.
- **"Ne yapıldı" bölümünün sınırsızca büyümesi.** ~40 girdiye kadar sorun yok. Ondan sonra, özellik kilometre taşına göre sıkıştır.
- **Belirsiz "devam eden" düz metin.** "buton çalışıyor" yazarsan, sonraki oturum "buton bağlı ama durum (state) yenilenmiyor"u "bitti" olarak yanlış okur. Neyin başarısız olduğu konusunda net ol.
- **Notların feature list ile senkronizasyondan çıkması.** Feature list, geçti/kaldı durumu için doğruluk kaynağıdır (source of truth); notlar düz metin açıklamasıdır. Çeliştiklerinde liste kazanır.
- **JSON devir dosyası.** Denendi ve terk edildi — model JSON'a zorlandığında daha kısa, daha az yararlı notlar yazdı. Düz metin işinde düz metin kazanır.

## Notlara NE konulMAMALI

- Tam dosya içerikleri. Blob'lar değil, yolları referans göster.
- Oturumun düşünce zinciri (chain-of-thought). Onu tek bir durum satırına sıkıştır.
- Feature list'e (geçti/kaldı durumu) veya git'e (neyin değiştiği) ait olan herhangi bir şey.

## Şunlarla eşleşir

- `broken-window-check` — neyin duman-testinden (smoke-test) geçirileceğini bilmek için "ne yapıldı" listesini okur.
- `spec-first` — spec sözleşmedir; notlar ona karşı tutulan defterdir (ledger).
- `context-budget` — notlar, context-budget skill'inin istediği sıkıştırılmış özettir.

shift-notes dosyası projenin hafızasıdır. Ona belirleyici (load-bearing) muamelesi yap.
