"""
Kullanıcı Bilgilendirme Agent — Kullanıcıya süreç bilgisi sunma ve eksik bilgi talebi.

Şartname Referansı (Görev 2):
    - "Kullanıcıya süreç hakkında açık ve anlaşılır bilgilendirme sunması"
    - "Gerekli durumlarda eksik bilgi talep edebilmesi": kritik ve önemli
      öncelikli her eksik alan için kullanıcıya sorulacak açık Türkçe soru
      state.clarification_requests içine yazılır; arayüzde "sistem eksik
      bilgi talep ediyor" olarak gösterilir.

Bildirim türleri:
    (0) akış uyarıları (koşullu kapılar: okunamayan metin, dil sezimi,
    düşük güven — orkestratörün workflow_warnings kayıtlarından üretilir),
    (1) süreç durumu, (2) eksik bilgi, (3) mevzuat, (4) yönlendirme,
    (5) hata, (6) sonraki adımlar (taslağın onaya sunulması, eksiklerin
    giderilmesi, birime sevk gibi somut adımlar).

Soru muhatabı ilkesi:
    Dilekçe/başvuru kaynaklı evrakta eksik bilgiler BAŞVURU SAHİBİNDEN,
    kurum içinde düzenlenen belge türlerinde (tutanak, rapor, onaylı
    belge, genelge) ise belgeyi DÜZENLEYEN BİRİMDEN talep edilir;
    tüm ifadeler buna göre koşullandırılır.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from src.agents.draft_writer_agent import DRAFT_TYPE_LABELS

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.user_info")

# Eksik alan → kullanıcıya sorulacak açık Türkçe soru
ALAN_SORULARI = {
    "tarih": "Evrakın düzenlenme tarihi nedir? (örn. 15.03.2026)",
    "sayi": "Evrakın sayı/referans numarası nedir?",
    "konu": "Evrakın konusu nedir? Kısaca belirtir misiniz?",
    "muhatap": "Evrakın muhatabı (gönderileceği kişi veya kurum) kimdir?",
    "imza": "Evrakı imzalayan kişinin adı, soyadı ve unvanı nedir?",
    "imzalar": "Tutanağı imzalayan katılımcıların ad-soyad ve unvanları nelerdir?",
    "ad_soyad": "Başvuru sahibinin adı ve soyadı nedir?",
    "tc_kimlik": "Başvuru sahibinin T.C. kimlik numarası nedir?",
    "adres": "Başvuru sahibinin tebligata esas açık adresi nedir?",
    "ilgi": "Bu evrakın ilgili olduğu önceki yazının tarihi ve sayısı nedir?",
    "kurum_bilgisi": "Evrakı gönderen kurum veya birim hangisidir?",
    "dagitim": "Yazının gönderileceği birimler (dağıtım listesi) hangileridir?",
    "saat": "Tutanağın düzenlendiği saat nedir?",
    "yer": "Tutanağın düzenlendiği yer neresidir?",
    "katilimcilar": "Toplantıya/işleme katılanlar kimlerdir?",
    "gundem": "Toplantının gündem maddeleri nelerdir?",
    "kararlar": "Toplantıda alınan kararlar nelerdir?",
    "hazirlayan": "Raporu hazırlayan kişi/birim kimdir?",
    "onaylayan": "Belgeyi onaylayan makam/kişi kimdir?",
}

# 3071 sayılı Dilekçe Hakkı Kanunu'na göre dilekçede zorunlu unsurlar
_DILEKCE_ZORUNLU_ALANLAR = {"ad_soyad", "adres", "imza", "tc_kimlik"}

# Kurum içinde düzenlenen belge türleri: bu evrakta bir "başvuru sahibi"
# yoktur; eksik bilgilerin muhatabı belgeyi DÜZENLEYEN BİRİMDİR.
_IC_BELGE_TURLERI = {"tutanak", "rapor", "onayli_belge", "genelge"}

# İç belge türlerinde soru ifadeleri düzenleyen birime göre koşullandırılır
# (genel sorulardaki "başvuru sahibi" ifadeleri bu türlerde kullanılmaz).
_IC_BELGE_ALAN_SORULARI = {
    "ad_soyad": "Belgeyi düzenleyen kişinin adı ve soyadı nedir?",
    "tc_kimlik": "Belgeyi düzenleyen kişinin T.C. kimlik numarası nedir?",
    "adres": "Belgeyi düzenleyen birimin yazışma adresi nedir?",
    "imza": "Belgeyi imzalayan yetkilinin adı, soyadı ve unvanı nedir?",
    "kurum_bilgisi": "Belgeyi düzenleyen kurum veya birim hangisidir?",
}


class UserInfoAgent:
    """
    Kullanıcı bilgilendirme agent'ı.

    İşlem sonuçlarını kullanıcıya anlaşılır biçimde sunar, somut sonraki
    adımları listeler ve eksik bilgiler için açık sorulardan oluşan
    bilgi taleplerini (clarification_requests) üretir.
    """

    def __init__(self) -> None:
        logger.info("Kullanıcı Bilgilendirme Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Kullanıcı bilgilendirme mesajları ve eksik bilgi talepleri oluşturur."""
        notifications = []

        # 0. Akış uyarıları (koşullu kapılar: okunamayan/kısa metin,
        #    dil sezimi, düşük güven) — kullanıcı önce bunları görmeli
        for uyari in (state.workflow_warnings or []):
            notifications.append({
                "tip": uyari.get("kod", "akis_uyarisi"),
                "baslik": uyari.get("baslik", "Uyarı"),
                "mesaj": uyari.get("mesaj", ""),
                "seviye": uyari.get("seviye", "uyari"),
            })

        # 1. İşlem durumu bildirimi
        notifications.append(self._create_status_notification(state))

        # 2. Eksik bilgi bildirimleri
        if state.missing_info:
            notifications.append(
                self._create_missing_info_notification(
                    state.missing_info, state.classification.get("tur", "")
                )
            )

        # 3. Mevzuat uyarıları
        if state.legislation_matches:
            notifications.append(self._create_legislation_notification(state.legislation_matches))

        # 4. Yönlendirme bilgisi
        if state.routing_suggestion:
            notifications.append(self._create_routing_notification(state.routing_suggestion))

        # 5. Hata bildirimleri
        if state.errors:
            notifications.append(self._create_error_notification(state.errors))

        # 6. Sonraki adımlar (somut süreç adımları)
        notifications.append(self._create_next_steps_notification(state))

        state.user_notifications = [n for n in notifications if n is not None]

        # Eksik bilgi talepleri (şartname: "eksik bilgi talep edebilmesi")
        state.clarification_requests = self._build_clarification_requests(
            state.missing_info, state.classification.get("tur", "")
        )

        logger.info(
            f"{len(state.user_notifications)} bilgilendirme mesajı, "
            f"{len(state.clarification_requests)} eksik bilgi talebi oluşturuldu."
        )
        return state

    # ------------------------------------------------------------------
    # Bildirimler
    # ------------------------------------------------------------------

    def _create_status_notification(self, state: "AgentState") -> dict:
        """İşlem durumu bildirimi oluşturur."""
        completed = sum(
            1 for s in state.processing_steps if s.get("status") == "success"
        )
        total = len(state.processing_steps)
        failed = sum(
            1 for s in state.processing_steps if s.get("status") == "error"
        )
        skipped = sum(
            1 for s in state.processing_steps if s.get("status") == "atlandi"
        )
        toplam_sure = sum(s.get("sure_saniye", 0) for s in state.processing_steps)

        bos_metin = any(
            u.get("kod") == "bos_metin" for u in (state.workflow_warnings or [])
        )
        durum_satiri = (
            "Evrak işlenemedi: metin okunamadı veya çok kısa."
            if bos_metin else "Evrak işleme tamamlandı."
        )

        mesaj = (
            f"{durum_satiri}\n"
            f"- Başarılı adımlar: {completed}/{total}\n"
            f"- Başarısız adımlar: {failed}/{total}\n"
        )
        if skipped:
            mesaj += f"- Atlanan adımlar: {skipped}/{total}\n"
        mesaj += (
            f"- Toplam süre: {toplam_sure:.2f} sn\n"
            f"- Evrak türü: {state.classification.get('tur_adi', 'Belirsiz')}"
        )
        if state.draft_type:
            mesaj += (
                f"\n- Üretilen taslak: "
                f"{DRAFT_TYPE_LABELS.get(state.draft_type, state.draft_type)}"
            )

        return {
            "tip": "durum",
            "baslik": "İşlem Durumu",
            "mesaj": mesaj,
            "seviye": "bilgi" if failed == 0 and not bos_metin else "uyari",
        }

    def _create_missing_info_notification(
        self, missing_info: list, evrak_turu: str = ""
    ) -> dict:
        """Eksik bilgi bildirimi oluşturur (muhatap ifadesi türe göre koşullu)."""
        critical = [m for m in missing_info if m.get("oncelik") == "kritik"]
        important = [m for m in missing_info if m.get("oncelik") == "önemli"]
        info_level = [m for m in missing_info if m.get("oncelik") == "bilgi"]

        mesaj_parts = ["Evrakta aşağıdaki eksik bilgiler tespit edilmiştir:\n"]

        if critical:
            mesaj_parts.append("KRİTİK:")
            for m in critical:
                mesaj_parts.append(f"  - {m['aciklama']}")

        if important:
            mesaj_parts.append("ÖNEMLİ:")
            for m in important:
                mesaj_parts.append(f"  - {m['aciklama']}")

        if info_level:
            mesaj_parts.append("BİLGİ:")
            for m in info_level:
                mesaj_parts.append(f"  - {m['aciklama']}")

        if critical:
            muhatap = (
                "belgeyi düzenleyen birime"
                if evrak_turu in _IC_BELGE_TURLERI else "başvuru sahibine"
            )
            mesaj_parts.append(
                f"\nKritik eksikler nedeniyle {muhatap} iletilmek üzere "
                "eksik bilgi talep yazısı hazırlanması önerilmiştir."
            )

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
        if routing.get("yontem"):
            mesaj += f"\nYöntem: {routing['yontem']}"

        if routing.get("alternatifler"):
            mesaj += "\n\nAlternatif birimler:"
            for alt in routing["alternatifler"]:
                mesaj += f"\n  - {alt['birim']} (skor: {alt.get('skor', '-')})"

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
            "mesaj": "Aşağıdaki hata(lar) oluştu:\n" + "\n".join(f"- {e}" for e in errors),
            "seviye": "hata",
        }

    def _create_next_steps_notification(self, state: "AgentState") -> Optional[dict]:
        """
        Sonraki adımlar bildirimi oluşturur.

        Kullanıcının süreçte atması gereken somut adımları sıralar:
        taslağın onaya sunulması, eksiklerin giderilmesi, birime sevk vb.
        Koşullu kapılar tetiklendiyse (okunamayan metin, dil uyarısı,
        düşük güven) adımlar buna göre uyarlanır.
        """
        uyari_kodlari = {
            u.get("kod") for u in (state.workflow_warnings or [])
        }

        # Kapı 1: okunamayan/çok kısa metinde tek anlamlı adım, geçerli
        # bir evrakla işlemin tekrarlanmasıdır.
        if "bos_metin" in uyari_kodlari:
            adimlar = [
                "Geçerli ve okunaklı bir evrak dosyası yükleyerek işlemi "
                "tekrarlayın.",
                "Evrak taranmış bir görüntüyse tarama kalitesini (çözünürlük, "
                "kontrast) kontrol edin.",
            ]
            mesaj = "Önerilen sonraki adımlar:\n" + "\n".join(
                f"{i}. {adim}" for i, adim in enumerate(adimlar, 1)
            )
            return {
                "tip": "sonraki_adimlar",
                "baslik": "Sonraki Adımlar",
                "mesaj": mesaj,
                "seviye": "uyari",
                "adimlar": adimlar,
            }

        adimlar = []

        # İç belgede eksiklerin muhatabı düzenleyen birimdir (başvuru sahibi değil)
        ic_belge = state.classification.get("tur", "") in _IC_BELGE_TURLERI

        kritik_var = any(
            m.get("oncelik") == "kritik" for m in (state.missing_info or [])
        )
        onemli_var = any(
            m.get("oncelik") == "önemli" for m in (state.missing_info or [])
        )

        # Kapı 2: dil uyarısı varsa önce evrak dili doğrulanmalı
        if "dil_uyarisi" in uyari_kodlari:
            adimlar.append(
                "Evrakın dilini doğrulayın; evrak Türkçe değilse çeviri/"
                "inceleme sonrasında yeniden işleyin."
            )

        if state.draft_text:
            taslak_adi = DRAFT_TYPE_LABELS.get(state.draft_type, "yazı")
            if state.draft_type == "eksik_bilgi_talep":
                talep_muhatabi = (
                    "belgeyi düzenleyen birime" if ic_belge else "başvuru sahibine"
                )
                adimlar.append(
                    f"Hazırlanan '{taslak_adi}' taslağını kontrol ederek "
                    f"{talep_muhatabi} gönderilmek üzere onaya sunun."
                )
            else:
                adimlar.append(
                    f"Hazırlanan '{taslak_adi}' taslağının içeriğini kontrol "
                    f"ederek yetkili amirin onayına sunun."
                )

        fv = state.format_validation or {}
        if fv and not fv.get("uygun", True):
            basarisiz = [
                k.get("kural", "") for k in fv.get("kontroller", [])
                if not k.get("durum", True)
            ]
            adimlar.append(
                "Format denetiminde uygun bulunmayan alanları düzeltin: "
                + ", ".join(basarisiz[:4]) + "."
            )

        if kritik_var or onemli_var:
            eksik_kaynagi = (
                "belgeyi düzenleyen birimden" if ic_belge else "başvuru sahibinden"
            )
            adimlar.append(
                f"Tespit edilen eksik bilgileri {eksik_kaynagi} temin edin "
                "(sistemin hazırladığı sorular 'eksik bilgi talepleri' "
                "bölümünde listelenmiştir)."
            )
            if kritik_var:
                adimlar.append(
                    "Kritik eksikler tamamlanmadan evrakı sonuçlandırmayın; "
                    "eksikler giderildikten sonra evrakı yeniden işleyin."
                )

        routing = state.routing_suggestion or {}
        if routing.get("birim"):
            adimlar.append(
                f"Evrakı gereği için '{routing['birim']}' birimine havale edin."
            )

        # Kapı 3: düşük güvenli kararlar insan kontrolünden geçirilmeli
        if state.human_review_required:
            adimlar.append(
                "Sistem kararlarında düşük güven tespit edildi; evrakı "
                "sonuçlandırmadan önce sonuçları insan kontrolünden geçirin."
            )

        sonuc_muhatabi = "ilgili birime" if ic_belge else "başvuru sahibine"
        adimlar.append(
            f"İşlem sonucunu {sonuc_muhatabi} bildirin ve evrak kaydını "
            "EBYS üzerinde kapatın."
        )

        mesaj = "Önerilen sonraki adımlar:\n" + "\n".join(
            f"{i}. {adim}" for i, adim in enumerate(adimlar, 1)
        )
        return {
            "tip": "sonraki_adimlar",
            "baslik": "Sonraki Adımlar",
            "mesaj": mesaj,
            "seviye": "bilgi",
            "adimlar": adimlar,
        }

    # ------------------------------------------------------------------
    # Eksik bilgi talepleri
    # ------------------------------------------------------------------

    def _build_clarification_requests(
        self, missing_info: list, evrak_turu: str
    ) -> list:
        """
        Kritik ve önemli öncelikli her eksik alan için kullanıcıya sorulacak
        açık Türkçe soru üretir (şartname: eksik bilgi talebi).

        Soru muhatabı evrak türüne göre koşullandırılır: başvuru kaynaklı
        evrakta başvuru sahibi, kurum içi belge türlerinde (tutanak, rapor,
        onaylı belge, genelge) belgeyi düzenleyen birim.

        Returns:
            [{"alan", "soru", "soru_muhatabi", "gerekce", "oncelik"}, ...]
            — kritikler önce
        """
        talepler = []
        secilen = [
            m for m in (missing_info or [])
            if m.get("oncelik") in ("kritik", "önemli")
        ]
        # Kritikler önce gelecek şekilde sırala
        secilen.sort(key=lambda m: 0 if m.get("oncelik") == "kritik" else 1)

        ic_belge = evrak_turu in _IC_BELGE_TURLERI
        soru_muhatabi = "duzenleyen_birim" if ic_belge else "basvuru_sahibi"

        for m in secilen:
            alan = m.get("alan", "")
            varsayilan_soru = (
                f"Evrak için gerekli olan '{alan.replace('_', ' ')}' bilgisini "
                f"belirtir misiniz?"
            )
            if ic_belge:
                soru = _IC_BELGE_ALAN_SORULARI.get(
                    alan, ALAN_SORULARI.get(alan, varsayilan_soru)
                )
                soru += " (Bu bilgi, belgeyi düzenleyen birimden talep edilmelidir.)"
            else:
                soru = ALAN_SORULARI.get(alan, varsayilan_soru)
            talepler.append({
                "alan": alan,
                "soru": soru,
                "soru_muhatabi": soru_muhatabi,
                "gerekce": self._build_gerekce(m, alan, evrak_turu),
                "oncelik": m.get("oncelik", "önemli"),
            })
        return talepler

    @staticmethod
    def _build_gerekce(missing: dict, alan: str, evrak_turu: str) -> str:
        """Eksik bilgi talebinin gerekçesini üretir."""
        temel = missing.get("aciklama", f"'{alan}' alanı evrakta bulunamadı")
        if evrak_turu == "dilekce" and alan in _DILEKCE_ZORUNLU_ALANLAR:
            dayanak = (
                "3071 sayılı Dilekçe Hakkı Kanunu uyarınca dilekçelerde "
                "bu bilginin bulunması zorunludur."
            )
        else:
            dayanak = (
                "Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında "
                "Yönetmelik gereği bu alan zorunludur."
            )
        return f"{temel}. {dayanak}"
