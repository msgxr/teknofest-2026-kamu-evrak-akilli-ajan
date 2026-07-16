---
name: feature-list-json
description: Her uçtan uca özelliği, passes:false ile katı JSON girdileri olarak listele; yalnızca-passes-düzenlenebilir disiplini ve öncelik sırasıyla. Temiz-bağlam (fresh-context) oturumlarının neyin bittiğini, sıradakini ve dokunmalarının yasak olduğunu bilmek için okuduğu defter (ledger).
when_to_use: iskele (scaffold) aşamasında ana özellik listesini kuran başlatıcı (initializer) ajan, uçtan uca (E2E) doğrulamadan sonra tek bir passes alanını çeviren kodlayıcı ajan, description/steps/tests alanlarının sessizce düzenlenmediğini denetleme
---

# feature_list.json

Ürünün eninde sonunda sahip olacağı her özelliğin defteri (ledger). Temiz-bağlam oturumları iş seçmek için onu okur; bittiğinde tam olarak bir boolean çevirir. Markdown değil JSON — sözdizimsel katılık yük taşır (load-bearing). Düz metin (prose) serbestçe düzenlenir; veri dikkatle düzenlenir.

Girdi başına format:

```json
{
  "category": "functional",
  "description": "New chat button creates a fresh conversation",
  "steps": [
    "Navigate to main interface",
    "Click the 'New Chat' button",
    "Verify a new conversation is created",
    "Check that chat area shows welcome state",
    "Verify conversation appears in sidebar"
  ],
  "passes": false
}
```

Kategoriler: `functional`, `ux`, `data`, `infra`. Diziyi uygulama (implementation) sırasına göre sırala — en üstteki, sıradaki inşa edilecek şeydir.

## Ne zaman uygulanır

- **Başlatıcı (initializer) ajan** iskele aşamasında: tam listeyi üret, her girdi `passes: false`. Genişliği hedefle — iyi kapsamlanmış 200 girdi, belirsiz 30 girdiyi yener.
- **Kodlayıcı ajan** oturum sonunda: uçtan uca doğrulamadan sonra, tam olarak bir `passes` alanını `false`'tan `true`'ya çevir.
- **Herhangi bir oturum** başlangıçta: kalan işi görmek için `jq '[.[] | select(.passes==false)] | length'`; en üstteki engellenmemiş (unblocked) girdiyi seç.

## Prosedür — başlatıcı (initializer)

1. Şartnamenin (spec) ima ettiği kullanıcı tarafından gözlemlenebilir her davranışı listele. Giriş (login), liste render'ı, boş durumlar, hata durumları, klavye kısayolları, mobil yerleşim — hepsi.
2. Her birini bir girdi olarak yaz. `description` tek cümledir, `steps` bir kullanıcının gerçek eylem dizisidir (uygulama notları değil).
3. Diziyi öyle sırala ki üstten alta yürüyen bir ajan, bağımlıları (dependents) inşa etmeden önce ön koşulları (prerequisites) inşa etsin.
4. Her `passes` `false` başlar. İstisna yok, duman testi (smoke test) için bile.
5. Doğrula: `jq '. | length'` sayını döndürür; `jq '[.[] | select(.passes==true)] | length'` 0 döndürür.

## Prosedür — kodlayıcı ajan

1. Dosyayı oku. Henüz düzenleme.
2. `passes: false` olan ve ön koşulları karşılanan en üstteki girdiyi seç. En üstteki engelliyse, en derindeki engellenmemiş girdiye in.
3. Uygula. Test et. Çalışma zamanı (runtime) yolu üzerinden uçtan uca doğrula (tarayıcı otomasyonu, HTTP, CLI) — yalnızca birim testleri değil. E2E'nin ne demek olduğu için bkz. [[broken-window-check]].
4. Yalnızca E2E yeşile döndükten sonra: o tek girdinin `passes` alanını `true`'ya çevir.
5. Dosyanın diff'ini al. Diff tam olarak bir `false` → `true` olmalı. Başka hiçbir şey değil.

## Anti-desenler (Anti-patterns)

- **`description`, `steps` veya `category` düzenleme** — bu alanları kaldırmak veya düzenlemek kabul edilemez çünkü eksik işlevselliğin gelecekteki oturumların gözünden kaçmasına izin verir. Defter, `passes` dışındaki her alanda yalnızca-ekleme (append-only) niteliğindedir.
- **Birim-testi kanıtıyla `passes: true` çevirme** — birim testleri geçerken rotalar yanlış yönlendirilmiş (misrouted), CORS bozuk veya buton bağlanmamış (unwired) olabilir. Yalnızca uçtan uca kanıt biti çevirir. Bkz. [[verification-before-completion]].
- **Tek oturumda birden fazla girdi çevirme** — oturum başına tek-özellik kuralı (bkz. [[one-feature-per-session]]) vardır çünkü tıka basa dolu oturumlar her şeyi yarım gönderir. Oturum başına bir çevirme.
- **Şartname (spec) değişikliği olmadan proje ortasında yeni girdi ekleme** — kapsam büyüdüyse, bunu [[shift-notes]]'a not düş ve yeniden-kapsamlama (re-scope) için işaretle; defteri sessizce genişletme.
- **"Eskimiş" girdileri silme** — bir özellik artık gerekmiyorsa, bırak ve bir notla `passes: true` işaretle veya kaldırmayı açıkça müzakere et. Sessiz silme, öncelik sayımını bozar.
- **JSON yerine Markdown veya YAML** — vardiya-işçisi (shift-work) ajan koşularında ölçüldüğünde, JSON, Markdown'a kıyasla sahte alan düzenlemelerini ~7 kat ve erken pass işaretlemeyi ~2 kat azaltır. Katılık işi yapan şeydir.

## Denetim kontrolü (Audit check)

Oturum sonunda, commit'lemeden önce:

```bash
git diff feature_list.json | grep -E '^[-+]' | grep -v 'passes'
```

Bu, dosya başlığı (header) dışında bir şey yazdırıyorsa, yasak bir alan düzenlemişsin demektir. O parçaları (hunks) geri al. Yalnızca `"passes": false` ↔ `"passes": true` satırlarının değişmesine izin verilir.

## Ne zaman uygulanmaz

- ~20 özelliğin altındaki projeler — listeyi yazmanın ek yükü (overhead), faydasını aşar; [[shift-notes]] içindeki düz bir TODO yeterlidir.
- Devir teslimi (handoff) olmayan tek-atışlık (one-shot) tek oturumlar — defterin bütün amacı oturumlar-arası disiplindir.

## İlgili

- [[shift-notes]] — düz metin (prose) tamamlayıcısı; feature_list.json durumu (state) tutar, shift-notes bağlamı (context) tutar.
- [[broken-window-check]] — biti çevirmeden önce "uçtan uca doğrulandı"nın ne demek olduğu.
- [[one-feature-per-session]] — seni oturum başına tek çevirmeyle sınırlayan kural.
- [[verification-before-completion]] — "çalışma zamanı kanıtı olmadan bit çevirme yok"un genel biçimi.