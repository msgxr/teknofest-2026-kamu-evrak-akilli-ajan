"""
Kullanıcı Bilgilendirme Agent — Kullanıcıya süreç bilgisi sunma ve eksik bilgi talebi.

Şartname Referansı (Görev 2):
    - "Kullanıcıya süreç hakkında açık ve anlaşılır bilgilendirme sunması"
    - "Gerekli durumlarda eksik bilgi talep edebilmesi"
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.user_info")


class UserInfoAgent:
    """
    Kullanıcı bilgilendirme agent'ı.

    İşlem sonuçlarını kullanıcıya anlaşılır biçimde sunar
    ve gerekli durumlarda eksik bilgi talep eder.
    """

    def __init__(self) -> None:
        logger.info("Kullanıcı Bilgilendirme Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Kullanıcı bilgilendirme mesajları oluşturur."""
        notifications = []

        # 1. İşlem durumu bildirimi
        notifications.append(self._create_status_notification(state))

        # 2. Eksik bilgi bildirimleri
        if state.missing_info:
            notifications.append(self._create_missing_info_notification(state.missing_info))

        # 3. Mevzuat uyarıları
        if state.legislation_matches:
            notifications.append(self._create_legislation_notification(state.legislation_matches))

        # 4. Yönlendirme bilgisi
        if state.routing_suggestion:
            notifications.append(self._create_routing_notification(state.routing_suggestion))

        # 5. Hata bildirimleri
        if state.errors:
            notifications.append(self._create_error_notification(state.errors))

        state.user_notifications = [n for n in notifications if n is not None]
        logger.info(f"{len(state.user_notifications)} bilgilendirme mesajı oluşturuldu.")
        return state

    def _create_status_notification(self, state: "AgentState") -> dict:
        """İşlem durumu bildirimi oluşturur."""
        completed = sum(
            1 for s in state.processing_steps if s.get("status") == "success"
        )
        total = len(state.processing_steps)
        failed = sum(
            1 for s in state.processing_steps if s.get("status") == "error"
        )

        return {
            "tip": "durum",
            "baslik": "İşlem Durumu",
            "mesaj": (
                f"Evrak işleme tamamlandı.\n"
                f"• Başarılı adımlar: {completed}/{total}\n"
                f"• Başarısız adımlar: {failed}/{total}\n"
                f"• Evrak türü: {state.classification.get('tur_adi', 'Belirsiz')}"
            ),
            "seviye": "bilgi" if failed == 0 else "uyari",
        }

    def _create_missing_info_notification(self, missing_info: list) -> dict:
        """Eksik bilgi bildirimi oluşturur."""
        critical = [m for m in missing_info if m.get("oncelik") == "kritik"]
        important = [m for m in missing_info if m.get("oncelik") == "önemli"]
        info_level = [m for m in missing_info if m.get("oncelik") == "bilgi"]

        mesaj_parts = ["Evrakta aşağıdaki eksik bilgiler tespit edilmiştir:\n"]

        if critical:
            mesaj_parts.append("🔴 KRİTİK:")
            for m in critical:
                mesaj_parts.append(f"  • {m['aciklama']}")

        if important:
            mesaj_parts.append("🟡 ÖNEMLİ:")
            for m in important:
                mesaj_parts.append(f"  • {m['aciklama']}")

        if info_level:
            mesaj_parts.append("🔵 BİLGİ:")
            for m in info_level:
                mesaj_parts.append(f"  • {m['aciklama']}")

        return {
            "tip": "eksik_bilgi",
            "baslik": "Eksik Bilgi Tespiti",
            "mesaj": "\n".join(mesaj_parts),
            "seviye": "uyari" if critical else "bilgi",
            "aksiyonlar": [
                {"tip": "bilgi_talebi", "alan": m["alan"], "aciklama": m["aciklama"]}
                for m in critical + important
            ],
        }

    def _create_legislation_notification(self, legislation: list) -> dict:
        """Mevzuat uyarı bildirimi oluşturur."""
        mesaj_parts = ["Bu evrakla ilgili mevzuat önerileri:\n"]
        for i, leg in enumerate(legislation[:3], 1):
            mesaj_parts.append(
                f"{i}. {leg.get('baslik', 'Bilinmiyor')}\n"
                f"   {leg.get('icerik_ozeti', '')[:100]}"
            )

        return {
            "tip": "mevzuat",
            "baslik": "İlgili Mevzuat",
            "mesaj": "\n".join(mesaj_parts),
            "seviye": "bilgi",
        }

    def _create_routing_notification(self, routing: dict) -> dict:
        """Yönlendirme bilgisi bildirimi oluşturur."""
        mesaj = (
            f"Önerilen Birim: {routing.get('birim', 'Belirsiz')}\n"
            f"Gerekçe: {routing.get('gerekce', '')}\n"
            f"Güven: %{routing.get('guven', 0) * 100:.0f}"
        )

        if routing.get("alternatifler"):
            mesaj += "\n\nAlternatif birimler:"
            for alt in routing["alternatifler"]:
                mesaj += f"\n  • {alt['birim']}"

        return {
            "tip": "yonlendirme",
            "baslik": "Birim Yönlendirme Önerisi",
            "mesaj": mesaj,
            "seviye": "bilgi",
        }

    def _create_error_notification(self, errors: list) -> dict:
        """Hata bildirimi oluşturur."""
        return {
            "tip": "hata",
            "baslik": "İşlem Hataları",
            "mesaj": "Aşağıdaki hata(lar) oluştu:\n" + "\n".join(f"• {e}" for e in errors),
            "seviye": "hata",
        }
