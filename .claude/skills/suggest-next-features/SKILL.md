---
name: suggest-next-features
description: İlk iskeleden (scaffold) bu yana git log'unu + son 3 ilerleme notunu oku, feature_list.json değişmez (immutable) kalsın diye AYRI bir öneriler dosyasına özellik eklemeleri taslakla
when_to_use: feature_list.json'da sıfır passes:false girdisi kaldığında YA DA son 3 oturum yeni iş eklemedi ve şartname (spec) sessizce genişledi (kullanıcı listede yer almayan bir şey istedi)
---

# suggest-next-features

Defter kuruyor (runs dry). Ya her `feature_list.json` girdisi `passes: true`, ya da son birkaç oturum yarı-özellikleri karıştırıp yeni iş eklemiyor çünkü şartname (spec) büyüdü ve liste büyümedi.

Bu skill aday eklemeleri taslaklar — ama **ayrı** bir dosyaya, `feature_list.suggestions.json`. `feature_list.json`, [[feature-list-json]]'ın izin verdiği tek `passes: false → true` çevirmesi dışında değişmezdir (immutable). Sessizce girdi eklemek o sözleşmeyi bozar ve kontrolsüz (runaway) bir oturumun kendi kapsamını uydurmasına izin verir.

Öneriler dosyası bir tekliftir (proposal). Bir insan, seçilen girdileri elle `feature_list.json`'a birleştirir (hand-merge); geri kalanı yok sayılır ya da silinir. Hiçbir ajan, hiçbir zaman, bu skill'den `feature_list.json`'ı doğrudan düzenlemez.

## Tetik (Trigger)

**Ya** koşul geçerliyse uygula:

- `jq '[.[] | select(.passes==false)] | length' feature_list.json` `0` döndürüyor.
- `claude-progress.txt`'deki son 3 ilerleme girdisi hiçbir yeni `passes: true` çevirmesi göstermiyor VE kullanıcı `feature_list.json`'da bulunmayan bir davranışa atıfta bulundu.

Yalnızca liste kısa göründüğü için uygulama. 30 bitmemiş girdi bir tetik değildir; 0 tetiktir.

## Prosedür

1. `git log --pretty=format:'%h %s' "$(git log --grep='chore: initial scaffold' --format=%H | tail -1)"..HEAD` — iskeleden (scaffold) bu yana her commit. Bu, iddia edilen değil, gerçekte gönderilen şeydir.
2. `claude-progress.txt`'den son 3 "What's done" / "Notes for the next session" girdisini oku. Son zamanlardaki kapsam kayması (scope creep) burada sızar.
3. `feature_list.json`'ı tam olarak oku. Kopya (duplicate) önermemek için nelerin zaten listelendiğini bilmen gerekir.
4. (1)+(2)'yi (3)'e karşı karşılaştır. Şunları ara:
   - Kullanıcının son oturumlarda istediği, eşleşen girdisi olmayan davranış.
   - Gönderilen özelliklerin ima ettiği doğal sonraki adımlar (bir özellik POST endpoint'i gönderir ama sonuçları için liste görünümü yoktur).
   - İlk listenin yetersiz kapsadığı (under-covered) kategoriler (hata durumları, boş durumlar, mobil yerleşim, klavye kısayolları, çevrimdışı (offline) davranış).
5. `feature_list.json` ile aynı biçimde 5–10 aday girdi taslakla. Her biri `passes: false` başlar. Onları kabaca önceliğe göre sırala.
6. Diziyi proje kökündeki `feature_list.suggestions.json`'a yaz. Önceki taslağın üzerine yaz — bu dosya yeniden-üretilebilir (regenerable), yalnızca-ekleme (append-only) değil.
7. Operatörün dosyayı açmadan tarayabilmesi için öneri başına tek-satırlık bir özet yazdır.
8. Dur. `feature_list.json`'a dokunma. `feature_list.suggestions.json`'ı commit'leme (bir teklif, proje durumu değil).

## Çıktı biçimi (Output shape)

`feature_list.suggestions.json` — `feature_list.json` ile aynı şema:

```json
[
  {
    "category": "ux",
    "description": "Empty conversation list shows an onboarding CTA",
    "steps": [
      "Load app as a user with zero conversations",
      "Verify the sidebar shows a 'Start your first chat' CTA",
      "Click the CTA and land in a fresh conversation"
    ],
    "passes": false,
    "rationale": "Sessions 41/43 both hit the empty-list path and rendered a blank sidebar; no entry covers it."
  }
]
```

`rationale` alanı öneriler dosyasına özgüdür — teklifi gerekçelendirir ki insan birleştirici (merger) hızlı karar verebilsin. `feature_list.json`'a birleştirmeden önce `rationale`'ı çıkar (strip).

## Anti-desenler (Anti-patterns)

- **Bu skill'den `feature_list.json`'ı asla doğrudan düzenleme.** Ne eklemek için, ne yeniden sıralamak için, ne de yorum eklemek için. [[feature-list-json]]'daki değişmezlik (immutability) kuralı kazanır.
- **Sonraki koşuda `feature_list.suggestions.json`'ı silme.** Üzerine yaz — operatör onu kısmen tüketmiş olabilir ve bir yeniden-yazma, diff-birleştirmeden (diff-merge) daha nettir.
- **Bir seferde 10'dan fazla önerme.** Uzun listeler okunmaz, göz gezdirilir. Daha fazlası hak ediliyorsa, ilk 10'u gönder ve geri kalanı `claude-progress.txt`'e not et.
- **Öneriler dosyasını commit'leme.** O, operatör için bir tekliftir, doğruluk-kaynağı (source-of-truth) artefaktı değil. Operatör henüz eklemediyse `feature_list.suggestions.json`'ı `.gitignore`'a ekle.

## İlgili

- [[feature-list-json]] — bu skill'in saygı gösterdiği değişmezlik (immutability) sözleşmesi.
- [[shift-notes]] — son-kapsam-kayması (recent-scope-drift) sinyallerinin yaşadığı yer.
- [[progress-reading-protocol]] — bu skill'in tersine yansıttığı taze-oturum okuması (geçmişi okur, ileriye dönük teklifler yazar).