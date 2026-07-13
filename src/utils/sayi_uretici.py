# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Kurgu-DETSİS tabanlı belge sayısı üretici ve doğrulayıcı.

2646 sayılı Yönetmelik m.11/1-2'deki sayı biçimini üretir:
    <ortam>-<Devlet Teşkilatı Numarası>-<standart dosya planı kodu>-<kayıt no>
    örnek biçim (m.11/2): E-67915368-903.07.02-4752

DÜRÜSTLÜK NOTLARI:
    - Üretilen Devlet Teşkilatı Numaraları KURGUDUR: kurum adından
      deterministik türetilir (aynı kurgu kurum → aynı kod), format
      uyumludur ancak DETSİS'teki gerçek bir idareyle eşleşme
      amaçlanmamıştır (bkz. data/README.md KVKK/kurgu notu).
    - Tür → dosya planı kodu eşlemesi de KURGUDUR; Devlet Arşivleri
      Başkanlığı Standart Dosya Planı'nın gerçek konu kodlarıyla birebir
      örtüşme iddia edilmez (format kanıtı amaçlıdır).
    - Taslak yazılara sayı YAZILMAZ (gerçek sayıyı EBYS verir); bu modül
      üstverideki "sayi_onerisi" alanını ve testleri besler.

Şartname Referansı (Görev 2): resmî yazışma kurallarına uygun taslak /
EBYS entegrasyon vizyonu.
"""

from __future__ import annotations

import hashlib
from typing import Optional

from src.utils.yazisma_desenleri import SAYI_BICIM_TAM

# Ortam ibareleri (m.11/1): E = elektronik, Z = zorunlu hâl (güvenli
# elektronik imza ile fiziksel), O = olağanüstü durum
GECERLI_ORTAMLAR = ("E", "Z", "O")

# Evrak türü → KURGU dosya planı kodu (format uyumlu; gerçek SDP
# eşlemesi iddia edilmez)
KURGU_SDP_KODLARI = {
    "dilekce": "622.01",
    "ust_yazi": "000.01",
    "cevap_yazisi": "622.02",
    "bilgilendirme": "010.07",
    "tutanak": "030.03",
    "rapor": "040.01",
    "genelge": "010.06",
    "onayli_belge": "020.01",
}
VARSAYILAN_SDP_KODU = "000.00"


def kurgu_detsis_no(kurum_adi: str) -> str:
    """
    Kurum adından KURGU, deterministik 8 haneli Devlet Teşkilatı Numarası
    türetir (aynı ad → aynı kod; ilk hane 0 olmaz).

    Determinizm sha256 ile sağlanır (kriptografik amaç yoktur); gerçek
    DETSİS kayıtlarıyla eşleşme amaçlanmamıştır.
    """
    ozet = hashlib.sha256((kurum_adi or "").strip().encode("utf-8")).hexdigest()
    deger = int(ozet[:12], 16) % 90_000_000 + 10_000_000
    return str(deger)


def sayi_uret(
    kurum_adi: str,
    evrak_turu: str = "",
    sira_no: int = 1,
    ortam: str = "E",
    sdp_kodu: Optional[str] = None,
) -> str:
    """
    m.11 biçiminde kurgu belge sayısı üretir.

    Args:
        kurum_adi: Kurgu DETSİS kodunun türetileceği kurum adı
        evrak_turu: KURGU_SDP_KODLARI'ndan dosya planı kodu seçimi için
        sira_no: Belge kayıt numarası (pozitif tamsayı)
        ortam: "E" / "Z" / "O" (m.11/1); geçersiz değerde "E" kullanılır
        sdp_kodu: Verilirse tür eşlemesi yerine doğrudan kullanılır

    Returns:
        "E-XXXXXXXX-XXX.XX-N" biçiminde sayı dizesi
    """
    ortam = ortam if ortam in GECERLI_ORTAMLAR else "E"
    kod = sdp_kodu or KURGU_SDP_KODLARI.get(evrak_turu, VARSAYILAN_SDP_KODU)
    sira = max(1, int(sira_no))
    return f"{ortam}-{kurgu_detsis_no(kurum_adi)}-{kod}-{sira}"


def sayi_dogrula(sayi: str) -> bool:
    """Sayının m.11 biçimine tam uyup uymadığını döndürür."""
    return bool(SAYI_BICIM_TAM.match((sayi or "").strip()))
