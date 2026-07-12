"""KVKK maskeleme kaçak (leak) denetimi — anonimleştirmenin nicel doğrulaması.

Anonimleştirilmiş metinde MASKELENMEDEN kalmış kişisel-veri deseni (checksum-
geçerli T.C. kimlik no, telefon, e-posta, IBAN) olup olmadığını ölçer. Böylece
KVKK iddiası "iddia" olmaktan çıkıp nicel kanıta bağlanır: kaçak = maskeleme
recall'ının tümleyeni. i2b2 de-identification değerlendirme geleneğinin hafif,
REFERANSSIZ uyarlamasıdır (span-düzeyi altın etiket gerektirmez).

Maskelenmiş değerler "*" içerdiğinden desenlerle eşleşmez; yalnızca maskelenmeden
kalan (gerçek biçimli) PII yakalanır. Literatür: Stubbs & Uzuner (2015) i2b2
de-identification; HIPAA Safe Harbor de-id değerlendirme geleneği; KVKK m.4/m.8.
Saf Python.
"""

from __future__ import annotations

import re
from typing import Dict

_DESENLER = {
    "eposta": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "telefon": re.compile(r"\b0?5\d{2}[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}\b"),
    "iban": re.compile(r"\bTR\d{24}\b"),
}
_ONBIRLI = re.compile(r"\b\d{11}\b")


def _tckn_gecerli(sayi: str) -> bool:
    """T.C. kimlik no resmî checksum doğrulaması (yalnızca geçerli olan PII'dir)."""
    if len(sayi) != 11 or not sayi.isdigit() or sayi[0] == "0":
        return False
    d = [int(c) for c in sayi]
    hane10 = ((sum(d[0:9:2]) * 7) - sum(d[1:8:2])) % 10
    hane11 = sum(d[:10]) % 10
    return d[9] == hane10 and d[10] == hane11


def kacak_olc(anonim_metin: str) -> Dict[str, int]:
    """Maskelenmeden kalmış PII desenlerini kategori bazında sayar.

    Returns:
        {eposta, telefon, iban, tckn, toplam} — toplam 0 ise sızıntı yok.
    """
    kacaklar: Dict[str, int] = {}
    metin = anonim_metin or ""
    for ad, desen in _DESENLER.items():
        kacaklar[ad] = len(desen.findall(metin))
    kacaklar["tckn"] = sum(1 for m in _ONBIRLI.findall(metin) if _tckn_gecerli(m))
    kacaklar["toplam"] = sum(v for k, v in kacaklar.items() if k != "toplam")
    return kacaklar
