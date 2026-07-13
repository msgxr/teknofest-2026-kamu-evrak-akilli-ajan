# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Aktif Öğrenme Kalibrasyon Önerisi — geri bildirim döngüsünün kapanışı.

Streamlit arayüzündeki "Sonucu Düzelt" akışı, kullanıcı düzeltmelerini
data/processed/geri_bildirim.jsonl dosyasına satır satır ekler:

    {"zaman": "...", "dosya": "...", "tahmin_tur": "dilekce",
     "dogru_tur": "cevap_yazisi", "tahmin_birim": "yazi_isleri",
     "dogru_birim": "hukuk"}

Bu betik o birikimi ÖLÜ VERİ olmaktan çıkarır: düzeltme desenlerini
(hangi tür hangi türle, hangi birim hangi birimle kaç kez düzeltilmiş)
özetler ve her desen için SOMUT, dosya/sözlük adı referanslı kalibrasyon
önerisi üretir — böylece geri bildirim döngüsü ölçülebilir bir iyileştirme
adımına bağlanır.

İLKESEL SINIR — betik kuralları OTOMATİK DEĞİŞTİRMEZ:
    Öneriler insan onayına sunulur; classification_agent.AGIRLIKLI_KELIMELER
    veya routing_agent.BIRIMLER üzerinde otomatik yazma yapılmaz. Gerekçe
    (değerlendirme bütünlüğü): az sayıda — ve muhtemelen tek kullanıcıdan
    gelen — geri bildirimle kuralları kendiliğinden değiştirmek, etiketli
    değerlendirme setine karşı kontrolsüz kayma (drift) yaratır; tek bir
    hatalı/kötü niyetli geri bildirim sistemin genel doğruluğunu düşürebilir.
    Doğru akış: öneri → insan incelemesi → elle kural değişikliği →
    testler + değerlendirme betiği ile doğrulama. Betik bu yüzden yalnız
    rapor üretir; kanıt düzeyini (kaç kez tekrarlandı) da açıkça işaretler.

Çıktılar:
    - Konsol raporu (rich Table)
    - data/processed/kalibrasyon_onerileri.json

Kullanım:
    python3 scripts/kalibrasyon_onerisi.py
    python3 scripts/kalibrasyon_onerisi.py --girdi baska.jsonl --cikti rapor.json
    python3 scripts/kalibrasyon_onerisi.py --json-only     # tablo basmaz

Desen-özetleme ve öneri fonksiyonları SAFTIR (girdi: satır listesi,
çıktı: sözlük/liste) ve dosya okumadan import edilip test edilebilir
(tests/test_iliski_zinciri.py).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Proje kökünü path'e ekle (betik hem kökten hem scripts/ içinden çalışsın)
_PROJE_KOKU = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJE_KOKU))

logger = logging.getLogger("kamu_evrak_ajan.kalibrasyon_onerisi")

VARSAYILAN_GIRDI = _PROJE_KOKU / "data" / "processed" / "geri_bildirim.jsonl"
VARSAYILAN_CIKTI = _PROJE_KOKU / "data" / "processed" / "kalibrasyon_onerileri.json"

# Kanıt düzeyi eşikleri: tek örnek rastlantı olabilir (zayıf); 2 tekrar
# bir eğilime işaret eder (orta); 3+ tekrar tutarlı bir desendir (güçlü).
# Düzeyler öneri tablosunda gösterilir ki insan onayı, kanıtı az olan
# desenlere karşı temkinli olabilsin.
KANIT_ESIKLERI = ((3, "güçlü"), (2, "orta"), (1, "zayıf"))

ORNEK_SATIR = {
    "zaman": "2026-07-11T10:30:00",
    "dosya": "data/raw/kurgu_evraklar/dilekce_01.txt",
    "tahmin_tur": "dilekce",
    "dogru_tur": "cevap_yazisi",
    "tahmin_birim": "yazi_isleri",
    "dogru_birim": "hukuk",
}


# --- Saf fonksiyonlar ---------------------------------------------------------


def jsonl_oku(yol: Path) -> List[dict]:
    """
    JSONL dosyasını satır listesi olarak okur; bozuk satırları atlar.

    Geri bildirim dosyası elle düzenlenmiş veya yarıda kesilmiş olabilir;
    tek bozuk satır tüm kalibrasyon raporunu düşürmemelidir.
    """
    satirlar: List[dict] = []
    with yol.open("r", encoding="utf-8") as f:
        for numara, ham in enumerate(f, 1):
            ham = ham.strip()
            if not ham:
                continue
            try:
                kayit = json.loads(ham)
            except json.JSONDecodeError:
                logger.warning("Bozuk JSONL satırı atlandı (satır %d).", numara)
                continue
            if isinstance(kayit, dict):
                satirlar.append(kayit)
    return satirlar


def _kanit_duzeyi(adet: int) -> str:
    """Tekrar sayısını kanıt düzeyi etiketine çevirir (bkz. KANIT_ESIKLERI)."""
    for esik, etiket in KANIT_ESIKLERI:
        if adet >= esik:
            return etiket
    return "zayıf"


def desenleri_ozetle(satirlar: "list[dict]") -> dict:
    """
    Geri bildirim satırlarından düzeltme desenlerini sayar.

    Bir satır iki bağımsız düzeltme taşıyabilir: tür (tahmin_tur ≠
    dogru_tur) ve birim (tahmin_birim ≠ dogru_birim). Tahminle aynı
    kalan alanlar düzeltme değil ONAYDIR ve desen sayımına girmez —
    onay sayısı ayrıca raporlanır (kuralın doğru çalıştığı kanıtı).

    Args:
        satirlar: geri_bildirim.jsonl kayıtları (sözlük listesi).

    Returns:
        {
            "toplam_satir": int,
            "onay_sayisi": int,          # hiçbir alanı düzeltilmemiş satır
            "tur_desenleri": [{"tahmin": str, "dogru": str, "adet": int}, ...],
            "birim_desenleri": [{"tahmin": str, "dogru": str, "adet": int}, ...],
        }
        Desen listeleri adet'e göre azalan sıralıdır (en sık desen önce).
    """
    tur_sayaci: Dict[tuple, int] = {}
    birim_sayaci: Dict[tuple, int] = {}
    onay_sayisi = 0

    for kayit in satirlar:
        if not isinstance(kayit, dict):
            continue
        duzeltme_var = False

        tahmin_tur = str(kayit.get("tahmin_tur") or "").strip()
        dogru_tur = str(kayit.get("dogru_tur") or "").strip()
        if tahmin_tur and dogru_tur and tahmin_tur != dogru_tur:
            tur_sayaci[(tahmin_tur, dogru_tur)] = (
                tur_sayaci.get((tahmin_tur, dogru_tur), 0) + 1
            )
            duzeltme_var = True

        tahmin_birim = str(kayit.get("tahmin_birim") or "").strip()
        dogru_birim = str(kayit.get("dogru_birim") or "").strip()
        if tahmin_birim and dogru_birim and tahmin_birim != dogru_birim:
            birim_sayaci[(tahmin_birim, dogru_birim)] = (
                birim_sayaci.get((tahmin_birim, dogru_birim), 0) + 1
            )
            duzeltme_var = True

        if not duzeltme_var:
            onay_sayisi += 1

    def _sirala(sayac: Dict[tuple, int]) -> List[dict]:
        return [
            {"tahmin": tahmin, "dogru": dogru, "adet": adet}
            for (tahmin, dogru), adet in sorted(
                sayac.items(), key=lambda oge: (-oge[1], oge[0])
            )
        ]

    return {
        "toplam_satir": len(satirlar),
        "onay_sayisi": onay_sayisi,
        "tur_desenleri": _sirala(tur_sayaci),
        "birim_desenleri": _sirala(birim_sayaci),
    }


def oneri_uret(ozet: dict) -> "list[dict]":
    """
    Desen özetinden somut, insan onayına hazır kalibrasyon önerileri üretir.

    Her öneri hangi dosyadaki hangi sözlüğe bakılacağını adıyla söyler
    (classification_agent.AGIRLIKLI_KELIMELER / routing_agent.BIRIMLER);
    genel geçer "kuralları iyileştirin" cümlesi üretilmez. Kurallar
    OTOMATİK DEĞİŞTİRİLMEZ (modül docstring'indeki gerekçe).

    Returns:
        [{"kapsam": "tur"|"birim", "desen": "a → b", "adet": int,
          "kanit_duzeyi": str, "oneri": str}, ...]
    """
    oneriler: List[dict] = []

    for desen in ozet.get("tur_desenleri", []):
        tahmin, dogru, adet = desen["tahmin"], desen["dogru"], desen["adet"]
        oneriler.append(
            {
                "kapsam": "tur",
                "desen": f"{tahmin} → {dogru}",
                "adet": adet,
                "kanit_duzeyi": _kanit_duzeyi(adet),
                "oneri": (
                    f"'{tahmin}' {adet} kez '{dogru}' olarak düzeltildi → "
                    f"src/agents/classification_agent.py içindeki "
                    f"AGIRLIKLI_KELIMELER['{dogru}'] sinyallerini gözden geçirin "
                    f"(bu evraklarda geçen ayırt edici kalıpları ekleyin/güçlendirin) "
                    f"ve AGIRLIKLI_KELIMELER['{tahmin}'] içinde her iki türde de "
                    f"geçen kelimelerin ağırlığını düşürmeyi değerlendirin."
                ),
            }
        )

    for desen in ozet.get("birim_desenleri", []):
        tahmin, dogru, adet = desen["tahmin"], desen["dogru"], desen["adet"]
        oneriler.append(
            {
                "kapsam": "birim",
                "desen": f"{tahmin} → {dogru}",
                "adet": adet,
                "kanit_duzeyi": _kanit_duzeyi(adet),
                "oneri": (
                    f"'{tahmin}' {adet} kez '{dogru}' olarak düzeltildi → "
                    f"src/agents/routing_agent.py içindeki "
                    f"BIRIMLER['{dogru}']['anahtar_kelimeler'] sözlüğüne bu "
                    f"evraklarda geçen ayırt edici terimleri eklemeyi, "
                    f"BIRIMLER['{tahmin}']['anahtar_kelimeler'] içinde iki birimi "
                    f"karıştıran kelimelerin ağırlığını düşürmeyi değerlendirin."
                ),
            }
        )

    return oneriler


def rapor_olustur(satirlar: "list[dict]", kaynak: str) -> dict:
    """Özet + önerileri tek JSON raporunda birleştirir (saf fonksiyon)."""
    ozet = desenleri_ozetle(satirlar)
    return {
        "olusturma_zamani": datetime.now().isoformat(timespec="seconds"),
        "kaynak_dosya": kaynak,
        "ozet": ozet,
        "oneriler": oneri_uret(ozet),
        "not": (
            "Öneriler insan onayı içindir; kurallar otomatik değiştirilmedi. "
            "Değişiklik sonrası tests/ ve değerlendirme betiği çalıştırılmalıdır."
        ),
    }


# --- Konsol / dosya çıktısı ---------------------------------------------------


def _tabloyu_bas(rapor: dict) -> None:
    """Kalibrasyon raporunu rich tablolarıyla konsola yazdırır."""
    from rich.console import Console
    from rich.table import Table

    console = Console()
    ozet = rapor["ozet"]
    console.print(
        f"\n[bold]Geri Bildirim Kalibrasyon Raporu[/bold] — "
        f"{ozet['toplam_satir']} kayıt "
        f"({ozet['onay_sayisi']} onay, "
        f"{len(rapor['oneriler'])} düzeltme deseni)\n"
    )

    if not rapor["oneriler"]:
        console.print(
            "[green]Düzeltme deseni yok — mevcut kurallar geri bildirimle uyumlu.[/green]"
        )
        return

    tablo = Table(title="Kalibrasyon Önerileri (insan onaylı — otomatik değişiklik yapılmaz)")
    tablo.add_column("Kapsam", style="cyan", no_wrap=True)
    tablo.add_column("Desen", style="magenta", no_wrap=True)
    tablo.add_column("Adet", justify="right")
    tablo.add_column("Kanıt", no_wrap=True)
    tablo.add_column("Öneri")
    for oneri in rapor["oneriler"]:
        tablo.add_row(
            oneri["kapsam"],
            oneri["desen"],
            str(oneri["adet"]),
            oneri["kanit_duzeyi"],
            oneri["oneri"],
        )
    console.print(tablo)


def main(argv: "list[str] | None" = None) -> int:
    """Betik giriş noktası: dosyayı okur, raporu basar ve JSON'a yazar."""
    parser = argparse.ArgumentParser(
        description="Geri bildirim kayıtlarından kural kalibrasyon önerileri üretir."
    )
    parser.add_argument(
        "--girdi",
        type=Path,
        default=VARSAYILAN_GIRDI,
        help=f"Geri bildirim JSONL dosyası (varsayılan: {VARSAYILAN_GIRDI})",
    )
    parser.add_argument(
        "--cikti",
        type=Path,
        default=VARSAYILAN_CIKTI,
        help=f"JSON rapor çıktısı (varsayılan: {VARSAYILAN_CIKTI})",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Konsol tablosu basma, yalnızca JSON raporu yaz.",
    )
    args = parser.parse_args(argv)

    if not args.girdi.exists():
        print(
            f"Geri bildirim dosyası bulunamadı: {args.girdi}\n\n"
            "Henüz kaydedilmiş geri bildirim yok. Streamlit arayüzündeki\n"
            "'Sonucu Düzelt (geri bildirim)' bölümünden düzeltme kaydettikçe\n"
            "dosya oluşacaktır. Beklenen format (her satır bir JSON kaydı):\n\n"
            f"  {json.dumps(ORNEK_SATIR, ensure_ascii=False)}\n"
        )
        return 0

    satirlar = jsonl_oku(args.girdi)
    rapor = rapor_olustur(satirlar, str(args.girdi))

    if not args.json_only:
        _tabloyu_bas(rapor)

    args.cikti.parent.mkdir(parents=True, exist_ok=True)
    with args.cikti.open("w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    print(f"\nJSON raporu yazıldı: {args.cikti}")
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    sys.exit(main())
