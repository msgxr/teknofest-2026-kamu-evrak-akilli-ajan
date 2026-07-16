---
name: read-the-trace
description: Hata türüne göre örüntü eşleştirmek yerine yığın izinden (stack trace) gerçek nedeni çıkarın. Herhangi bir çökme veya istisnada (exception) kullanın.
when_to_use: bir yığın izi (stack trace), bir istisna, "TypeError/NullPointer/undefined", bir çökme günlüğü
---
# İzi Oku (Read the Trace)
LLM'ler "TypeError" görüp izi okumadan genel bir düzeltme üretmeye bayılır. Yapma.
- **KENDİ kodundaki en derin çerçeveyi (frame)** bul — en üstteki kütüphane çerçevesini değil. Kötü değerin girdiği yer orasıdır.
- Gerçek değerleri oku: ne null/undefined/yanlış-tür idi ve nereden geldi.
- Bir seviye yukarı izle: o değer neden kötüydü? Kök genellikle fırlatmadan 1-2 çerçeve yukarıdadır.
- Düzeltmeden önce tam olarak o girdiyle yeniden üret.
Bir TypeError yüz şey anlamına gelebilir. İz hangisi olduğunu söyler — "caused by" dahil hepsini oku.
