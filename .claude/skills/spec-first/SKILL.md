---
name: spec-first
description: Ajan eyleme geçmeden önce hedef spec'ini diske yaz, böylece sapamaz. Herhangi bir çok adımlı görevden önce kullan.
when_to_use: 2'den fazla adımı olan bir görev, uzun süren bir iş, "X'i inşa et", ajanın sapması
---
# Önce Spec
Harici bir sözleşme olmadan, ajan ~3 iterasyondan sonra sapar — ve başarısızlık ilerleme gibi görünür (kod yazılmış, testler geçiyor, yanlış hedef çözülmüş).
Eyleme geçmeden ÖNCE `PROMPT.md` yaz:
- **Hedef (Goal)** — tek cümle.
- **Tamamlanınca (Done when)** — somut, kontrol edilebilir koşullar. "Test paketi yeşil: <cmd>".
- **Asla dokunma (Never touch)** — sınır dışı dosyalar/alanlar.
- **Şu durumda dur (Stop if)** — kapsam dışında N'den fazla dosya değişirse; geçen bir test başarısız olmaya başlarsa.
Ajan bu dosyayı her iterasyonda yeniden okur. Durum (ne yapıldığı) ayrı bir `IMPLEMENTATION_PLAN.md` dosyasına gider ve orada yerinde güncellenir. "done when"i somut yazamıyorsan, görev hazır değildir — kodlamadan önce netleştir.
