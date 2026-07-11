"""
ML Eğitim Betiği — İstatistiksel sınıflandırıcı modelini eğitir.

Geliştirme setindeki (data/raw/kurgu_evraklar) etiketli evraklarla
saf Python Multinomial Naive Bayes modelini (TF-IDF benzeri
ağırlıklandırma; bkz. src/models/istatistiksel_siniflandirici.py)
eğitir ve data/processed/ml_model.json dosyasına yazar.

VERİ HİJYENİ: Eğitim YALNIZCA geliştirme setiyle yapılır. Held-out
setler (kurgu_evraklar_heldout*) dış geçerlilik ölçümüne ayrılmıştır;
eğitimde kullanılmaları veri sızıntısıdır ve ölçülen başarımı geçersiz
kılar. Betik, adında "heldout" geçen dizinlerle eğitimi reddeder.

Kullanım:
    python3 scripts/ml_egit.py
    python3 scripts/ml_egit.py --veri-dizini data/raw/kurgu_evraklar \\
        --cikti data/processed/ml_model.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Tuple

# Proje kökünü sys.path'e ekle (script doğrudan çalıştırıldığında gerekli)
PROJE_KOKU = Path(__file__).resolve().parent.parent
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

from src.models.istatistiksel_siniflandirici import egit, model_kaydet  # noqa: E402

logger = logging.getLogger("kamu_evrak_ajan.ml_egit")

VARSAYILAN_VERI_DIZINI = PROJE_KOKU / "data" / "raw" / "kurgu_evraklar"
VARSAYILAN_CIKTI = PROJE_KOKU / "data" / "processed" / "ml_model.json"


def egitim_verisi_yukle(veri_dizini: Path) -> List[Tuple[str, str]]:
    """
    etiketler.json'daki (dosya -> etiket) eşlemesinden eğitim verisi kurar.

    Returns:
        (metin, tur) ikilileri listesi.

    Raises:
        SystemExit: Etiket dosyası yoksa veya dizin held-out set ise.
    """
    if "heldout" in veri_dizini.name.lower():
        print(
            f"HATA: '{veri_dizini.name}' bir held-out (dış geçerlilik) setidir; "
            "eğitimde kullanılamaz (veri sızıntısı). Eğitim yalnızca "
            "geliştirme setiyle yapılmalıdır.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    etiket_dosyasi = veri_dizini / "etiketler.json"
    if not etiket_dosyasi.exists():
        print(f"HATA: Etiket dosyası bulunamadı: {etiket_dosyasi}", file=sys.stderr)
        raise SystemExit(2)

    etiketler = json.loads(etiket_dosyasi.read_text(encoding="utf-8"))
    dokumanlar: List[Tuple[str, str]] = []
    atlanan = 0
    for dosya_adi, bilgi in etiketler.items():
        dosya = veri_dizini / dosya_adi
        tur = str(bilgi.get("tur", "")).strip()
        if not dosya.exists() or not tur:
            atlanan += 1
            logger.warning(f"Atlandı (dosya veya tür etiketi yok): {dosya_adi}")
            continue
        dokumanlar.append((dosya.read_text(encoding="utf-8"), tur))

    if atlanan:
        print(f"Uyarı: {atlanan} kayıt atlandı (eksik dosya/etiket).")
    return dokumanlar


def main() -> None:
    """Modeli eğitir, kaydeder ve eğitim özetini basar."""
    parser = argparse.ArgumentParser(
        description="İstatistiksel sınıflandırıcı (Multinomial NB) eğitimi"
    )
    parser.add_argument(
        "--veri-dizini",
        type=Path,
        default=VARSAYILAN_VERI_DIZINI,
        help="Etiketli evrak dizini (varsayılan: data/raw/kurgu_evraklar)",
    )
    parser.add_argument(
        "--cikti",
        type=Path,
        default=VARSAYILAN_CIKTI,
        help="Model çıktı dosyası (varsayılan: data/processed/ml_model.json)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    dokumanlar = egitim_verisi_yukle(args.veri_dizini)
    print(f"Eğitim verisi: {len(dokumanlar)} belge ({args.veri_dizini.name})")

    model = egit(dokumanlar)
    yol = model_kaydet(model, args.cikti)

    print("\n--- Eğitim Özeti ---")
    print(f"Yöntem              : {model['yontem']} (saf Python, log-uzay, Laplace)")
    print(f"Belge sayısı        : {model['belge_sayisi']}")
    print(f"Sözlük boyutu       : {model['sozluk_boyutu']} öznitelik "
          "(kelime + karakter 3-gram)")
    print("Sınıf başına örnek  :")
    for sinif, adet in sorted(model["sinif_belge_sayilari"].items()):
        print(f"  {sinif:<16} {adet}")
    print(f"Model dosyası       : {yol} ({yol.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
