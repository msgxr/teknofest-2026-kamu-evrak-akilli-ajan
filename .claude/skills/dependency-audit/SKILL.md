---
name: dependency-audit
description: Bir bağımlılığı eklemeye, tutmaya veya kaldırmaya karar ver. Herhangi bir paket eklemeden önce kullan.
when_to_use: bir paket ekleme, şişmiş bir lockfile, bir CVE uyarısı, "bu dep'e ihtiyacımız var mı"
---
# Dependency Audit
Bir paket eklemeden önce sor:
1. **Stdlib bunu yapabilir mi?** `Array.map` için lodash yok. left-pad seviyesinde paketler yok.
2. **Zaten ağaçta (tree) mı var?** Proje fetch kullanıyorsa axios ekleme.
3. **Yaşıyor mu?** Son commit, açık issue'lar, maintainer yanıt verirliği.
4. **Maliyet?** Bir tarih formatlamak için 500KB'lık bir dep buna değmez. Kurulum boyutunu ve transitive dep'leri kontrol et.
5. **Güvenlik?** Bilinen CVE'ler? Postinstall script'leri?
Bir tane eklediğinde, PR gövdesinde gerekçelendir. package.json'ı asla sessizce büyütme. Mevcut dep'ler için: kullanılmayan veya tek fonksiyonluk olan her şey kaldırılır.
