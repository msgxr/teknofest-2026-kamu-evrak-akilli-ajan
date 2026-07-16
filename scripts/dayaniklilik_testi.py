# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Metamorfik Dayanıklılık Testi (CheckList-INV).

Geliştirme setindeki her evrağa etiket-KORUYAN bozulmalar (diyakritik kaybı,
yazım hatası, OCR ikamesi, boşluk/noktalama gürültüsü) uygular ve sistemin
kararının (tür / birim) bu bozulmalar altında DEĞİŞMEME oranını (invaryans) ile
gürbüz doğruluğu (robust accuracy) ölçer. 52 elle etiketli evrak, deterministik
tohumla yüzlerce varyanta ölçeklenir; en kırılgan bozulma türü hata analizi
olarak raporlanır.

Şartname bağlamı: sağlamlık/dayanıklılık kanıtı (Yöntem ve Teknik Yaklaşım).
Literatür: Ribeiro vd. 2020 (CheckList INV). Ölçüm KURAL-TABANLI (offline) mod
içindir. Tüm yollar GÖRELİDİR (raporlara mutlak yol sızmaz).

Kullanım:
    python3 scripts/dayaniklilik_testi.py
    python3 scripts/dayaniklilik_testi.py --tohum 7 --azami-dosya 10
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJE_KOKU = Path(__file__).resolve().parent.parent
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

from src.utils.metamorfik import PERTURBASYONLAR, varyant_uret  # noqa: E402

logger = logging.getLogger("kamu_evrak_ajan.dayaniklilik")

VARSAYILAN_SET = PROJE_KOKU / "data" / "raw" / "kurgu_evraklar"
VARSAYILAN_RAPOR = PROJE_KOKU / "data" / "processed" / "dayaniklilik_raporu.json"


def goreli_yol(yol: Path) -> str:
    """Mutlak yolu proje köküne göre göreli stringe çevirir (yol sızıntısı yok)."""
    p = Path(yol).resolve()
    try:
        return p.relative_to(PROJE_KOKU).as_posix()
    except ValueError:
        return p.name


def dayaniklilik_olc(
    veri_dizini: Path, tohum: int = 1234, azami_dosya: Optional[int] = None
) -> Dict[str, Any]:
    """Metamorfik dayanıklılığı ölçer ve rapor sözlüğü döndürür."""
    from src.pipelines.end_to_end_pipeline import EndToEndPipeline

    etiket_yolu = veri_dizini / "etiketler.json"
    etiketler = json.loads(etiket_yolu.read_text(encoding="utf-8"))
    dosyalar = sorted(etiketler.keys())
    if azami_dosya:
        dosyalar = dosyalar[:azami_dosya]

    pipeline = EndToEndPipeline()

    tur_ayni = birim_ayni = 0
    robust_dogru = 0
    toplam_varyant = 0
    islenen_evrak = 0  # DÜZELTME: diskte gerçekten bulunan/işlenen evrak sayısı
    pert = defaultdict(lambda: {"toplam": 0, "tur_degisti": 0, "birim_degisti": 0})
    degisim_ornekleri: List[Dict[str, str]] = []

    for i, dosya_adi in enumerate(dosyalar, 1):
        yol = veri_dizini / dosya_adi
        if not yol.exists():
            continue
        logger.info(f"[{i}/{len(dosyalar)}] {dosya_adi}")
        islenen_evrak += 1
        metin = yol.read_text(encoding="utf-8")

        orijinal = pipeline.process_text(metin, mode="full", kayit=False)
        o_tur = (orijinal.get("siniflandirma") or {}).get("tur", "diger")
        o_birim = (orijinal.get("yonlendirme") or {}).get("birim_kodu", "")
        gercek_tur = etiketler[dosya_adi].get("tur", "diger")

        for ad, varyant_metin in varyant_uret(metin, tohum):
            sonuc = pipeline.process_text(varyant_metin, mode="full", kayit=False)
            v_tur = (sonuc.get("siniflandirma") or {}).get("tur", "diger")
            v_birim = (sonuc.get("yonlendirme") or {}).get("birim_kodu", "")

            toplam_varyant += 1
            pert[ad]["toplam"] += 1
            if v_tur == o_tur:
                tur_ayni += 1
            else:
                pert[ad]["tur_degisti"] += 1
                degisim_ornekleri.append({
                    "dosya": dosya_adi, "bozulma": ad,
                    "orijinal_tur": o_tur, "bozulmus_tur": v_tur,
                })
            if v_birim == o_birim:
                birim_ayni += 1
            else:
                pert[ad]["birim_degisti"] += 1
            if v_tur == gercek_tur:
                robust_dogru += 1

    n = max(toplam_varyant, 1)
    # En kırılgan bozulma (tür kararını en çok değiştiren)
    pert_ozet = {
        ad: {
            "toplam": v["toplam"],
            "tur_invaryans": round(1 - v["tur_degisti"] / max(v["toplam"], 1), 4),
            "birim_invaryans": round(1 - v["birim_degisti"] / max(v["toplam"], 1), 4),
        }
        for ad, v in pert.items()
    }
    en_kirilgan = min(
        pert_ozet, key=lambda a: pert_ozet[a]["tur_invaryans"], default=None
    )

    return {
        "zaman_damgasi": datetime.now().isoformat(timespec="seconds"),
        "veri_dizini": goreli_yol(veri_dizini),
        "tohum": tohum,
        "degerlendirilen_evrak": islenen_evrak,  # DÜZELTME: len(dosyalar) değil (eksik dosyalar atlanır)
        "uygulanan_bozulmalar": list(PERTURBASYONLAR),
        "toplam_varyant": toplam_varyant,
        "tur_invaryans": round(tur_ayni / n, 4),
        "birim_invaryans": round(birim_ayni / n, 4),
        "gurbuz_dogruluk": round(robust_dogru / n, 4),
        "bozulma_bazinda": pert_ozet,
        "en_kirilgan_bozulma": en_kirilgan,
        "degisim_ornekleri": degisim_ornekleri[:20],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Metamorfik dayanıklılık testi (CheckList-INV)."
    )
    parser.add_argument("--veri-dizini", type=Path, default=VARSAYILAN_SET)
    parser.add_argument("--rapor-dosyasi", type=Path, default=VARSAYILAN_RAPOR)
    parser.add_argument("--tohum", type=int, default=1234)
    parser.add_argument("--azami-dosya", type=int, default=None)
    parser.add_argument("--json-only", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    rapor = dayaniklilik_olc(args.veri_dizini, args.tohum, args.azami_dosya)
    args.rapor_dosyasi.parent.mkdir(parents=True, exist_ok=True)
    args.rapor_dosyasi.write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if not args.json_only:
        print("\n=== Metamorfik Dayanıklılık Testi ===")
        print(f"Değerlendirilen evrak : {rapor['degerlendirilen_evrak']}")
        print(f"Toplam varyant        : {rapor['toplam_varyant']}")
        print(f"Tür invaryansı        : {rapor['tur_invaryans']}")
        print(f"Birim invaryansı      : {rapor['birim_invaryans']}")
        print(f"Gürbüz doğruluk       : {rapor['gurbuz_dogruluk']}")
        print(f"En kırılgan bozulma   : {rapor['en_kirilgan_bozulma']}")
        print(f"Rapor                 : {goreli_yol(args.rapor_dosyasi)}")


if __name__ == "__main__":
    main()
