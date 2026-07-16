# Sunumlar

Bu dizin yarışma sunumlarını içerir.

## Dosyalar

- `Agentra_Tech_Takim_Tanitim_Sunum.pptx` — **Takım Tanıtım Sunumu** (görsel/diyagramlı/kod bloklu, kurumsal tasarım). Kaynağı `.md` değil, doğrudan `scripts/build_takim_tanitim_sunum.py` script'idir (native PowerPoint diyagramları çizer).
- `on_degerlendirme_sunumu.md` — Ön değerlendirme sunumunun slayt kaynak metni (konuşmacı notlarıyla)
- `on_degerlendirme_sunumu.pptx` — Ön değerlendirme sunumu
- `final_sunumu.pptx` — Final sunumu (Ağustos)

## Üretim

PPTX dosyası, `.md` kaynak dosyasından script ile üretilir:

```bash
pip install -r requirements-optional.txt   # python-pptx (yalnızca ilk sefer)
python scripts/build_presentation.py
# Final sunumu için:
python scripts/build_presentation.py --girdi presentations/final_sunumu.md --cikti presentations/final_sunumu.pptx
```

Slayt içeriği değiştirilecekse `.md` dosyası düzenlenip script yeniden çalıştırılır.
**PDF sürümü** (şartname PDF **ve** PPTX ister) PowerPoint'te dosya açılarak
"Dosya → Farklı Kaydet → PDF" ile elle alınır.

> ⚠️ Teslimden önce `.md` içindeki köşeli parantezli alanlar (`[TAKIM ADI]`,
> `[ÜYE 3]`, `[ÜYE 4]`, roller, `[E-POSTA]`) doldurulup script yeniden
> çalıştırılmalıdır.

## Sunum Kuralları (Şartname)

- Toplam süre: **15 dakika** (10 dk sunum + 5 dk jüri soru-cevap)
- Dil: **Türkçe** (teknik terimler İngilizce verilebilir)
- Format: **PDF ve PPTX**
- Sunan: Takım kaptanı veya yetkilendirdiği üyeler
