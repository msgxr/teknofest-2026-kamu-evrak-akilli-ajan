# Demo Senaryosu 2.0

Jüri sunumu için tasarlanmış, 4 sahneli uçtan uca gösterim
(şartname m.8: temel yetenekler ve özgün çıktılar Türkçe metinler
üzerinde gözlemlenebilir olmalı; internet kesintisine karşı yedek plan).

## Çalıştırma

```bash
# Proje kök dizininden — canlı demo
python demo/demo_scenario.py

# Kayıt yedeğiyle (konsol dökümü dosyaya yazılır; jürinin kayıttan
# izleme talebine hazırlık)
python demo/demo_scenario.py --kayit demo_kaydi.txt
```

Windows PowerShell'de Türkçe karakter sorunu yaşanırsa:
`$env:PYTHONIOENCODING="utf-8"` ayarlayıp yeniden çalıştırın.

## Sahneler

| # | Sahne | Gösterilen yetenek |
|---|---|---|
| 1 | Vatandaş dilekçesi → analiz + **cevap taslağı** | Görev 1 zinciri + Görev 2 taslağı, madde-referanslı mevzuat önerisi ve format denetimi, bağımsız taslak kalite hakemi, 3071 m.7 son işlem tarihi |
| 2 | **İVEDİ** damgalı üst yazı → **triyaj + yönlendirme** | Aciliyet damgası algılama, "5 iş günü" metin-içi süre + resmî tatil-farkında son tarih, gerekçeli birim yönlendirme |
| 3 | **Taranmış/gürültülü görüntü** → OCR hattı | G1-a görüntüden okuma; opsiyonel OCR yığını (pytesseract/easyocr) kuruluysa çalışır, değilse dürüst bildirimle atlanır |
| 4 | **"İNTERNETİ KES"** | Tüm ağ soket erişimi programatik olarak engellenirken aynı evrak yeniden işlenir — offline-first çekirdeğin kesintisiz çalıştığının kanıtı |

Her işlenen evrak için gözlemlenen çıktılar: sınıflandırma + güven,
bilgi çıkarımı, eksik bilgi tespiti, madde-referanslı mevzuat önerileri
(gerekçeleriyle), özet, resmî yazı taslağı, madde-dayanaklı format
denetimi, taslak kalite hakemi puanı, birim yönlendirme gerekçesi,
aciliyet/yasal süre, KVKK paylaşım nüshası özeti ve adım süreleri.

## Notlar

- Sahne 2'nin İVEDİ evrakı ve Sahne 3'ün taranmış görüntüsü **çalışma
  anında** `demo/demo_evraklar/` altına üretilir (tarih-bağımlı "kalan
  gün" hesabı canlı demoda her zaman anlamlı kalsın diye); bu dizin
  sürüm takibine girmez.
- Demo sonunda **süre provası** raporlanır (hedef ≤ 240 sn; 10 dakikalık
  sunumda demoya ayrılan pay). Salt işleme süresi saniyeler
  mertebesindedir; canlı sunumda anlatım temposu süreyi belirler.
- Görüntü sahnesi için opsiyonel kurulum:
  `pip install -r requirements-optional.txt` + sistemde Tesseract
  (`tesseract-ocr` + `tesseract-ocr-tur`).

## Jüri Sunumu İçin Not

- Demo gerçek zamanlı veya kayıttan sunulabilir; jürinin canlı
  çalıştırma talebine `python demo/demo_scenario.py` ile anında yanıt
  verilebilir.
- Kullanılan veri setleri kurgu olup gerçek kamu verisi içermemektedir;
  kaynak ve kullanım hakları: [`../data/README.md`](../data/README.md) —
  takım üretimi sentetik veri, Apache 2.0.
