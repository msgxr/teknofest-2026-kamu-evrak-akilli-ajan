# TAKP (Türkiye Açık Kaynak Platformu) Aktarım Provası

Şartname m.7: "Yarışmacılardan projelerinde kullandıkları ve geliştirdikleri
kodları, veri kümelerini ve bileşenleri Türkiye Açık Kaynak Platformu GitHub
hesabında açık lisansla paylaşmaları beklenir." Bu belge, aktarımın önceden
provası ve yol haritasıdır.

## Doğrulanmış Durum Tespiti (12.07.2026)

| Konu | Bulgu | Kaynak |
|---|---|---|
| TAKP resmî sitesi | turkiyeacikkaynakplatformu.com (İstanbul Kalkınma Ajansı destekli; Bilişim Vadisi + TÜBİTAK TÜSSİDE) | site + Vikipedi |
| TAKP resmî GitHub org'u | github.com/tracikkaynak — mevcut ancak **Ağustos 2019'dan beri hareketsiz** (tek repo: platform sitesi) | GitHub |
| Resmî "proje ekleme" süreci | Platform dokümantasyonunda tarif edilmiş bir fork/transfer/başvuru akışı **bulunamadı** | site taraması |
| Fiilî uygulama | GitHub'da `turkiye-acik-kaynak-platformu` topic'i altında 7 public repo — ağırlıkla önceki TEKNOFEST NLP takımları; etiketleme geleneği | github.com/topics/turkiye-acik-kaynak-platformu |
| Bu repo | Topic **zaten ekli** ✅ (repo ayarlarında doğrulandı); Apache-2.0, public | gh repo view |

Not: acikkaynak.gov.tr ("Açık Kaynak Kod Platformu") TAKP'den AYRI bir devlet
Git servisidir; github.com/acikkaynak da ayrı bir topluluktur — ikisi de bu
yükümlülüğün muhatabı değildir (karıştırılmamalı).

## Ön-Aktarım Kontrol Listesi (bugün itibarıyla durum)

- [x] Açık lisans: Apache-2.0 (`LICENSE`)
- [x] Depoda model ağırlığı YOK; üçüncü taraf modeller yalnız
      bağlantı+sürüm+lisans+talimatla (`docs/model_bilgileri.md`)
- [x] Veri kümeleri sentetik + kaynak/kullanım haklı veri kartlarıyla
      (`data/README.md`; gerçek kamu/kişi verisi yok)
- [x] `turkiye-acik-kaynak-platformu` topic'i ekli
- [x] README'de TAKP rozeti (bu provayla eklendi)
- [ ] Yayın öncesi son süzgeç: `YAYIN_ONCESI_KONTROL.md` maddeleri
      aktarım günü yeniden koşulur
- [ ] Yarışma yönetiminden resmî aktarım talimatı (aşağıdaki senaryolar)

## Aktarım Senaryoları (talimata göre biri uygulanır)

**Senaryo A — Yönetimin bildireceği TAKP hesabına TRANSFER (tercih):**

```bash
# 1) Ön kontrol: temiz durum + CI yeşil
git status && gh run list --limit 1
# 2) Transfer (GitHub: Settings → Danger Zone → Transfer ownership)
gh api repos/msgxr/teknofest-2026-kamu-evrak-akilli-ajan/transfer \
  -f new_owner=<TAKP_HESABI>
# 3) Eski URL otomatik yönlenir; takım fork'ları yeniden bağlanır
```

**Senaryo B — TAKP org'una FORK/mirror (transfer istenmezse):**

```bash
gh repo fork msgxr/teknofest-2026-kamu-evrak-akilli-ajan \
  --org <TAKP_HESABI> --clone=false
# veya birebir ayna:
git clone --mirror https://github.com/msgxr/teknofest-2026-kamu-evrak-akilli-ajan.git
cd teknofest-2026-kamu-evrak-akilli-ajan.git
git push --mirror https://github.com/<TAKP_HESABI>/teknofest-2026-kamu-evrak-akilli-ajan.git
```

**Senaryo C — Topic-etiketli public repo (mevcut durum / fiilî gelenek):**
Resmî hesap talimatı gelmezse, önceki yarışma dönemlerinin fiilî uygulaması
olan `turkiye-acik-kaynak-platformu` topic'li public + Apache-2.0 repo durumu
zaten sağlanmıştır; teslim yazışmasında bu durum ve bu belge referans verilir.

## Sorumlu ve Zamanlama

- Sorumlu: Emine (şartname uyum takibi) + Sina (repo yönetimi).
- Zamanlama: Finalistlerin açıklanması (24 Temmuz) sonrasında, yarışma
  yönetiminin teslim yazısındaki talimata göre; son teslim tarihinden en az
  48 saat önce tamamlanır (takım kuralı).
