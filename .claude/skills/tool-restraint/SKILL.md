---
name: tool-restraint
description: Bir ajanı araçlarla/MCP sunucularıyla aşırı donatma. Daha fazla araç = başarısız olmak için daha fazla yol ve daha yüksek bilişsel yük. Araç bağlarken veya bir ajan düşük performans gösterdiğinde kullan.
when_to_use: MCP sunucuları eklemek, çok araçlı bir ajan, "her şeye erişim ver"
---
# Tool Restraint
Bir ajanı "ne olur ne olmaz" diye 14 MCP sunucusuyla yüklemek onu daha yetenekli değil, daha yavaş ve daha aptal yapar — araç kullanan (tool-use) ajanlar, bilişsel yük yükseldikçe keskin yetenek uçurumlarına çarpar.
- **Yalnızca** mevcut işin gerçekten kullandığı sunucuları etkinleştir. Gerisini kaldır.
- Kimlik gerektiren (credentialed) araçlar için resmi sunucuları tercih et; asla beşini spekülatif olarak kurma.
- Her aracın açıklaması her turda context yer; daha az ama keskin araçlar bir çekmece dolusu abur cuburu yener.
- Yazma yetkili (write-scoped) bir sunucu eklemeden önce, her çağrıyı loglayan bir hook ekle.
Ajan yanlış aracı seçer ya da bocalarsa (thrash), çözüm genellikle daha akıllı bir model değil, daha net açıklamalı daha az araçtır.
