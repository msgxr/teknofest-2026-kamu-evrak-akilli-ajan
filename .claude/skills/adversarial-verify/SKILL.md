---
name: adversarial-verify
description: Bir diff'i, kodun BOZUK olduğunu varsayarak hedef spec'ine karşı incele.
  Yapımcının kafasında yaşayan denetçi her zaman kendisiyle hemfikirdir — bu, incelemeyi
  düşmanca, ayrı bir tura çeker. Her kod değişikliğinden sonra, işi tamamlandı işaretlemeden
  önce çağır.
when_to_use: bir kod değişikliği "tamamlandı", bir görevi tamamlandıya çevirmeden önce, commit'ten önce
---

# Düşmanca Doğrulama

Varsayılan duruş: **aksi kanıtlanana kadar kod bozuktur.** Görevin, nerede olduğunu bulmak.
Nazik olma. Düzeltme önerme. Kodu çalıştırma. Sadece avlan.

## Önce oku

- Hedef spec (PROMPT.md / görev). "Tamamlandı" gerçekte neyi gerektiriyor?
- Diff. Değişen her satır.

## Ajanların "tamamlandı"yı sahtelemek için aldığı 11 kısayol — her birini kontrol et

1. **Gevşetilmiş testler (relaxed tests)** — kırmızıyı yeşile çevirmek için zayıflatılmış veya silinmiş assertion'lar.
2. **Yutulmuş hatalar (swallowed errors)** — başarısızlığı ele almak yerine gizleyen try/except.
3. **Sahte yeniden adlandırmalar (fake renames)** — yeniden adlandırılarak "düzeltilmiş", davranışı değişmemiş bir fonksiyon.
4. **Saplama dönüşler (stub returns)** — tek testi geçen ama diğer her şeyde başarısız olan, sabit kodlanmış dönüş değerleri.
5. **Düzeltme yerine yorum (comment-as-fix)** — hata artık bir TODO.
6. **Yalnızca mutlu yol (happy-path only)** — 500'ler, boş girdiler, eksik dosyalar ele alınmamış.
7. **Kapsam kayması (scope creep)** — hedefle ilgisiz değişiklikler ("hazır oradayken").
8. **Uydurulmuş API (invented API)** — gerçek kaynakta var olmayan bir metot/parametre.
9. **Sessiz karar (silent decision)** — bayrak kaldırmadan yapılan mimari bir seçim (şema, auth).
10. **Mock ile geçme (pass-by-mock)** — test, doğruladığını iddia ettiği şeyin ta kendisini mock'lar.
11. **Spec dışı tamamlanma (off-spec done)** — kod çalışıyor, testler geçiyor, ama istenen hedeften başka bir hedefi çözüyor.

## Çıktı (JSON, düz metin yok)

```json
{"passes": false, "failures": [{"line": 42, "shortcut": "swallowed errors", "why": "..."}]}
```

Gerçekten geçiyorsa, tek satırda söyle. Çoğu zaman geçmez.
