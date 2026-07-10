"""
Yazı Taslak Oluşturma Agent — Resmi yazı taslağı üretme.

Şartname Referansı (Görev 2):
    - "Üst yazı, cevap yazısı, bilgilendirme metni veya alternatif resmi yazışma türü için uygun bir taslak oluşturması"
    - "Taslak metnin resmi üsluba uygun olmasını sağlaması"
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.draft_writer")


# Resmi yazı şablonları
YAZI_SABLONLARI = {
    "ust_yazi": """T.C.
{kurum_adi}
{birim_adi}

Sayı   : {sayi}
Konu   : {konu}

{muhatap} MAKAMINA

İlgi   : {ilgi}

{metin}

{ek_bilgi}

                                                        {imza_sahibi}
                                                        {unvan}

Ek     : {ekler}
Dağıtım: {dagitim}
""",
    "cevap_yazisi": """T.C.
{kurum_adi}
{birim_adi}

Sayı   : {sayi}
Konu   : {konu}

{muhatap} MAKAMINA

İlgi   : {ilgi}

İlgide kayıtlı yazınız incelenmiş olup, konu hakkında aşağıdaki hususlar bilgilerinize sunulur:

{metin}

Bilgilerinize arz ederim.

                                                        {imza_sahibi}
                                                        {unvan}
""",
    "bilgilendirme": """T.C.
{kurum_adi}
{birim_adi}

Sayı   : {sayi}
Konu   : {konu}

{muhatap}

{metin}

Bilgilerinize rica ederim.

                                                        {imza_sahibi}
                                                        {unvan}

Dağıtım: {dagitim}
""",
}


class DraftWriterAgent:
    """
    Yazı taslak oluşturma agent'ı.

    Evrak türüne ve içeriğine göre resmi üsluba uygun
    yazı taslağı oluşturur.
    """

    def __init__(self) -> None:
        logger.info("Yazı Taslak Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Resmi yazı taslağı oluşturur."""
        evrak_turu = state.classification.get("tur", "ust_yazi")
        text = state.raw_text
        extracted = state.extracted_info
        legislation = state.legislation_matches

        # Uygun yazı türünü belirle
        yazi_turu = self._determine_draft_type(evrak_turu)
        state.draft_type = yazi_turu

        # Taslak oluştur
        draft = self._generate_draft(yazi_turu, text, extracted, legislation)
        state.draft_text = draft

        logger.info(f"Yazı taslağı oluşturuldu: {yazi_turu} ({len(draft)} karakter)")
        return state

    def _determine_draft_type(self, evrak_turu: str) -> str:
        """Gelen evrak türüne göre oluşturulacak yazı türünü belirler."""
        type_mapping = {
            "dilekce": "cevap_yazisi",
            "ust_yazi": "cevap_yazisi",
            "cevap_yazisi": "bilgilendirme",
            "bilgilendirme": "ust_yazi",
            "tutanak": "ust_yazi",
            "rapor": "ust_yazi",
            "genelge": "bilgilendirme",
            "onayli_belge": "bilgilendirme",
            "diger": "ust_yazi",
        }
        return type_mapping.get(evrak_turu, "ust_yazi")

    def _generate_draft(
        self,
        yazi_turu: str,
        text: str,
        extracted: dict,
        legislation: list,
    ) -> str:
        """
        Yazı taslağı oluşturur.

        Önce LLM ile dener, başarısız olursa şablon tabanlı oluşturur.
        """
        try:
            return self._generate_with_llm(yazi_turu, text, extracted, legislation)
        except Exception as e:
            logger.warning(f"LLM taslak oluşturulamadı, şablon kullanılıyor: {e}")
            return self._generate_from_template(yazi_turu, extracted)

    def _generate_with_llm(
        self,
        yazi_turu: str,
        text: str,
        extracted: dict,
        legislation: list,
    ) -> str:
        """LLM ile yazı taslağı oluşturur."""
        from src.models.llm_wrapper import LLMWrapper

        llm = LLMWrapper()

        mevzuat_str = "\n".join(
            f"- {m['baslik']}" for m in legislation[:3]
        ) if legislation else "Belirtilmemiş"

        prompt = f"""Aşağıdaki gelen evrak metnine uygun bir resmi {yazi_turu.replace('_', ' ')} taslağı oluştur.

Gelen Evrak Metni:
---
{text[:3000]}
---

Çıkarılan Bilgiler:
- Konu: {extracted.get('konu', 'Belirtilmemiş')}
- Muhatap: {extracted.get('muhatap', 'Belirtilmemiş')}
- Tarihler: {', '.join(extracted.get('tarihler', ['Belirtilmemiş']))}

İlgili Mevzuat:
{mevzuat_str}

Kurallar:
- Resmi yazışma kurallarına uygun format kullan
- T.C. başlığı ile başla
- Sayı, Konu, İlgi alanlarını ekle
- Resmi ve nesnel Türkçe kullan
- "Arz ederim" veya "Rica ederim" ile bitir
- Tarih: {datetime.now().strftime('%d/%m/%Y')}
"""
        return llm.generate(prompt)

    def _generate_from_template(self, yazi_turu: str, extracted: dict) -> str:
        """Şablon tabanlı yazı taslağı oluşturur."""
        template = YAZI_SABLONLARI.get(yazi_turu, YAZI_SABLONLARI["ust_yazi"])

        now = datetime.now()

        return template.format(
            kurum_adi="[KURUM ADI]",
            birim_adi="[BİRİM ADI]",
            sayi=f"E-{now.strftime('%Y%m%d')}-001",
            konu=extracted.get("konu", "[KONU]"),
            muhatap=extracted.get("muhatap", "[MUHATAP]"),
            ilgi="[İLGİ YAZISI TARİH VE SAYISI]",
            metin="[YAZI METNİ BURAYA YAZILACAKTIR]",
            ek_bilgi="",
            imza_sahibi="[İMZA SAHİBİ]",
            unvan="[UNVAN]",
            ekler="[VARSA EKLER]",
            dagitim="Gereği / Bilgi",
        )
