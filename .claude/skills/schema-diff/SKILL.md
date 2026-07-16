---
name: schema-diff
description: İki şema durumunu karşılaştır ve riskli değişiklikleri su yüzüne çıkar. Migration'ları uygulamadan önce veya bir model değişikliğinden sonra kullan.
when_to_use: bir migration'ı incelerken, "şemada ne değişti", deploy öncesi kontrol
---
# Schema Diff
Eski şema ile yeniyi diff'le. Riske göre işaretle:
- **Yıkıcı (destructive)** (yüksek): düşürülen (dropped) kolon/tablo, daraltılan tip, mevcut satırlar üzerinde yeni NOT NULL, bir sorgunun dayandığı düşürülen index.
- **Kilitleyici (locking)** (ölçekte yüksek): CONCURRENTLY olmadan index, tabloyu yeniden yazan tip değişikliği.
- **Güvenli**: yeni nullable kolon, yeni tablo, yeni CONCURRENTLY index.
Her yıkıcı değişiklik için: veri kaybı var mı? geri döndürülebilir mi? bir geri doldurma (backfill) var mı? Çıktı: riske göre sıralı bir liste ve güvenli yayına-alma (rollout) sırasıyla bir git/gitme (go/no-go) kararı.
