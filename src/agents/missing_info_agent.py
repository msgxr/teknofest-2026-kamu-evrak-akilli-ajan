"""
Eksik Bilgi Tespit Agent — Evrakta bulunması gereken eksik bilgileri tespit etme.

Şartname Referansı (Görev 1):
    "Evrakta bulunması gereken ancak eksik olan bilgileri tespit edebilme"
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.missing_info")

# Evrak türüne göre zorunlu alanlar
ZORUNLU_ALANLAR = {
    "dilekce": [
        "tarih", "ad_soyad", "tc_kimlik", "adres", "konu", "talep_metni", "imza",
    ],
    "ust_yazi": [
        "tarih", "sayi", "konu", "muhatap", "ilgi", "metin", "imza", "kurum_bilgisi",
    ],
    "cevap_yazisi": [
        "tarih", "sayi", "konu", "muhatap", "ilgi", "cevap_metni", "imza",
    ],
    "bilgilendirme": [
        "tarih", "sayi", "konu", "metin", "dagitim", "imza",
    ],
    "tutanak": [
        "tarih", "saat", "yer", "katilimcilar", "gundem", "kararlar", "imzalar",
    ],
    "rapor": [
        "tarih", "baslik", "hazirlayan", "ozet", "bulgular", "sonuc", "imza",
    ],
    "genelge": [
        "tarih", "sayi", "konu", "metin", "dagitim",
    ],
    "onayli_belge": [
        "tarih", "sayi", "onaylayan", "onay_metni",
    ],
    "diger": [
        "tarih", "konu", "metin",
    ],
}


class MissingInfoAgent:
    """
    Eksik bilgi tespit agent'ı.

    Evrak türüne göre bulunması gereken zorunlu alanları kontrol eder
    ve eksik olanları raporlar.
    """

    def __init__(self) -> None:
        logger.info("Eksik Bilgi Tespit Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Evraktaki eksik bilgileri tespit eder."""
        evrak_turu = state.classification.get("tur", "diger")
        text = state.raw_text
        extracted_info = state.extracted_info

        zorunlu = ZORUNLU_ALANLAR.get(evrak_turu, ZORUNLU_ALANLAR["diger"])
        eksikler = []

        for alan in zorunlu:
            if not self._check_field_exists(alan, text, extracted_info):
                eksikler.append({
                    "alan": alan,
                    "aciklama": self._get_field_description(alan),
                    "oncelik": self._get_field_priority(alan),
                })

        state.missing_info = eksikler

        if eksikler:
            logger.warning(f"Eksik bilgi tespit edildi: {len(eksikler)} alan")
            for e in eksikler:
                logger.debug(f"  - {e['alan']}: {e['aciklama']}")
        else:
            logger.info("Tüm zorunlu alanlar mevcut.")

        return state

    def _check_field_exists(self, field: str, text: str, extracted: dict) -> bool:
        """Bir alanın evrakta mevcut olup olmadığını kontrol eder."""
        field_checks = {
            "tarih": lambda: bool(extracted.get("tarihler")),
            "sayi": lambda: "sayı" in text.lower() or "no:" in text.lower(),
            "konu": lambda: bool(extracted.get("konu")),
            "muhatap": lambda: bool(extracted.get("muhatap")),
            "imza": lambda: "imza" in text.lower() or any(
                k in text.lower() for k in ["müsteşar", "müdür", "başkan", "vali"]
            ),
            "ad_soyad": lambda: bool(extracted.get("kisi_adlari")),
            "tc_kimlik": lambda: bool(
                __import__("re").search(r"\d{11}", text)
            ),
            "adres": lambda: any(
                k in text.lower() for k in ["adres", "mahalle", "cadde", "sokak"]
            ),
            "ilgi": lambda: "ilgi" in text.lower(),
            "metin": lambda: len(text.strip()) > 100,
            "talep_metni": lambda: len(text.strip()) > 50,
            "cevap_metni": lambda: len(text.strip()) > 50,
            "dagitim": lambda: "dağıtım" in text.lower() or "gereği" in text.lower(),
            "kurum_bilgisi": lambda: bool(extracted.get("kurum_adlari")),
        }

        checker = field_checks.get(field)
        if checker:
            return checker()

        # Genel kontrol: alan adı metinde geçiyor mu
        return field.replace("_", " ") in text.lower()

    def _get_field_description(self, field: str) -> str:
        """Bir alan için açıklama döndürür."""
        descriptions = {
            "tarih": "Evrak tarihi belirtilmemiş",
            "sayi": "Evrak sayı/referans numarası eksik",
            "konu": "Konu alanı belirtilmemiş",
            "muhatap": "Muhatap/alıcı bilgisi eksik",
            "imza": "İmza bilgisi bulunamadı",
            "ad_soyad": "Başvuru sahibinin adı soyadı eksik",
            "tc_kimlik": "T.C. Kimlik Numarası belirtilmemiş",
            "adres": "Adres bilgisi eksik",
            "ilgi": "İlgi (referans) bilgisi eksik",
            "dagitim": "Dağıtım listesi belirtilmemiş",
            "kurum_bilgisi": "Kurum bilgisi eksik",
        }
        return descriptions.get(field, f"'{field}' alanı eksik")

    def _get_field_priority(self, field: str) -> str:
        """Bir alan için öncelik seviyesi döndürür."""
        critical = {"tarih", "sayi", "konu", "imza", "ad_soyad"}
        important = {"muhatap", "ilgi", "tc_kimlik", "kurum_bilgisi"}

        if field in critical:
            return "kritik"
        elif field in important:
            return "önemli"
        return "bilgi"
