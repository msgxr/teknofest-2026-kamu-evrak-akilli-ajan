---
name: changelog-from-diff
description: Bir dizi commit'i veya bir diff'i temiz, kullanıcıya dönük bir changelog girdisine dönüştürün. Bir sürüm (release) veya PR açıklamasından önce kullanın.
when_to_use: sürüm çıkarma, sürüm notları yazma, bir dalı özetleme
---
# Diff'ten Changelog (Changelog from Diff)
Commit mesajlarını değil, gerçek diff'i/commit'leri oku (mesajlar yalan söyler).
Şu gruplara ayır: **Eklendi · Değişti · Düzeltildi · Kaldırıldı · Güvenlik** (boş grupları atla).
Her satır: uygulama detayını değil, kullanıcıya dönük etkiyi anlatır. "Büyük harf içeren e-postalarda başarısız olan girişi düzeltti" — "kullanıcı aramasındaki hatayı düzeltti" değil.
- Kullanıcının fark ettiğiyle başla. İç detayları göm
- Bozan değişiklikleri (breaking changes) yüksek sesle, göç (migration) adımıyla birlikte belirt.
- PR/issue bağlantısını ver. Pazarlama süsü yok.
Çıktı: yapıştırılmaya hazır markdown. Bir değişikliğin kullanıcıya etkisi yoksa, dışarıda bırak.
