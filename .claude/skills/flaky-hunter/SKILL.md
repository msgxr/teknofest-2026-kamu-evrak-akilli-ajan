---
name: flaky-hunter
description: Bazen geçen bazen başarısız olan testleri teşhis edin ve düzeltin. CI aralıklı olarak kırmızıya döndüğünde kullanın.
when_to_use: aralıklı CI başarısızlığı, "yerelde geçiyor CI'da başarısız", kararsız (flaky) bir test
---
# Kararsız Test Avcısı (Flaky Test Hunter)
Şüpheli testi önce bir döngüde 20 kez çalıştır — gerçekten kararsız (flaky) mı, yoksa sadece bozuk mu olduğunu doğrula.
Yaygın nedenler, olasılık sırasına göre:
1. **Zaman/sıra** — test çalıştırma sırasına veya paylaşılan değiştirilebilir duruma (shared mutable state) bağlı. İzole et; tek başına çalıştır.
2. **Async yarış (race)** — bir promise/refetch çözülmeden önce doğrulama (assert) yapmak. Bir sleep yerine gerçek koşulu await et.
3. **Gerçek ağ/saat/rastgele** — bunları mock'la. Zamanı dondur, RNG'yi tohumla (seed), çağrıyı stub'la.
4. **Kaynak sızıntısı (resource leak)** — önceki bir test bir bağlantı/dosya/port açık bırakmış.
Belirtiyi değil nedeni düzelt. Kararsız bir testte `retry(3)`, üretimde ısıracak gerçek bir yarışı (race) gizler. Karantinaya almayı yalnızca son çare olarak, bir ticket ile yap.
