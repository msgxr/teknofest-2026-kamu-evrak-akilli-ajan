"""
Taslak Kalite Hakemi — üretici ajandan bağımsız kalite değerlendirmesi.

Üretilen resmî yazı taslağını "üretici ajanı ayrı bir denetçi ajan
kontrol eder" desenine uygun biçimde puanlar (Nguyen vd. 2025,
arXiv:2511.10925 doğrulayıcı-ajan yaklaşımına paralel). İki yol vardır
ve İKİSİ DE AYNI 0-100 ölçeğine normalize edilir:

    1. LLM-as-judge (opsiyonel): erişilebilir bir LLM varsa üslup/yapı/
       kapanış/açıklık boyutları rubrikle puanlatılır.
    2. Kural tabanlı hakem (çekirdek, her zaman çalışır): biçim skoru,
       üslup sinyalleri (birinci şahıs anlatı, yabancı kelime, kapanış
       ailesi) ve mevzuat temellilik bileşenlerinden hesaplanır.

Mevzuat temellilik (RAGAS'ın "groundedness" fikrinin saf Python
karşılığı) HER İKİ yolda da kural tabanlı hesaplanır: taslakta atıf
yapılan mevzuat, mevzuat önerici ajanın (mutlak ölçekli) benzerlik
skorlarıyla desteklenmeli ve öneri listesinde bulunmalıdır — listede
olmayan atıf halüsinasyon işareti sayılır ve ağır cezalandırılır.

Şartname Referansı (Görev 2): "Yazının ... resmî yazışma kurallarına
uygunluğunun denetlenmesi"; puan tablosunda "özetleme + yazı şablonu
kalitesi" kanıtı.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from src.utils.turkish_nlp import turkish_lower

logger = logging.getLogger("kamu_evrak_ajan.taslak_hakemi")

# Bileşen ağırlıkları (toplam 1.0): biçim, üslup, mevzuat temellilik
AGIRLIK_BICIM = 0.4
AGIRLIK_USLUP = 0.3
AGIRLIK_TEMELLILIK = 0.3

# LLM-as-judge yolunda LLM rubrik ortalamasının ağırlığı; mevzuat
# temellilik bileşeni her iki yolda da deterministik (kural) kalır —
# temellilik yargısı LLM'e bırakılırsa halüsinasyon halüsinasyonla
# denetlenmiş olur.
AGIRLIK_LLM = 0.7

# Üslup cezaları (100 üzerinden düşülür)
CEZA_BIRINCI_SAHIS = 15   # cümle başına (azami CEZA_BIRINCI_SAHIS_AZAMI)
CEZA_BIRINCI_SAHIS_AZAMI = 45
CEZA_YABANCI_KELIME = 10  # kelime başına (azami CEZA_YABANCI_AZAMI)
CEZA_YABANCI_AZAMI = 30
CEZA_KAPANIS_YOK = 25

# Temellilik puanları
TEMELLILIK_GENEL_ATIF = 70    # özgül atıf yok, genel "ilgili mevzuat" ifadesi
TEMELLILIK_UYDURMA_ATIF = 10  # öneri listesinde olmayan atıf (halüsinasyon işareti)
TEMELLILIK_ZAYIF_ESLESME = 40  # zayıf-eşleşme işaretli öneriye atıf
# Atıf edilen önerinin mutlak benzerliği bu değere ulaşınca tam puan
# (taslak ajanının atıf eşiğiyle aynı: MEVZUAT_ATIF_ESIGI)
TEMELLILIK_TAM_PUAN_BENZERLIK = 0.6

# Uygun kapanış ifadeleri ailesi (Yön. 2646 m.16/12)
_KAPANIS_AILESI = ("arz ederim", "rica ederim", "saygılarımla",
                   "bilgilerinize sunulur", "arz olunur")

# Taslak metnindeki mevzuat atıflarını yakalar: "3071 Sayılı ... Kanun(u)"
# veya "... Hakkında Yönetmelik" biçimli ad öbekleri
_MEVZUAT_ATIF_DESENI = re.compile(
    r"\b\d{4}\s+[Ss]ayılı\s+[^,.;\n]{3,80}?[Kk]anun\w*"
    r"|[A-ZÇĞİÖŞÜ][^,.;\n]{5,90}?[Yy]önetmeli\w+"
)


def _sinirla(deger: float) -> int:
    """Puanı [0, 100] tamsayı aralığına kırpar."""
    return int(round(max(0.0, min(100.0, deger))))


def _uslup_puani(taslak: str, notlar: List[str]) -> int:
    """
    Üslup bileşenini (0-100) hesaplar: birinci şahıs anlatı, yabancı
    kelime ve kapanış ifadesi ailesi sinyalleriyle.

    Birinci şahıs ve yabancı kelime desenleri taslak ajanının test
    edilmiş tanımlarından gelir; içe aktarma modül-yükleme döngüsünü
    önlemek için çağrı anında (lazy) yapılır — hakemi çağıran zaten
    taslak ajanı olduğundan modül bu noktada yüklüdür.
    """
    from src.agents.draft_writer_agent import (
        _BIRINCI_SAHIS_EK,
        _BIRINCI_SAHIS_KELIMELER,
        _BIRINCI_SAHIS_KOSAC,
        _YABANCI_KELIME_DESENI,
    )

    puan = 100.0
    low = turkish_lower(taslak)

    # Birinci şahıs anlatı: resmî yazı üçüncü şahıs anlatımla yazılır
    birinci_sahis = 0
    for cumle in re.split(r"(?<=[.!?])\s+", low):
        kelimeler = re.findall(r"[a-zçğıöşü]+", cumle)
        if not kelimeler:
            continue
        # "arz ederim / rica ederim" kapanışları birinci şahıs sayılmaz
        if any(k in cumle for k in _KAPANIS_AILESI):
            continue
        zamir = any(k in _BIRINCI_SAHIS_KELIMELER for k in kelimeler)
        ekli = any(
            _BIRINCI_SAHIS_EK.search(k) or _BIRINCI_SAHIS_KOSAC.search(k)
            for k in kelimeler[-3:]
        )
        if zamir and ekli:
            birinci_sahis += 1
    if birinci_sahis:
        puan -= min(CEZA_BIRINCI_SAHIS_AZAMI, birinci_sahis * CEZA_BIRINCI_SAHIS)
        notlar.append(
            f"Üslup: {birinci_sahis} cümlede birinci şahıs anlatı işareti "
            "(resmî yazı üçüncü şahıs anlatımla yazılır)."
        )

    yabanci = sorted({
        m.group(1).lower() if m.groups() and m.group(1) else m.group(0).lower()
        for m in _YABANCI_KELIME_DESENI.finditer(taslak)
    })
    if yabanci:
        puan -= min(CEZA_YABANCI_AZAMI, len(yabanci) * CEZA_YABANCI_KELIME)
        notlar.append(f"Üslup: yabancı kelime kullanımı ({', '.join(yabanci)}).")

    if not any(k in low for k in _KAPANIS_AILESI):
        puan -= CEZA_KAPANIS_YOK
        notlar.append("Üslup: uygun kapanış ifadesi (arz/rica/saygı) bulunamadı.")

    return _sinirla(puan)


def _temellilik_puani(
    taslak: str, matches: List[dict], notlar: List[str]
) -> int:
    """
    Mevzuat temellilik bileşenini (0-100) hesaplar.

    Taslaktaki mevzuat atıfları, önerici ajanın listesiyle karşılaştırılır:
    listede olmayan atıf halüsinasyon işareti sayılır; listedeki atıfın
    puanı mutlak benzerlik skoruyla orantılıdır; hiç özgül atıf yoksa
    (genel "ilgili mevzuat" ifadesi) nötr-dürüst bir puan verilir.
    """
    matches = [m for m in (matches or []) if isinstance(m, dict)]
    # Mevzuat adları taslakta satır sonuna sarabilir; atıf araması tek
    # satıra normalize edilmiş metin üzerinde yapılır
    duz_metin = re.sub(r"\s+", " ", taslak)
    atiflar = [a.strip() for a in _MEVZUAT_ATIF_DESENI.findall(duz_metin)]

    if not atiflar:
        notlar.append(
            "Temellilik: özgül mevzuat atfı yok (genel ifade) — yanlış atıf "
            "riski de yok."
        )
        return TEMELLILIK_GENEL_ATIF

    puanlar: List[float] = []
    for atif in atiflar:
        atif_low = turkish_lower(atif)
        eslesen = None
        for m in matches:
            baslik_low = turkish_lower(str(m.get("baslik") or ""))
            if not baslik_low:
                continue
            if atif_low in baslik_low or baslik_low in atif_low:
                eslesen = m
                break
        if eslesen is None:
            puanlar.append(TEMELLILIK_UYDURMA_ATIF)
            notlar.append(
                f"Temellilik: '{atif}' atfı mevzuat önerici listesinde YOK — "
                "olası halüsinasyon; taslak insan kontrolünden geçirilmeli."
            )
            continue
        if eslesen.get("zayif_esleme"):
            puanlar.append(TEMELLILIK_ZAYIF_ESLESME)
            notlar.append(
                f"Temellilik: '{atif}' zayıf-eşleşme işaretli öneriye dayanıyor."
            )
            continue
        benzerlik = float(eslesen.get("benzerlik") or 0.0)
        puanlar.append(
            100.0 * min(1.0, benzerlik / TEMELLILIK_TAM_PUAN_BENZERLIK)
        )

    return _sinirla(sum(puanlar) / len(puanlar))


def _llm_rubrik(taslak: str, llm: Any) -> Optional[int]:
    """
    LLM-as-judge rubriği: üslup/yapı/kapanış/açıklık boyutlarının
    0-100 ortalamasını döndürür; her hata durumunda None (kural yolu).
    """
    try:
        sonuc = llm.generate_json(
            prompt=(
                "Aşağıdaki resmî yazı taslağını dört boyutta 0-100 arası "
                "puanla. Boyutlar: uslup (resmî üçüncü şahıs anlatım, TDK "
                "uyumu, gereksiz yabancı kelime yokluğu), yapi (başlık/sayı/"
                "konu/muhatap/metin/imza düzeni), kapanis (arz/rica/saygı "
                "ifadesinin muhataba uygunluğu), aciklik (anlaşılırlık, "
                "gereksiz tekrar yokluğu). Yalnızca JSON döndür.\n\n"
                f"TASLAK:\n{taslak[:3000]}"
            ),
            schema_hint=(
                '{"uslup": 0-100, "yapi": 0-100, "kapanis": 0-100, '
                '"aciklik": 0-100}'
            ),
            system_prompt=(
                "Sen resmî yazışma kurallarına hâkim, titiz bir kalite "
                "değerlendiricisisin. Yalnızca istenen JSON'u üretirsin."
            ),
        )
        boyutlar = [
            float(sonuc.get(k)) for k in ("uslup", "yapi", "kapanis", "aciklik")
            if isinstance(sonuc.get(k), (int, float))
        ]
        if not boyutlar:
            return None
        return _sinirla(sum(boyutlar) / len(boyutlar))
    except Exception as e:
        logger.warning(f"LLM hakem puanlaması başarısız, kural yoluna dönülüyor: {e}")
        return None


def taslak_puanla(
    taslak: str,
    format_validation: Optional[dict] = None,
    legislation_matches: Optional[List[dict]] = None,
    llm: Any = None,
) -> Dict[str, Any]:
    """
    Taslağı 0-100 ölçeğinde puanlar.

    Args:
        taslak: Üretilen resmî yazı taslağı metni
        format_validation: Format öz-denetim sonucu ({"skor": 0-1, ...})
        legislation_matches: Mevzuat önerici ajanın öneri listesi
            (temellilik denetimi için)
        llm: LLM sarmalayıcısı; None verilirse varsayılan sarmalayıcı
            denenir, erişilebilir değilse kural yoluna düşülür

    Returns:
        {"puan": 0-100, "yontem": "llm_hakem"|"kural_hakem",
         "bilesenler": {"bicim", "uslup", "mevzuat_temellilik"},
         "notlar": [...]}
    """
    taslak = str(taslak or "")
    notlar: List[str] = []

    fv = format_validation if isinstance(format_validation, dict) else {}
    bicim = _sinirla(float(fv.get("skor") or 0.0) * 100.0)
    uslup = _uslup_puani(taslak, notlar)
    temellilik = _temellilik_puani(taslak, legislation_matches or [], notlar)

    if llm is None:
        try:
            from src.models.llm_wrapper import get_default_llm

            aday = get_default_llm()
            llm = aday if aday.is_available() else None
        except Exception:
            llm = None

    yontem = "kural_hakem"
    if llm is not None:
        llm_puan = _llm_rubrik(taslak, llm)
        if llm_puan is not None:
            yontem = "llm_hakem"
            # Format (biçim) skoru LLM yolunda da HESABA KATILIR: yapısal olarak
            # bozuk bir taslak (düşük biçim), LLM öznel yüksek verse bile yüksek
            # puan alamaz — deterministik madde-referanslı biçim güvencesi korunur.
            kalan = 1.0 - AGIRLIK_LLM
            puan = _sinirla(
                AGIRLIK_LLM * llm_puan + kalan * 0.5 * bicim + kalan * 0.5 * temellilik
            )
            return {
                "puan": puan,
                "yontem": yontem,
                "bilesenler": {
                    "llm_rubrik": llm_puan,
                    "bicim": bicim,
                    "uslup": uslup,
                    "mevzuat_temellilik": temellilik,
                },
                "notlar": notlar,
            }

    puan = _sinirla(
        AGIRLIK_BICIM * bicim
        + AGIRLIK_USLUP * uslup
        + AGIRLIK_TEMELLILIK * temellilik
    )
    return {
        "puan": puan,
        "yontem": yontem,
        "bilesenler": {
            "bicim": bicim,
            "uslup": uslup,
            "mevzuat_temellilik": temellilik,
        },
        "notlar": notlar,
    }
