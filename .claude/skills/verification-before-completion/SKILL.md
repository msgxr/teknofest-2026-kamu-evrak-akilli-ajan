---
name: verification-before-completion
description: İşi tamamlandı, düzeltildi veya geçiyor olarak iddia etmeden önce kullan — commit'lemeden, PR açmadan veya devretmeden önce. Herhangi bir başarı iddiasından önce doğrulama komutunu BU turda çalıştırmayı ve çıktısını okumayı gerektirir.
---

# Tamamlanmadan Önce Doğrulama

İşi taze bir doğrulama olmadan tamamlandı diye iddia etmek verimlilik değil, dürüstsüzlüktür. `adversarial-verify` *ne* olduğudur; bu skill *ne zaman* olduğudur — herhangi bir tamamlanma iddiasından hemen önce geçtiğin kapı.

## Demir Kural

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

Doğrulama komutunu bu mesajda çalıştırmadıysan, geçtiğini iddia edemezsin. "Geçmeli" değil, "muhtemelen" değil, "diff'e bakılırsa" değil.

## Kapı fonksiyonu

"tamamlandı" / "düzeltildi" / "yeşil" / "birleştirmeye hazır" yazmadan önce — kendi kafanda bile:

1. **Belirle (Identify)** — bu iddiayı tam olarak hangi komut kanıtlıyor?
2. **Çalıştır (Run)** — taze, eksiksiz, bu turda yürüt.
3. **Oku (Read)** — tam çıktı, çıkış kodunu kontrol et, başarısızlıkları say.
4. **Doğrula (Verify)** — çıktı iddiayı gerçekten teyit ediyor mu?
5. **Ancak o zaman** — iddiayı, kanıtı ekleyerek yap.

Herhangi bir adımı atla = kullanıcıya yalan söylüyorsun, doğrulamıyorsun.

## Yaygın sahte iddialar → gerçekte neye ihtiyaç duydukları

| İddia | Gerektirir | Yeterli değil |
|---|---|---|
| Testler geçiyor | Taze test koşusu, çıkış 0, 0 başarısızlık | "geçmeli", önceki koşu, "mantık doğru görünüyor" |
| Linter temiz | Linter çıktısı, 0 hata | Kısmi kontrol, ilgisiz dosyalardan çıkarım yapma |
| Build başarılı | Build komutu, çıkış 0 | Linter'ın geçmesi, editör kıvrımlarının (squiggles) kaybolması |
| Hata düzeltildi | Orijinal belirtiyi yeniden üret, gerçekleşmediğini izle | Kod değişti, "varsayılan" düzeltme |
| Regresyon testi çalışıyor | Kırmızı → yeşil döngüsü doğrulandı (düzeltmeyi geri al, testin başarısız olduğunu izle, geri yükle, geçtiğini izle) | Testin bir kez geçmesi |
| Ajan/subagent tamamladı | VCS diff'ini oku, iddia edilen değişikliklerin var olduğunu doğrula | Ajanın kendi "başarı" raporu |
| Spec karşılandı | Plana karşı satır satır kontrol listesi | "Testler geçiyor, faz tamam" |

## Kırmızı bayraklar — doğrulamadan iddia etmek üzeresin

- "geçmeli", "muhtemelen", "gibi görünüyor", "iyi görünüyor" gibi kelimeler
- Komutu çalıştırmadan önce memnuniyet dili ("Harika!", "Mükemmel!", "Tamam!")
- Bu turda bir doğrulama bloğu olmadan commit / push / PR açmak üzere
- Bir subagent'ın kendi başarı raporuna güvenmek
- "Sadece bu seferlik" düşüncesi ya da "Yorgunum, yeterince yakın"
- Kısmi doğrulama (linter geçti, o halde build de geçmeli)

## Rasyonalizasyonu önleme

| Bahane | Gerçek |
|---|---|
| "Artık çalışmalı" | ÇALIŞTIR onu. |
| "Eminim" | Güven ≠ kanıt. |
| "Linter geçti" | Linter ≠ derleyici ≠ testler. |
| "Ajan başarı dedi" | Diff'i kendin oku. |
| "Kısmi kontrol yeterli" | Kısmi, bütün hakkında hiçbir şey kanıtlamaz. |
| "Farklı kelimeler, o yüzden kural geçmez" | Lafız değil ruh esastır. |

## Desenler

**Testler**
- Test komutunu çalıştır. `34/34 pass` gör. Sonra "tüm testler geçiyor" de.
- Asla: "artık geçmeli".

**Regresyon testleri (gerçek kırmızı-yeşil)**
- Test yaz → çalıştır (geç) → düzeltmeyi geri al → çalıştır (BAŞARISIZ OLMALI) → düzeltmeyi geri yükle → çalıştır (geç).
- Asla: kırmızı-yeşil döngüsü olmadan "bir regresyon testi ekledim".

**Build**
- Build'i çalıştır. Çıkış 0 gör. Sonra "build geçiyor" de.
- Asla: "linter geçti, build de geçmeli".

**Ajan devri (delegation)**
- Subagent başarı bildirir → VCS diff'ini kontrol et → iddia edilen değişikliğin gerçekten orada olduğunu doğrula → gerçek durumu bildir.
- Asla: ajanın raporunu yapıştırıp gerçekmiş gibi kabul etme.

## Bu ne zaman tetiklenir

Her zaman, şunlardan önce:
- Başarı / tamamlanma / düzeltildi / geçiyor / yeşil ifadesinin herhangi bir varyasyonu
- Commit'leme, PR açma, bir görevi tamamlandı işaretleme, devretme
- Sonraki göreve geçme
- İşin durumu hakkında herhangi bir olumlu ifade

## Şununla eşleştir

- `adversarial-verify` — ajanların "tamamlandı"yı sahtelemek için aldığı 11 kısayol; listeyi baştan sona geç, sonra bu kapıdan geç.
- `clean-commits` — temiz commit'ler doğrulanmış içerik gerektirir.
- `verifier` subagent'ı — onu görevlendir; sonra raporunu diff'e karşı doğrula (yukarıdaki "Ajan devri" desenine göre).

## Özet (bottom line)

Komutu çalıştır. Çıktıyı oku. SONRA sonucu iddia et. Pazarlık konusu değil.
