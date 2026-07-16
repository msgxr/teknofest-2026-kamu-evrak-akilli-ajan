---
name: systematic-debugging
description: Herhangi bir hata, test başarısızlığı, çökme veya beklenmedik davranış için
  kullanın. Bir düzeltme önermeden önce önce-yeniden-üret-sonra-izole-et disiplinini
  dayatır. Ajanın tahmin yürütmesini engeller.
when_to_use: bir test başarısız olduğunda, bir çökme, yanlış çıktı, "dün çalışıyordu", kararsız (flaky) bir başarısızlık
---

# Sistematik Hata Ayıklama (Systematic Debugging)

En pahalı ajan hatası tek başına şudur: bir hatayı görüp, gerçekte ne olduğunu okumadan,
yalnızca hata türüne bakarak hemen bir "düzeltme" üretmek. Yapma.

## Döngü

1. **Hatanın tamamını oku.** Tüm mesaj ve yığın izini (stack trace). Bir TypeError yüz
   farklı şey anlamına gelebilir — hangisi olduğunu izin (trace) söyler. Hatayı fırlatan tam satırı alıntıla.

2. **Önce yeniden üret.** Yeniden üretemiyorsan, bir düzeltmeyi doğrulayamazsın. Hatayı
   tetikleyen en küçük girdiyi yaz. "Sanırım bu düzeltir" hata ayıklama değil, kumardır.

3. **Tek bir hipotez kur, adını koy.** "Sanırım değer null, çünkü üst-akıştaki (upstream) çağrı
   gövdesiz 204 döndürüyor." Hiçbir şeye dokunmadan önce bunu ifade et.

4. **Tek bir şey değiştir. Test et. Tekrarla.** Üç şeyi değiştirip çalışırsa, hangisinin
   düzelttiğini bilemezsin — ve diğer ikisi yeni hatalar eklemiş olabilir.

5. **Belirtiyi değil kök nedeni düzelt.** Bir null'ı gizleyen null kontrolü bir düzeltme değildir.
   Neden null olduğunu bul. Yalnızca çökmeyi yamarsan, altta yatan hata farklı bir biçimde yeniden ortaya çıkar.

## Durma koşulları

- 3 hipotez başarısız olursa, DUR ve raporla: ne denedin, ne gördün, neden şüpheleniyorsun.
  "X ve Y'yi denedim, çıktı burada, sanırım sebep Z ama emin değilim" ifadesi, 20 sessiz
  rastgele denemeden iyidir.
- Anlamadığın bir geçici çözümü (workaround) asla ekleme.

## Çıktı

Şununla bitir: kök neden (tek cümle), minimal düzeltme ve artık bunu kanıtlayan test.
