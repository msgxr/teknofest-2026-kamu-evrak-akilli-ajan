"""
Yazı Taslak Oluşturma Agent — Resmî yazı taslağı üretme ve format denetimi.

Şartname Referansı (Görev 2):
    - "Üst yazı, cevap yazısı, bilgilendirme metni veya alternatif resmî
      yazışma türü için uygun bir taslak oluşturması"
    - "Taslak metnin resmî üsluba uygun olmasını sağlaması"
    - "Gerekli durumlarda eksik bilgi talep edebilmesi": state.missing_info
      içinde 'kritik' öncelikli eksik varsa;
        * başvuru niteliğindeki evraklarda (dilekçe) başvuru sahibinden
          eksik bilgi/belge talep eden 'eksik_bilgi_talep' yazısı,
        * iç/kurumsal belge türlerinde (tutanak, rapor, onaylı belge,
          genelge, kurum yazıları) düzenleyen birime yönelik, eksiklerin
          ikmalini isteyen kısa resmî 'iade_ikmal_notu'
      üretilir (iç belgeye vatandaş tebligatı yazılmaz).

Format referansı:
    Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik
    (RG 10.06.2020/31151) — başlık (T.C./kurum/birim), Sayı, Tarih, Konu,
    muhatap, İlgi, metin, uygun kapanış (üst makama "arz ederim", alt/eş
    makama "rica ederim", gerçek kişiye "Saygılarımla"), imza bloğu,
    Ek ve Dağıtım bölümleri.

Çalışma deseni:
    1. LLM varsa taslak LLM'e yazdırılır (format kuralları prompt'a gömülü).
    2. LLM yoksa/başarısızsa şablon + kural tabanlı gövde üretimi devreye
       girer; şablonlar gerçek içerikle doldurulur, yer tutucu bırakılmaz.
    3. Her iki yolda da taslak, yönetmelik kontrol listesinden geçirilerek
       state.format_validation doldurulur.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from src.utils.turkish_nlp import extract_sentences, turkish_lower

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.draft_writer")

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"

TEMPLATE_FILES = {
    "ust_yazi": "ust_yazi.txt",
    "cevap_yazisi": "cevap_yazisi.txt",
    "bilgilendirme": "bilgilendirme_metni.txt",
    "eksik_bilgi_talep": "eksik_bilgi_talep.txt",
    "iade_ikmal_notu": "iade_ikmal_notu.txt",
}

DRAFT_TYPE_LABELS = {
    "ust_yazi": "Üst Yazı",
    "cevap_yazisi": "Cevap Yazısı",
    "bilgilendirme": "Bilgilendirme Metni",
    "eksik_bilgi_talep": "Eksik Bilgi Talep Yazısı",
    "iade_ikmal_notu": "İade/İkmal Notu",
}

# Başvuru niteliğindeki evrak türleri: kritik eksikte başvuru sahibine
# 'eksik_bilgi_talep' yazılır; diğer türlerde düzenleyen birime yönelik
# 'iade_ikmal_notu' üretilir (iç belgeye vatandaş tebligatı yazılmaz).
BASVURU_TURLERI = {"dilekce"}

# İlgi bloğu içeren şablonlar; İlgi'siz şablonlarda giriş cümlesi
# "İlgi'de kayıtlı" atfı YAPMAZ (finding: İlgi'siz şablonda İlgi atfı).
TEMPLATES_WITH_ILGI = {"ust_yazi", "cevap_yazisi", "eksik_bilgi_talep", "iade_ikmal_notu"}

# Sayı satırı: uydurma numara yerine dürüst taslak ibaresi
# (gerçek sayı belge kayıt sisteminden alınır).
TASLAK_SAYI_IBARESI = "(TASLAK — sayı EBYS tarafından verilecektir)"

# Gelen evrak türü → İlgi/giriş cümlelerinde kullanılacak kaynak adı
_EVRAK_KAYNAK_ADI = {
    "dilekce": "dilekçe",
    "ust_yazi": "yazı",
    "cevap_yazisi": "cevabi yazı",
    "bilgilendirme": "bilgilendirme yazısı",
    "tutanak": "tutanak",
    "rapor": "rapor",
    "genelge": "genelge",
    "onayli_belge": "onay belgesi",
}

# Taslakta mevzuat atfı için asgari benzerlik eşiği; altındaki eşleşmeler
# yerine genel "ilgili mevzuat hükümleri" ifadesi kullanılır.
MEVZUAT_ATIF_ESIGI = 0.6

# Birinci şahıs (başvuru sahibi ağzından) cümle tespiti: resmî yazı üçüncü
# şahıs anlatımla yazılır (Resmî Yazışma Yönetmeliği'nin öngördüğü resmî
# üslup); vatandaşın "abonesi olduğum … anlamış bulunmaktayım" gibi
# birinci-şahıs cümleleri kurum yazısına aynen aktarılmaz. Tespit,
# Türkçe morfolojisine dayanır: birinci şahıs zamirleri ile fiil/iyelik
# ekleri (-DIğIm, -mAktAyIm, -Iyorum, -mIşIm, -mAlIyIm, "ederim" vb.).
_BIRINCI_SAHIS_KELIMELER = frozenset({
    "ben", "benim", "bana", "beni", "bende", "benden",
    "biz", "bizim", "bize", "bizi", "bizler",
    "şahsım", "şahsıma", "şahsımın", "adıma",
    "tarafıma", "tarafımdan", "tarafımca",
})
_BIRINCI_SAHIS_EK = re.compile(
    r"(?:"
    r"[dt][ıiuü]ğ[ıiuü]m(?:[ıi]z)?"        # olduğum, ikamet ettiğimiz
    r"|makta(?:yım|yız)|mekte(?:yim|yiz)"  # bulunmaktayım, etmekteyiz
    r"|[ıiuü]yor(?:um|uz)"                 # istiyorum, ediyoruz
    r"|m[ıiuü]ş[ıiuü](?:m|z)"              # kalmışım, olmuşuz
    r"|mal[ıi]y[ıi](?:m|z)|meli(?:yim|yiz)"  # yapmalıyım, etmeliyiz
    r"|eder[ıi]m|eder[ıi]z|[ıi]ster[ıi]m|[ıi]ster[ıi]z"  # arz ederim …
    r"|sunar[ıi]m|sunar[ıi]z|d[ıi]ler[ıi]m|d[ıi]ler[ıi]z"
    r"|l[ae]r[ıi]m(?:[ıiae]|d[ae]n?)?"     # belgelerim, hareketlerime (tekil iyelik)
    r")$"
)

# Ad + 1. tekil koşacı ("hissedarıyım", "abonesiyim"): iyelikli ada
# y kaynaştırmasıyla eklenen koşaç dar ünlü taşır ([ıiuü]y[ıiuü]m).
# En az 7 harf şartı, aynı diziyle biten yalın adları ("uyum", "giyim",
# "duyum") dışarıda bırakır — koşaçlı yüklem kök+iyelik+koşaç içerdiği
# için zorunlu olarak daha uzundur.
_BIRINCI_SAHIS_KOSAC = re.compile(r"[ıiuü]y[ıiuü]m$")

# Cümle sonundaki çekimli yüklemler ("tespit edilmiştir",
# "yaşanmaktadır", "geçilecektir"): Konu satırı, yönetmelik gereği
# yazının konusunu özetleyen bir AD ÖBEĞİdir; cümleden konu türetilirken
# çekimli yüklem atılır.
_CEKIMLI_YUKLEM = re.compile(
    r"(?:m[ıiuü]şt[ıiuü]r|m[ae]kt[ae]d[ıi]r|[ae]c[ae]kt[ıi]r"
    r"|m[ae]l[ıi]d[ıi]r|mekted[ıi]r)$"
)
# Yardımcı fiille birleşik yüklem kuran ad ögeleri ("tespit edilmiştir")
_YUKLEM_AD_OGELERI = frozenset({
    "tespit", "talep", "teslim", "tebliğ", "ifade", "beyan", "karar",
    "kabul", "tesis", "arz", "rica", "teşekkür", "devam", "elde",
})
# Cümle başındaki bağlayıcılar (konuya taşınmaz)
_BAS_BAGLAYICILAR = frozenset({
    "ayrıca", "ancak", "nitekim", "dolayısıyla", "bununla", "birlikte",
    "öte", "yandan", "oysa", "üstelik",
})

# Gelen evrak türü → üretilecek yazı türü eşlemesi
DRAFT_TYPE_MAP = {
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

# Şablon dosyası okunamazsa kullanılacak asgari yedek şablon
FALLBACK_TEMPLATE = """T.C.
{kurum_adi}
{birim_adi}

Sayı   : {sayi}                                                {tarih}
Konu   : {konu}

{muhatap}

İlgi   : {ilgi}

{metin}

{kapanis}

                                                        {imza_sahibi}
                                                        {unvan}
"""

# Kurum (üst kuruluş) adı tespiti için ekler
_KURUM_EKLERI = ("Bakanlığı", "Başkanlığı", "Valiliği", "Kaymakamlığı",
                 "Belediyesi", "Üniversitesi", "Kurumu", "Genel Müdürlüğü")
# Birim adı tespiti için ekler
_BIRIM_EKLERI = ("Müdürlüğü", "Müşavirliği", "Dairesi", "Daire Başkanlığı",
                 "Şube Müdürlüğü")

# Antet (kurum) seçiminde ek tipine göre öncelik hiyerarşisi:
# üst kuruluşlar > orta kademe > birim düzeyi ekler. "En uzun aday"
# yerine bu hiyerarşi kullanılır (yanlış antet seçimini önler).
_KURUM_ONCELIK_KADEMELERI = (
    ("Bakanlığı", "Valiliği", "Kaymakamlığı", "Belediyesi", "Üniversitesi"),
    ("Başkanlığı", "Genel Müdürlüğü", "Kurumu"),
    ("Müdürlüğü", "Dairesi", "Müşavirliği"),
)

# Dağıtım bölümündeki "Gereği :" / "Bilgi :" satırları: buradaki adlar
# yazının MUHATAP birimleridir, düzenleyen kurumun anteti değildir.
_DAGITIM_SATIRI = re.compile(r"^\s*(?:Gereği|Bilgi)\s*:\s*(.+)$", re.IGNORECASE)

# Gelen evrakta ek beyanı ("Ek :", "Ekler :", "Ek-1", "EKLER:") tespiti
_EK_BEYANI = re.compile(r"(?mi)^\s*ek(?:ler)?\s*(?:-?\s*\d+\s*)?:")

# ----------------------------------------------------------------------
# Madde-referanslı format denetimi sabitleri (P0-2)
#
# Her denetim kuralı {kural_id, kural, durum, detay, dayanak, agirlik}
# şemasıyla raporlanır. Dayanaklar, 2646 sayılı Cumhurbaşkanı Kararı'nın
# (Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik,
# RG 10.06.2020/31151) RESMÎ metninden fıkra düzeyinde doğrulanmıştır
# (mevzuat.gov.tr + tccb.gov.tr çapraz kontrol, 11.07.2026). Uydurma
# madde atfı yapılmaz; yönetmelikte karşılığı olmayan iç kalite kuralları
# "iç kalite kuralı" dayanağıyla işaretlenir.
# ----------------------------------------------------------------------

# m.11/1-2: sayı = "E"/"Z"/"O" ibaresi + DETSİS'teki Devlet Teşkilatı
# Numarası + standart dosya planı kodu + kayıt numarası, kısa çizgiyle
# (örnek biçim m.11/2: E-67915368-903.07.02-4752)
_SAYI_BICIM_DESENI = re.compile(r"\b[EZO]-\d{8}-[\d.]+-\d+\b")

# Sayı ve Konu satırlarının değerlerini yakalar (biçim/özlük denetimi)
_SAYI_SATIRI = re.compile(r"(?mi)^\s*Say[ıi]\s*:\s*(.+)$")
_KONU_SATIRI = re.compile(r"(?mi)^\s*Konu\s*:\s*(.+)$")

# m.13/2 "kısa ve öz" konunun makul mühendislik karşılığı: bu uzunluğu
# aşan konu uyarılır (yönetmelikte katı karakter sınırı yoktur; m.13/1
# konunun birden çok satıra taşmasına da izin verir)
_KONU_AZAMI_UZUNLUK = 160

# m.16/8: zorunlu olmadıkça yabancı dillerden kelime kullanılmaz.
# Kamu yazışmalarında sık görülen, yerleşik Türkçe karşılığı olan örnekler:
_YABANCI_KELIMELER = (
    "attachment", "deadline", "download", "e-mail", "email", "feedback",
    "mail", "meeting", "online", "server", "update", "upload",
)
_YABANCI_KELIME_DESENI = re.compile(
    r"\b(" + "|".join(_YABANCI_KELIMELER) + r")\b", re.IGNORECASE
)

# m.16/10: maddelemede Türk alfabesindeki KÜÇÜK harfler KAPAMA PARANTEZİ
# ile kullanılır: "a)" — "a." veya "A)" biçimleri yönetmeliğe aykırıdır
_MADDELEME_SATIRI = re.compile(r"(?m)^\s*([a-zçğıöşüA-ZÇĞİÖŞÜ])([.)])\s+")

# m.17/9: yetki devrinde imza bloğunda "... a." ibaresi (ör. "Vali a.");
# ibarenin ALTINDA imzalayanın unvanı yer alır. Aynı fıkra: iç
# yazışmalarda yetki devredenin unvanı kullanılmaz.
_YETKI_DEVRI_SATIRI = re.compile(r"(?m)^[^\S\n]*\S[^\n]*\sa\.[^\S\n]*$")

# m.25 (gizlilik dereceli belgeler) + m.26/4 (KİŞİYE ÖZEL): damga,
# tek başına satır hâlinde büyük harflerle aranır (tesadüfi kelime
# eşleşmesini önlemek için)
_GIZLILIK_DAMGASI = re.compile(
    r"(?m)^\s*(ÇOK GİZLİ|GİZLİ|HİZMETE ÖZEL|KİŞİYE ÖZEL)\s*$"
)

# BÜYÜK harf hitap/yönelme biçimleri (…MÜDÜRLÜĞÜNE, …BAŞKANLIĞINA,
# …MAKAMINA, …BİRİMLERE benzeri) — morfolojik desen
_HITAP_SONU = re.compile(
    r"(?:L[IİUÜ][GĞ][IİUÜ]N[AE]|L[AE]R[Iİ]?N[AE]|L[AE]R[AE]|"
    r"MAKAMINA|DAİRESİNE|KOMİSYONUNA|KURULUNA|KURUMUNA|"
    r"BİRİMLERE|BİRİME|İLGİLİLERE)$"
)


def _tr_upper(text: str) -> str:
    """Türkçe'ye uygun büyük harfe çevirme (i→İ, ı→I)."""
    return (text or "").replace("i", "İ").replace("ı", "I").upper()


def _tr_baslik(text: str) -> str:
    """Türkçe'ye uygun başlık biçimi (her kelimenin ilk harfi büyük)."""
    kelimeler = []
    for kelime in (text or "").split():
        kucuk = turkish_lower(kelime)
        kelimeler.append(_tr_upper(kucuk[0]) + kucuk[1:] if kucuk else kucuk)
    return " ".join(kelimeler)


def _her_iki_bicim(ekler: tuple) -> str:
    """Regex için eklerin hem başlık hem BÜYÜK biçimlerinden alternation üretir."""
    parcalar = []
    for ek in ekler:
        parcalar.append(re.escape(ek))
        parcalar.append(re.escape(_tr_upper(ek)))
    return "|".join(parcalar)


# "... BAŞKANLIĞI Bilgi İşlem Müdürlüğü" gibi birleşik adlarda kurum kısmını ayırır
_KURUM_DESENI = re.compile(r"^(.*?(?:" + _her_iki_bicim(_KURUM_EKLERI) + r"))(?:\s|$)")
# Birleşik adlarda kurum kısmını atıp birim kısmını bırakmak için
_KURUM_SOYMA_DESENI = re.compile(r"^.*?(?:" + _her_iki_bicim(_KURUM_EKLERI) + r")\s+")


class DraftWriterAgent:
    """
    Yazı taslak oluşturma agent'ı.

    Evrak türüne, çıkarılan bilgilere ve mevzuat eşleşmelerine göre resmî
    üsluba uygun yazı taslağı oluşturur; taslağı yönetmelik kurallarına
    göre denetleyip format raporu üretir. Kritik eksik bilgi varsa
    'eksik bilgi talep yazısı' üretir (şartname: eksik bilgi talebi).
    """

    def __init__(self) -> None:
        logger.info("Yazı Taslak Agent başlatıldı.")

    # ------------------------------------------------------------------
    # Ana akış
    # ------------------------------------------------------------------

    def run(self, state: "AgentState") -> "AgentState":
        """Resmî yazı taslağı oluşturur ve format denetimini doldurur."""
        evrak_turu = state.classification.get("tur", "diger")

        # Hedef yazı türü (kritik eksik bilgi → eksik_bilgi_talep)
        yazi_turu = self._determine_draft_type(evrak_turu, state.missing_info)
        state.draft_type = yazi_turu

        draft, yontem = self._generate_draft(yazi_turu, state)
        state.draft_text = draft

        gizlilik = self._gizlilik_damgasi(state.raw_text)
        validation = self._validate_format(
            draft, yazi_turu, gizlilik_damgasi=gizlilik
        )
        validation["uretim_yontemi"] = yontem
        state.format_validation = validation

        # m.25: gizlilik dereceli evrak kısıtlı modda işlenir — üretilen
        # taslak ancak insan onayıyla kullanılabilir (Kapı 3 mekanizması)
        if gizlilik:
            state.human_review_required = True
            neden = (
                f"Kaynak evrak '{gizlilik}' damgası taşıyor; gizlilik "
                "dereceli evrakta taslak yalnızca insan onayıyla "
                "kullanılmalıdır (Yön. m.25)."
            )
            if neden not in state.human_review_reasons:
                state.human_review_reasons.append(neden)

        logger.info(
            f"Yazı taslağı oluşturuldu: {yazi_turu} "
            f"({len(draft)} karakter, yöntem: {yontem}, "
            f"format skoru: {validation['skor']:.2f})"
        )
        return state

    def _determine_draft_type(self, evrak_turu: str, missing_info: list) -> str:
        """
        Gelen evrak türüne göre oluşturulacak yazı türünü belirler.

        Şartname isteri: sistem gerekli durumlarda eksik bilgi talep
        edebilmelidir. Kritik öncelikli eksik bilgi varsa;
          - başvuru niteliğindeki türlerde (dilekçe) başvuru sahibine
            'eksik_bilgi_talep' yazısı,
          - iç/kurumsal belge türlerinde (tutanak, rapor, onaylı belge,
            genelge, kurum yazıları) düzenleyen birime 'iade_ikmal_notu'
        üretilir; iç belge için vatandaşa tebligatlı talep yazılmaz.
        """
        kritik = [m for m in (missing_info or []) if m.get("oncelik") == "kritik"]
        if kritik:
            hedef = (
                "eksik_bilgi_talep" if evrak_turu in BASVURU_TURLERI
                else "iade_ikmal_notu"
            )
            logger.info(
                f"{len(kritik)} kritik eksik bilgi tespit edildi; "
                f"'{hedef}' yazısı üretilecek."
            )
            return hedef
        return DRAFT_TYPE_MAP.get(evrak_turu, "ust_yazi")

    def _generate_draft(self, yazi_turu: str, state: "AgentState") -> tuple:
        """
        Yazı taslağı oluşturur: önce LLM, başarısızsa kural tabanlı yol.

        Returns:
            (taslak_metni, uretim_yontemi) ikilisi
        """
        try:
            draft = self._generate_with_llm(yazi_turu, state)
            skor = self._validate_format(draft, yazi_turu)["skor"]
            if skor < 0.6:
                logger.warning(
                    f"LLM taslağı format denetiminden geçemedi (skor={skor:.2f}); "
                    f"kural tabanlı taslağa dönülüyor."
                )
                return self._generate_from_template(yazi_turu, state), "kural_tabanli"
            return draft, "llm"
        except Exception as e:
            logger.warning(f"LLM taslak oluşturulamadı, şablon kullanılıyor: {e}")
            return self._generate_from_template(yazi_turu, state), "kural_tabanli"

    # ------------------------------------------------------------------
    # LLM yolu
    # ------------------------------------------------------------------

    def _generate_with_llm(self, yazi_turu: str, state: "AgentState") -> str:
        """LLM ile yönetmelik kurallarına uygun yazı taslağı oluşturur."""
        from src.models.llm_wrapper import (
            GUVENLIK_SISTEM_EKI,
            LLMUnavailableError,
            belge_blogu,
            get_default_llm,
        )

        llm = get_default_llm()
        if not llm.is_available():
            raise LLMUnavailableError("LLM backend'i yok (offline mod).")

        extracted = state.extracted_info or {}
        mevzuat_str = "\n".join(
            f"- {m.get('baslik', '')}" for m in (state.legislation_matches or [])[:3]
        ) or "- Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hakkında Yönetmelik"

        eksik_str = ""
        if yazi_turu in ("eksik_bilgi_talep", "iade_ikmal_notu"):
            eksikler = [
                f"- {m.get('aciklama', m.get('alan', ''))} (öncelik: {m.get('oncelik', '')})"
                for m in (state.missing_info or [])
                if m.get("oncelik") in ("kritik", "önemli")
            ]
            hedef_kitle = (
                "Başvuru sahibinden talep edilecek"
                if yazi_turu == "eksik_bilgi_talep"
                else "Evrakı düzenleyen birimden ikmali istenecek"
            )
            eksik_str = (
                f"\n{hedef_kitle} eksik bilgi/belgeler:\n" + "\n".join(eksikler)
            )

        # GÜVENLİK: evrak metni belge_blogu ile "yalnızca veri" olarak
        # işaretlenir (dolaylı prompt injection savunması, OWASP LLM01)
        prompt = f"""Aşağıdaki gelen evraka karşılık resmî bir "{DRAFT_TYPE_LABELS.get(yazi_turu, yazi_turu)}" taslağı yaz.

{belge_blogu(state.raw_text, 3000)}

Çıkarılan Bilgiler:
- Konu: {extracted.get('konu') or 'Belirtilmemiş'}
- Muhatap: {extracted.get('muhatap') or 'Belirtilmemiş'}
- Tarihler: {', '.join(extracted.get('tarihler') or ['Belirtilmemiş'])}
- Kurumlar: {', '.join(extracted.get('kurum_adlari') or ['Belirtilmemiş'])}

İlgili Mevzuat (metinde uygun yerde atıf yap):
{mevzuat_str}
{eksik_str}

Resmî Yazışma Yönetmeliği (RG 10.06.2020/31151) format kuralları — MUTLAKA uygula:
1. "T.C." başlığı, altında kurum adı ve birim adı ile başla.
2. Sayı satırına numara UYDURMA; "Sayı : {TASLAK_SAYI_IBARESI}" yaz ve tarih ({datetime.now().strftime('%d.%m.%Y')}) satırı ekle.
3. "Konu :" satırında konuyu kısaca belirt.
4. Muhatap satırı: kuruma yazıyorsan BÜYÜK HARF (örn. "... MAKAMINA"), gerçek kişiye yazıyorsan "Sayın Ad SOYAD".
5. "İlgi :" bölümünde gelen evrakın tarih/sayısına atıf yap.
6. Metin gövdesi resmî, nesnel ve açık Türkçe olsun; ilgili mevzuata atıf içersin.
7. Kapanış kuralı: üst makama "... arz ederim.", alt veya eş makama "... rica ederim.", gerçek kişiye "Saygılarımla." kullan.
8. İmza bloğu: ad-soyad yerine "(e-imzalıdır)" ve altında unvan yaz.
9. "Ek :" bölümüne yalnızca gerçekten var olan ekleri yaz; ek yoksa "Ek : Yoktur." yaz. Gerekiyorsa "Dağıtım:" bölümü ekle.
10. Köşeli parantezli yer tutucu ([...]) KULLANMA; tüm alanları gerçek içerikle doldur.

Yalnızca yazı taslağının kendisini döndür; açıklama ekleme."""

        system_prompt = (
            "Sen bir kamu kurumunda resmî yazışma kurallarına hâkim, "
            "deneyimli bir yazı işleri uzmanısın. Türkçe resmî üslupla yazarsın."
            + GUVENLIK_SISTEM_EKI
        )
        return llm.generate(prompt, system_prompt=system_prompt).strip()

    # ------------------------------------------------------------------
    # Kural tabanlı yol
    # ------------------------------------------------------------------

    def _generate_from_template(self, yazi_turu: str, state: "AgentState") -> str:
        """
        Şablonu gerçek içerikle doldurarak yazı taslağı oluşturur.

        Yer tutucu ([PLACEHOLDER]) bırakılmaz; tüm alanlar çıkarılan
        bilgilerden veya kural tabanlı üretilen içerikten doldurulur.
        """
        template = self._load_template(yazi_turu)
        extracted = state.extracted_info or {}
        evrak_turu = state.classification.get("tur", "diger")
        now = datetime.now()

        kurum_adi = self._resolve_kurum_adi(extracted, state.raw_text)
        birim_adi = self._resolve_birim_adi(extracted, state.raw_text)
        if yazi_turu == "iade_ikmal_notu":
            # İade/ikmal notunu evrak kayıt birimi düzenler; düzenleyen
            # birim ise muhataptır (kendi kendine yazışma oluşmaz).
            birim_adi = "Yazı İşleri Müdürlüğü"
        konu = self._resolve_konu(yazi_turu, extracted, state)
        muhatap = self._resolve_muhatap(yazi_turu, evrak_turu, extracted, state.raw_text)
        ilgi = self._resolve_ilgi(evrak_turu, extracted, state.raw_text)
        metin = self._build_body(yazi_turu, evrak_turu, konu, state)
        kapanis = self._resolve_kapanis(yazi_turu, evrak_turu, muhatap, kurum_adi)
        unvan = self._unvan_from_birim(birim_adi)

        fields = {
            "kurum_adi": kurum_adi,
            "birim_adi": birim_adi,
            "sayi": TASLAK_SAYI_IBARESI,
            "tarih": now.strftime("%d.%m.%Y"),
            "konu": konu,
            "muhatap": muhatap,
            "ilgi": ilgi,
            "metin": metin,
            "kapanis": kapanis,
            "imza_sahibi": "(e-imzalıdır)",
            "unvan": unvan,
            "ekler": self._resolve_ekler(yazi_turu, state.raw_text),
            "dagitim_geregi": self._resolve_dagitim(yazi_turu, muhatap),
            "dagitim_bilgi": "Yazı İşleri Müdürlüğü",
            "eksik_liste": self._build_eksik_liste(state.missing_info),
            "talep_metni": self._build_talep_metni(yazi_turu, evrak_turu),
        }
        return template.format(**fields)

    def _load_template(self, yazi_turu: str) -> str:
        """Şablon dosyasını okur; okunamazsa yedek şablona düşer."""
        dosya = TEMPLATE_FILES.get(yazi_turu, TEMPLATE_FILES["ust_yazi"])
        path = TEMPLATE_DIR / dosya
        try:
            return path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning(f"Şablon dosyası okunamadı ({path}): {e}; yedek şablon kullanılıyor.")
            return FALLBACK_TEMPLATE

    # ---------------- Alan çözümleyiciler ----------------

    def _resolve_kurum_adi(self, extracted: dict, raw_text: str) -> str:
        """
        Çıkarılan kurum adlarından üst kuruluş (antet) adını seçer.

        Seçim "en uzun aday" yerine ek tipine göre öncelik hiyerarşisiyle
        yapılır (Bakanlığı/Valiliği/Belediyesi/Üniversitesi >
        Başkanlığı/Genel Müdürlüğü > Müdürlüğü/Dairesi); eşitlikte metinde
        önce görünen (antet konumundaki) aday tercih edilir. "Gereği :" /
        "Bilgi :" dağıtım satırlarından gelen adlar muhataptır, antete
        alınmaz. Aday yoksa muhatap hitabından kurum adı türetilir.
        """
        adaylar = self._antet_adaylari(extracted, raw_text)
        en_iyi: Optional[tuple] = None
        for sira, aday in enumerate(adaylar):
            match = _KURUM_DESENI.search(aday)
            if not match:
                continue
            kurum = match.group(1).strip()
            anahtar = (self._kurum_kademesi(kurum), sira)
            if en_iyi is None or anahtar < en_iyi[:2]:
                en_iyi = (*anahtar, kurum)
        if en_iyi:
            return _tr_upper(en_iyi[2])

        # Antetsiz evrak (ör. dilekçe): muhatap hitabından kurum türet
        hitaptan = self._hitaptan_kurum(extracted.get("muhatap") or "")
        if hitaptan:
            return hitaptan
        if adaylar:
            return _tr_upper(adaylar[0])
        return "GENEL MÜDÜRLÜK"

    def _resolve_birim_adi(self, extracted: dict, raw_text: str) -> str:
        """
        Çıkarılan kurum adlarından birim (müdürlük vb.) adını seçer.

        Birleşik adlarda kurum kısmı soyulur; dağıtım ("Gereği :"/"Bilgi :")
        satırlarından gelen adlar elenir; birden fazla aday varsa en kısa
        (en özgül) olan tercih edilir.
        """
        birimler = []
        for aday in self._antet_adaylari(extracted, raw_text):
            aday = _KURUM_SOYMA_DESENI.sub("", aday).strip()
            if aday and any(aday.endswith(ek) for ek in _BIRIM_EKLERI):
                birimler.append(aday)
        if birimler:
            return min(birimler, key=len)
        return "Yazı İşleri Müdürlüğü"

    def _antet_adaylari(self, extracted: dict, raw_text: str) -> list:
        """
        Antette kullanılabilecek kurum/birim adaylarını döndürür.

        "Gereği :" / "Bilgi :" satırlarında geçen adlar dağıtım muhatabı
        olduğundan aday listesinden çıkarılır.
        """
        dagitim = self._dagitim_adlari(raw_text)
        adaylar = []
        for ham in (extracted.get("kurum_adlari") or []):
            aday = self._clean_org(ham)
            if not aday:
                continue
            aday_kucuk = turkish_lower(aday)
            if any(aday_kucuk in deger for deger in dagitim):
                continue
            adaylar.append(aday)
        return adaylar

    @staticmethod
    def _dagitim_adlari(raw_text: str) -> list:
        """'Gereği :' / 'Bilgi :' satırlarındaki değerleri (küçük harf) verir."""
        degerler = []
        for line in (raw_text or "").split("\n"):
            match = _DAGITIM_SATIRI.match(line)
            if match:
                degerler.append(turkish_lower(match.group(1).strip()))
        return degerler

    @staticmethod
    def _kurum_kademesi(kurum: str) -> int:
        """Kurum adının öncelik kademesini döndürür (küçük değer = öncelikli)."""
        buyuk = _tr_upper(kurum)
        for kademe, ekler in enumerate(_KURUM_ONCELIK_KADEMELERI):
            if any(buyuk.endswith(_tr_upper(ek)) for ek in ekler):
                return kademe
        return len(_KURUM_ONCELIK_KADEMELERI)

    def _hitaptan_kurum(self, muhatap: str) -> str:
        """
        Muhatap hitabından yalın kurum adı türetir.

        Dilekçe gibi antetsiz evraklarda cevabı yazacak kurum, evrakın
        hitap ettiği makamdır: "… BELEDİYE BAŞKANLIĞINA" → "… BELEDİYE
        BAŞKANLIĞI". Yönelme eki morfolojik olarak soyulur; sonuç kurum
        ekiyle bitmiyorsa kullanılmaz.
        """
        hitap = _tr_upper(self._clean_org(muhatap))
        if not hitap:
            return ""
        hitap = re.sub(r"\s+MAKAMINA$", "", hitap)
        hitap = re.sub(r"([GĞ])([IİUÜ])N[AE]$", r"\1\2", hitap)  # …LIĞINA → …LIĞI
        hitap = re.sub(r"(S[IİUÜ])N[AE]$", r"\1", hitap)         # …SİNE → …Sİ
        match = _KURUM_DESENI.search(hitap)
        if match:
            return _tr_upper(match.group(1).strip())
        return ""

    @staticmethod
    def _clean_org(name: str) -> str:
        """Kurum adındaki satır sonu / 'T.C.' / 'Sayın' artıklarını temizler."""
        temiz = re.sub(r"\s+", " ", name or "").strip()
        temiz = re.sub(r"^T\.C\.\s*", "", temiz)
        temiz = re.sub(r"^Say[ıi]n\s+", "", temiz)
        return temiz.strip(" ,;:")

    def _resolve_konu(self, yazi_turu: str, extracted: dict, state: "AgentState") -> str:
        """
        Konu satırını üretir.

        Konu; çıkarılan "Konu :" alanından, yoksa belge başlığından, o da
        yoksa künyesiz özet gövdesinin (summary_body) ilk anlamlı
        cümlesinden türetilir. Künyeli özet ASLA kullanılmaz; kesme kelime
        sınırında yapılır; "hakkında" ile biten konuya " hk." eklenmez.
        """
        konu = self._konu_metni(extracted, state)

        if yazi_turu == "eksik_bilgi_talep":
            if konu:
                kisa = self._konu_bas_harfi(
                    self._baglanti_icin_temizle(self._kisalt(konu, 60))
                )
                return f"{kisa} başvurusundaki eksik bilgi ve belgelerin tamamlanması hk."
            return "Başvurudaki eksik bilgi ve belgelerin tamamlanması hk."

        if yazi_turu == "iade_ikmal_notu":
            if konu:
                kisa = self._konu_bas_harfi(
                    self._baglanti_icin_temizle(self._kisalt(konu, 60))
                )
                return f"{kisa} konulu evraktaki eksik unsurların ikmali hk."
            return "Evraktaki eksik unsurların ikmali hk."

        if konu:
            kisa = self._konu_bas_harfi(self._kisalt(konu, 100))
            kucuk = turkish_lower(kisa)
            if kucuk.endswith("hakkında") or kucuk.endswith("hk.") or kucuk.endswith("hk"):
                return kisa
            return kisa + " hk."

        tur_adi = state.classification.get("tur_adi", "Gelen evrak")
        return f"{tur_adi} hakkında yapılan işlem hk."

    def _konu_metni(self, extracted: dict, state: "AgentState") -> str:
        """
        Konu için ham metni belirler: "Konu :" alanı > belge başlığı >
        summary_body ilk NESNEL cümlesi. Alan etiketi kalıntıları
        temizlenir; başvuru sahibinin birinci-şahıs cümleleri Konu
        satırına taşınmaz (resmî yazı üçüncü şahıs anlatım gerektirir).
        """
        konu = self._etiket_temizle((extracted.get("konu") or "").strip().rstrip("."))
        if konu:
            return konu

        baslik = self._belge_basligi(state.raw_text)
        if baslik:
            return _tr_baslik(baslik)

        for cumle in extract_sentences(
            re.sub(r"\s+", " ", state.summary_body or "").strip()
        ):
            if self._birinci_sahis_mi(cumle):
                continue
            temiz = self._cumleden_konu(
                self._etiket_temizle(cumle).strip().rstrip(".")
            )
            if len(temiz.split()) >= 3:
                return temiz
        return ""

    @staticmethod
    def _cumleden_konu(text: str) -> str:
        """
        Cümleden Konu satırına uygun ad öbeği türetir.

        Konu satırı, Resmî Yazışma Yönetmeliği'ne göre yazının konusunu
        özetleyen bir ad öbeğidir; çekimli cümle değildir. Bu nedenle
        cümle başındaki bağlayıcılar ("Ayrıca", "Ancak" …) ile sondaki
        çekimli yüklem ("tespit edilmiştir", "yaşanmaktadır" …) atılır;
        Türkçe özne/tümleçler yüklemden önce geldiği için kalan parça
        dilbilgisel bütünlüğünü korur.
        """
        kelimeler = (text or "").split()
        while kelimeler and turkish_lower(kelimeler[0]).strip(",;") in _BAS_BAGLAYICILAR:
            kelimeler.pop(0)
        if kelimeler and _CEKIMLI_YUKLEM.search(turkish_lower(kelimeler[-1])):
            kelimeler.pop()
            # Birleşik yüklemin ad ögesi de atılır ("tespit edilmiştir")
            if kelimeler and turkish_lower(kelimeler[-1]) in _YUKLEM_AD_OGELERI:
                kelimeler.pop()
        return " ".join(kelimeler).strip(" ,;:-")

    @staticmethod
    def _etiket_temizle(text: str) -> str:
        """
        Metindeki 'Rapor No :', 'Belge No :', 'Tarih :' gibi alan etiketi
        kalıntılarını (etiket + değer) ve künye ayraçlarını temizler.
        """
        temiz = re.sub(
            r"(?:[A-ZÇĞİÖŞÜ][\wçğıöşü]*\s+){0,2}"
            r"(?:No|Numarası|Tarihi|Tarih|Say[ıi]s[ıi]|Say[ıi]|Saati|Saat|"
            r"Yeri|Yer|Hazırlayan|Düzenleyen|Katılımcılar)\s*:\s*\S*",
            " ",
            text or "",
        )
        temiz = re.sub(r"[|\[\]{}]", " ", temiz)
        return re.sub(r"\s+", " ", temiz).strip(" -,;:")

    @staticmethod
    def _belge_basligi(raw_text: str) -> str:
        """
        Evrakın büyük harfli başlık satırını bulur ("ARIZA TESPİT
        TUTANAĞI" gibi). Antet (kurum adı), "T.C." ve hitap satırları
        başlık sayılmaz.
        """
        for line in (raw_text or "").split("\n")[:15]:
            aday = line.strip().rstrip(" :")
            if len(aday) < 8 or len(aday.split()) < 2:
                continue
            if aday.startswith("T.C"):
                continue
            if aday != _tr_upper(aday) or not any(c.isalpha() for c in aday):
                continue
            if _KURUM_DESENI.search(aday):  # kurum anteti
                continue
            if _HITAP_SONU.search(aday):  # muhatap hitabı
                continue
            return aday
        return ""

    @staticmethod
    def _kisalt(text: str, maks: int) -> str:
        """
        Metni öbek bütünlüğünü koruyarak kısaltır.

        Sırasıyla:
        1. Sığıyorsa olduğu gibi döner.
        2. Sınır içindeki SON öbek sınırında keser: virgül/noktalı virgül
           veya 've / ile / veya' bağlacı — bağlaçla/virgülle bağlanan
           öbeklerin ilki kendi başına dilbilgisel bütünlük taşır.
        3. Öbek sınırı yoksa öndeki kelimeler atılır: Türkçe baş-sona
           (head-final) bir dildir, ad öbeğinin başı (asıl ad) sondadır;
           öndeki niteleyiciler atılınca öbek başı korunur ("depolardaki
           dayanıklı taşınır malların yıl sonu sayımı" → "malların yıl
           sonu sayımı"). Böylece kesme kelime veya öbek ortasına düşmez.
        """
        temiz = re.sub(r"\s+", " ", text or "").strip()
        if len(temiz) <= maks:
            return temiz

        # 2) Öbek sınırında kesme (yeterince uzun bir ön parça kalıyorsa)
        bolge = temiz[: maks + 1]
        sinir = -1
        for m in re.finditer(r"[,;]\s|\s(?:ve|ile|veya)\s", bolge):
            sinir = m.start()
        if sinir >= maks // 2:
            return bolge[:sinir].rstrip(" ,;:-")

        # 3) Baş-sona ilkesi: öbek başı (son kelimeler) korunur,
        #    öndeki niteleyiciler atılır.
        kelimeler = temiz.split()
        while len(kelimeler) > 1 and len(" ".join(kelimeler)) > maks:
            kelimeler.pop(0)
        # Başta sarkan bağlaç/edat artıkları atılır
        while len(kelimeler) > 1 and turkish_lower(kelimeler[0]) in (
            "ve", "ile", "veya", "için", "olan", "ya", "da", "de", "ki",
        ):
            kelimeler.pop(0)
        sonuc = " ".join(kelimeler).strip(" ,;:-")
        if len(sonuc) <= maks:
            return sonuc
        # Tek kelime bile sığmıyorsa son çare: sınırda kes
        return sonuc[:maks].rstrip()

    @staticmethod
    def _konu_bas_harfi(konu: str) -> str:
        """
        Konu satırının ilk harfini Türkçe kurala göre büyütür.

        Yönetmelik örneklerinde Konu satırı büyük harfle başlar; baş-sona
        (head-final) kısaltmada öndeki niteleyiciler atıldığında kalan ad
        öbeği küçük harfle başlayabilir ("ambarındaki taşınır malların…");
        satır başı bu durumda büyütülür. Rakamla başlayan konu
        ("2026/62 numaralı…") olduğu gibi bırakılır.
        """
        t = (konu or "").strip()
        if t and t[0].isalpha() and turkish_lower(t[0]) == t[0]:
            return _tr_upper(t[0]) + t[1:]
        return t

    @staticmethod
    def _baglanti_icin_temizle(konu: str) -> str:
        """Bileşik konu kalıbına girecek metinden sondaki 'hakkında/hk.' atılır."""
        return re.sub(
            r"\s+(?:hakkında|hk\.?)$", "", konu, flags=re.IGNORECASE
        ).strip()

    def _resolve_muhatap(
        self, yazi_turu: str, evrak_turu: str, extracted: dict, raw_text: str
    ) -> str:
        """Muhatap satırını üretir (kuruma BÜYÜK HARF, kişiye 'Sayın')."""
        # Kişiye yazılan türler: dilekçeye cevap ve eksik bilgi talebi
        if yazi_turu == "eksik_bilgi_talep" or (
            yazi_turu == "cevap_yazisi" and evrak_turu == "dilekce"
        ):
            kisi = self._find_applicant(extracted, raw_text)
            return f"Sayın {kisi}" if kisi else "Sayın Başvuru Sahibi"

        # İade/ikmal notunun muhatabı evrakı düzenleyen birimdir
        if yazi_turu == "iade_ikmal_notu":
            birimler = [
                _KURUM_SOYMA_DESENI.sub("", a).strip()
                for a in self._antet_adaylari(extracted, raw_text)
            ]
            birimler = [
                b for b in birimler
                if b and any(b.endswith(ek) for ek in _BIRIM_EKLERI)
            ]
            if birimler:
                return self._yonelme_hali(min(birimler, key=len))
            return "EVRAKI DÜZENLEYEN BİRİME"

        if yazi_turu == "bilgilendirme":
            return "İLGİLİ BİRİMLERE"

        muhatap = self._clean_org(extracted.get("muhatap") or "")
        if muhatap:
            muhatap_upper = _tr_upper(muhatap)
            # Zaten yönelme hâlinde hitap ise ("… MÜDÜRLÜĞÜNE",
            # "TÜM BİRİMLERE") olduğu gibi korunur; "MAKAMINA" eklenmez.
            if "MAKAM" in muhatap_upper or _HITAP_SONU.search(muhatap_upper):
                return muhatap_upper
            return f"{muhatap_upper} MAKAMINA"
        return "GENEL MÜDÜRLÜK MAKAMINA"

    @staticmethod
    def _yonelme_hali(ad: str) -> str:
        """
        Birim/kurum adını BÜYÜK harfli yönelme hâline çevirir
        ("Bilgi İşlem Müdürlüğü" → "BİLGİ İŞLEM MÜDÜRLÜĞÜNE").
        """
        buyuk = _tr_upper((ad or "").strip())
        if not buyuk:
            return ""
        if _HITAP_SONU.search(buyuk):
            return buyuk
        unluler = [c for c in buyuk if c in "AEIİOÖUÜ"]
        kalin = bool(unluler) and unluler[-1] in "AIOU"
        if buyuk.endswith(("I", "İ", "U", "Ü")):
            # İyelik ekli ad (MÜDÜRLÜĞÜ, DAİRESİ): kaynaştırma N + yönelme
            return buyuk + ("NA" if kalin else "NE")
        if buyuk.endswith(("A", "E", "O", "Ö")):
            return buyuk + ("YA" if kalin else "YE")
        return buyuk + ("A" if kalin else "E")

    @staticmethod
    def _find_applicant(extracted: dict, raw_text: str) -> str:
        """Başvuru sahibinin adını bulur (kişi adları > 'Ad Soyad:' satırı)."""
        kisiler = extracted.get("kisi_adlari") or []
        if kisiler:
            return str(kisiler[0]).strip()
        match = re.search(r"Ad[ıi]?\s*[-]?\s*Soyad[ıi]?\s*:\s*(.+)", raw_text or "")
        if match:
            return match.group(1).strip()
        return ""

    def _resolve_ilgi(self, evrak_turu: str, extracted: dict, raw_text: str) -> str:
        """İlgi satırını gelen evrakın tarih/sayı bilgisinden üretir."""
        kaynak = (
            "dilekçeniz" if evrak_turu == "dilekce"
            else _EVRAK_KAYNAK_ADI.get(evrak_turu, "yazı")
        )

        # İlgi atfı evrakın KENDİ tarihiyle yapılır (atıf tarihleri değil);
        # evrak tarihi tespit edilememişse tarihsiz atıf üretilir.
        if "evrak_tarihi" in extracted:
            tarih = str(extracted.get("evrak_tarihi") or "").strip()
        else:
            # Eski çağrılar için geriye dönük yol
            tarih = ""
            match = re.search(r"Tarih\s*:\s*([\d./]+)", raw_text or "")
            if match:
                tarih = match.group(1).strip()
            elif extracted.get("tarihler"):
                tarih = str(extracted["tarihler"][0]).strip()

        refler = extracted.get("referans_numaralari") or []
        ref = str(refler[0]).strip() if refler else ""

        if tarih and ref:
            return f"{tarih} tarihli ve {ref} sayılı {kaynak}."
        if tarih:
            return f"{tarih} tarihli {kaynak}."
        if ref:
            return f"{ref} sayılı {kaynak}."
        return f"Kurumumuza intikal eden {kaynak}."

    def _build_body(
        self, yazi_turu: str, evrak_turu: str, konu: str, state: "AgentState"
    ) -> str:
        """
        Yazı gövdesini kural tabanlı kurar:
        giriş cümlesi + özet atfı + mevzuat referansı + sonuç cümlesi.

        Özet atfında YALNIZCA künyesiz özet gövdesi (state.summary_body)
        kullanılır ve kesme cümle sınırında yapılır; künye ayraçları ve
        yarım kelimeler gövdeye taşınmaz.
        """
        paragraflar = []

        # İade/ikmal notu kısa tutulur: tespit cümlesi; eksik listesi ve
        # talep paragrafı şablonda ayrıca yer alır.
        if yazi_turu == "iade_ikmal_notu":
            kaynak = _EVRAK_KAYNAK_ADI.get(evrak_turu, "evrak")
            return (
                f"İlgi'de kayıtlı {kaynak} üzerinde yapılan ön incelemede, "
                f"evrakın işleme alınabilmesi için zorunlu olan bazı "
                f"unsurların eksik olduğu tespit edilmiştir."
            )

        # 1) Giriş cümlesi: gelen evrak türüne göre; "İlgi'de kayıtlı"
        #    atfı yalnızca İlgi bloğu içeren şablonlarda yapılır.
        konu_atfi = self._etiket_temizle(
            (state.extracted_info or {}).get("konu", "").strip().rstrip(".")
        )
        konu_str = f" '{self._kisalt(konu_atfi, 80)}' konulu" if konu_atfi else ""
        if yazi_turu in TEMPLATES_WITH_ILGI:
            giris_map = {
                "dilekce": f"İlgi'de kayıtlı{konu_str} dilekçeniz incelenmiştir.",
                "ust_yazi": f"İlgi'de kayıtlı{konu_str} yazı ve ekleri incelenmiştir.",
                "cevap_yazisi": f"İlgi'de kayıtlı{konu_str} cevabi yazı incelenmiştir.",
                "bilgilendirme": f"İlgi'de kayıtlı{konu_str} bilgilendirme yazısı değerlendirilmiştir.",
                "tutanak": "İlgi'de kayıtlı tutanakta yer alan tespitler incelenmiştir.",
                "rapor": "İlgi'de kayıtlı raporda yer alan tespit ve öneriler değerlendirilmiştir.",
                "genelge": "İlgi'de kayıtlı genelge hükümleri incelenmiştir.",
                "onayli_belge": "İlgi'de kayıtlı onay belgesi incelenmiştir.",
            }
            varsayilan = f"İlgi'de kayıtlı{konu_str} evrak incelenmiştir."
        else:
            giris_map = {
                "dilekce": f"Kurumumuza intikal eden{konu_str} dilekçe incelenmiştir.",
                "ust_yazi": f"Kurumumuza intikal eden{konu_str} yazı ve ekleri incelenmiştir.",
                "cevap_yazisi": f"Kurumumuza intikal eden{konu_str} cevabi yazı incelenmiştir.",
                "bilgilendirme": f"Kurumumuza intikal eden{konu_str} bilgilendirme yazısı değerlendirilmiştir.",
                "tutanak": "Kurumumuza intikal eden tutanakta yer alan tespitler incelenmiştir.",
                "rapor": "Kurumumuza intikal eden raporda yer alan tespit ve öneriler değerlendirilmiştir.",
                "genelge": "Kurumumuza intikal eden genelge hükümleri incelenmiştir.",
                "onayli_belge": "Kurumumuza intikal eden onay belgesi incelenmiştir.",
            }
            varsayilan = f"Kurumumuza intikal eden{konu_str} evrak incelenmiştir."
        paragraflar.append(giris_map.get(evrak_turu, varsayilan))

        # 2) Özet atfı (künyesiz gövdeden, cümle sınırında)
        ozet_cumleleri = self._ozet_cumleleri(state)
        if ozet_cumleleri:
            atif_ozne = "dilekçenizde" if evrak_turu == "dilekce" else "evrakta"
            paragraflar.append(
                f"Yapılan incelemede, {atif_ozne} özetle şu hususlara yer "
                f"verildiği görülmüştür: " + " ".join(ozet_cumleleri)
            )

        # 3) Mevzuat referans cümlesi: yalnızca benzerliği eşik üstünde
        #    olan eşleşmelere atıf yapılır; yoksa genel ifade kullanılır.
        basliklar = [
            m.get("baslik", "").strip()
            for m in (state.legislation_matches or [])[:2]
            if m.get("baslik")
            and float(m.get("benzerlik") or 0.0) >= MEVZUAT_ATIF_ESIGI
        ]
        ozne = "başvuru" if evrak_turu == "dilekce" else "evrak"
        if basliklar:
            paragraflar.append(
                f"Söz konusu {ozne}, {' ve '.join(basliklar)} "
                f"hükümleri kapsamında değerlendirilmiştir."
            )
        else:
            paragraflar.append(
                f"Söz konusu {ozne}, ilgili mevzuat hükümleri kapsamında "
                f"değerlendirilmiştir."
            )

        # 4) Eksik bilgi talebinde gövde farklı biter (liste şablonda ayrı)
        if yazi_turu == "eksik_bilgi_talep":
            paragraflar.append(
                "Ancak yapılan ön incelemede, başvurunuzun değerlendirilebilmesi "
                "için zorunlu olan bazı bilgi ve belgelerin eksik olduğu tespit "
                "edilmiştir."
            )
            return "\n\n".join(paragraflar)

        # 5) Sonuç/kapanışa hazırlık cümlesi
        ek_var = bool(_EK_BEYANI.search(state.raw_text or ""))
        sonuc_map = {
            "cevap_yazisi": (
                "Talebiniz ilgili birimimizce değerlendirmeye alınmış olup "
                "yapılacak iş ve işlemlerin sonucundan tarafınıza ayrıca "
                "bilgi verilecektir."
            ),
            "ust_yazi": (
                f"Söz konusu {'evrak ve ekleri' if ek_var else 'evrak'}, "
                f"değerlendirilmek ve gereği yapılmak üzere ilişikte "
                f"sunulmuştur."
            ),
            "bilgilendirme": (
                "Konu hakkında birimlerce yürütülecek iş ve işlemlerde "
                "yukarıda belirtilen hususların dikkate alınması gerekmektedir."
            ),
        }
        paragraflar.append(sonuc_map.get(yazi_turu, sonuc_map["ust_yazi"]))
        return "\n\n".join(paragraflar)

    @staticmethod
    def _birinci_sahis_mi(cumle: str) -> bool:
        """
        Cümlenin birinci şahıs (başvuru sahibi ağzından) yazılıp
        yazılmadığını Türkçe morfolojisiyle sezer: birinci şahıs zamirleri
        veya birinci şahıs fiil/iyelik ekleri (-DIğIm, -mAktAyIm, -Iyorum,
        "arz ederim" vb.) taşıyan kelime varsa True döner.
        """
        for token in re.findall(r"[^\W\d_]+", turkish_lower(cumle)):
            if token in _BIRINCI_SAHIS_KELIMELER or _BIRINCI_SAHIS_EK.search(token):
                return True
            if len(token) >= 7 and _BIRINCI_SAHIS_KOSAC.search(token):
                # hissedarıyım, abonesiyim (ad + 1. tekil koşacı)
                return True
        return False

    @staticmethod
    def _ozet_cumleleri(state: "AgentState", sinir: int = 350) -> list:
        """
        Özet atfı için künyesiz özet gövdesinden tam cümleler seçer.

        Kesme cümle sınırında yapılır (turkish_nlp.extract_sentences);
        toplam uzunluk sınırı aşılınca sonraki cümleler alınmaz. Özet
        gövdesi yoksa ham metnin cümlelerine düşülür.

        Resmî yazı üçüncü şahıs anlatım gerektirdiğinden, başvuru
        sahibinin birinci-şahıs cümleleri ("abonesi olduğum …",
        "… anlamış bulunmaktayım") atıf paragrafına aynen alınmaz; bu
        cümleler atlanır, kalan nesnel cümleler kullanılır. ':' veya ';'
        ile biten eksiltili parçalar da tam cümle sayılmaz.
        """
        kaynak = re.sub(r"\s+", " ", state.summary_body or "").strip()
        if not kaynak:
            kaynak = re.sub(r"\s+", " ", state.raw_text or "").strip()
        kaynak = re.sub(r"\[[^\]]*\]", " ", kaynak)

        secilen = []
        toplam = 0
        for cumle in extract_sentences(kaynak):
            cumle = cumle.strip().rstrip(";:,-").strip()
            if not cumle:
                continue
            if DraftWriterAgent._birinci_sahis_mi(cumle):
                continue
            if secilen and toplam + len(cumle) > sinir:
                break
            if cumle[-1] not in ".!?":
                cumle += "."
            secilen.append(cumle)
            toplam += len(cumle)
            if toplam >= sinir:
                break
        return secilen

    def _build_eksik_liste(self, missing_info: list) -> str:
        """Eksik bilgi/belge listesini numaralı biçimde üretir."""
        onemliler = [
            m for m in (missing_info or [])
            if m.get("oncelik") in ("kritik", "önemli")
        ] or (missing_info or [])
        if not onemliler:
            return "1) Başvuruya ilişkin ek bilgi ve belgeler."
        return "\n".join(
            f"{i}) {m.get('aciklama', m.get('alan', 'Eksik bilgi'))}"
            f" (öncelik: {m.get('oncelik', 'belirsiz')})"
            for i, m in enumerate(onemliler, 1)
        )

    def _build_talep_metni(self, yazi_turu: str, evrak_turu: str) -> str:
        """Eksik bilgi talep / iade-ikmal yazısının talep paragrafını üretir."""
        # İç belge için düzenleyen birime yönelik ikmal talebi
        # (vatandaş tebligatı ve süre şartı uygulanmaz)
        if yazi_turu == "iade_ikmal_notu":
            return (
                "Yukarıda belirtilen eksikliklerin düzenleyen birimce ikmal "
                "edilerek evrakın birimimize yeniden gönderilmesi "
                "gerekmektedir."
            )
        mevzuat = (
            "3071 sayılı Dilekçe Hakkı Kanunu ve ilgili mevzuat"
            if evrak_turu == "dilekce"
            else "ilgili mevzuat"
        )
        return (
            "Yukarıda belirtilen eksikliklerin, bu yazının tarafınıza "
            "tebliğinden itibaren 15 (on beş) gün içinde birimimize yazılı "
            "olarak veya elektronik ortamda iletilmesi gerekmektedir. "
            f"Belirtilen süre içinde tamamlanmayan başvurular hakkında "
            f"{mevzuat} hükümlerine göre işlem tesis edilecektir."
        )

    def _muhatap_kademesi(self, muhatap: str) -> Optional[int]:
        """
        Muhatap hitabından kurum kademesini (0 = üst kuruluş) çıkarır.

        Gerçek kişi ('Sayın ...') veya kademe hiyerarşisine oturmayan
        hitaplarda None döner — bu durumda hiyerarşi denetimi yapılmaz
        (belirsizlikte yanlış alarm üretilmez).
        """
        if not muhatap or muhatap.strip().startswith("Sayın"):
            return None
        # Yönelme ekini yalın hâle çevir: …LIĞINA → …LIĞI, …SİNE → …Sİ
        # (_hitaptan_kurum yalnız üst kuruluş eklerini kabul ettiğinden
        # burada kademe tablosunun tamamına karşı kendi soyması yapılır)
        hitap = _tr_upper(muhatap.strip())
        hitap = re.sub(r"\s+MAKAMINA$", "", hitap)
        hitap = re.sub(r"([GĞ])([IİUÜ])N[AE]$", r"\1\2", hitap)
        hitap = re.sub(r"(S[IİUÜ])N[AE]$", r"\1", hitap)
        kademe = self._kurum_kademesi(hitap)
        if kademe >= len(_KURUM_ONCELIK_KADEMELERI):
            return None
        return kademe

    @staticmethod
    def _gizlilik_damgasi(metin: str) -> str:
        """
        Metindeki gizlilik/kişiye özel damgasını döndürür (yoksa "").

        Damga tek başına satır hâlinde büyük harflerle aranır (Yön. m.25
        gizlilik dereceleri + m.26/4 KİŞİYE ÖZEL); gövde içindeki
        "gizlilik" benzeri sıradan kelimeler damga sayılmaz.
        """
        eslesme = _GIZLILIK_DAMGASI.search(metin or "")
        return eslesme.group(1) if eslesme else ""

    def _resolve_kapanis(
        self, yazi_turu: str, evrak_turu: str,
        muhatap: str = "", kurum_adi: str = "",
    ) -> str:
        """
        Kapanış ifadesini Yönetmelik m.16/12'ye göre seçer: alt makama
        'rica ederim', üst ve AYNI DÜZEYDEKİ makama 'arz ederim'
        (m.16/12-a), gerçek kişiye 'Saygılarımla.' / 'Bilgilerinize
        sunulur.' (m.16/12-e). Muhatap ve gönderen kademeleri tespit
        edilebiliyorsa hiyerarşi esas alınır; edilemiyorsa yazı türüne
        dayalı varsayılan davranış korunur.
        """
        if yazi_turu == "eksik_bilgi_talep":
            return "Bilgilerinize sunulur.\n\nSaygılarımla."
        if yazi_turu == "iade_ikmal_notu":
            return "Bilgilerinizi ve gereğini rica ederim."
        if yazi_turu == "cevap_yazisi" and evrak_turu == "dilekce":
            return "Bilgilerinize sunulur.\n\nSaygılarımla."
        if (muhatap or "").strip().startswith("Sayın"):
            return "Bilgilerinize sunulur.\n\nSaygılarımla."

        muhatap_kademe = self._muhatap_kademesi(muhatap)
        gonderen_kademe = (
            self._kurum_kademesi(kurum_adi) if kurum_adi
            else len(_KURUM_ONCELIK_KADEMELERI)
        )
        if (
            muhatap_kademe is not None
            and gonderen_kademe < len(_KURUM_ONCELIK_KADEMELERI)
        ):
            # Küçük kademe değeri = hiyerarşide üst kuruluş; üst VE denk
            # makama arz edilir (m.16/12-a)
            if muhatap_kademe <= gonderen_kademe:
                return "Bilgilerinize arz ederim."
            return "Bilgilerinize rica ederim."

        if yazi_turu == "ust_yazi":
            return "Bilgilerinize arz ederim."
        return "Bilgilerinize rica ederim."

    def _resolve_ekler(self, yazi_turu: str, raw_text: str) -> str:
        """
        Ek bölümü içeriğini üretir.

        Ek beyanı yalnızca gerçekten var olan ekler için yazılır: üst
        yazı ilgi evrakı ilişikte sunar (evrakın kendisi ektir; kaynak
        evrakta ek beyanı varsa ekleriyle birlikte). Diğer yazılarda ek
        üretilmediğinden "Yoktur." yazılır; uydurma ek beyan edilmez.
        """
        if yazi_turu == "ust_yazi":
            if _EK_BEYANI.search(raw_text or ""):
                return "İlgi evrak ve ekleri (1 adet)"
            return "İlgi evrak (1 adet)"
        return "Yoktur."

    def _resolve_dagitim(self, yazi_turu: str, muhatap: str) -> str:
        """Dağıtım (Gereği) satırını üretir (yalın hâlde, başlık biçiminde)."""
        if yazi_turu == "bilgilendirme":
            return "Tüm Birimler"
        temiz = muhatap.replace(" MAKAMINA", "").strip()
        if temiz.isupper():
            # Yönelme ekini yalın hâle çevir: …LIĞINA → …LIĞI, …LERE → …LER
            temiz = re.sub(r"([GĞ])([IİUÜ])N[AE]$", r"\1\2", temiz)
            temiz = re.sub(r"(S[IİUÜ])N[AE]$", r"\1", temiz)
            temiz = re.sub(r"(L[AE]R)[AE]$", r"\1", temiz)
            temiz = _tr_baslik(temiz)
        return temiz or "İlgili Birim"

    @staticmethod
    def _unvan_from_birim(birim_adi: str) -> str:
        """Birim adından imza bloğu unvanı türetir."""
        b = (birim_adi or "").strip()
        donusum = [
            ("Şube Müdürlüğü", "Şube Müdürü"),
            ("Genel Müdürlüğü", "Genel Müdür"),
            ("Genel Müdürlük", "Genel Müdür"),
            ("Müdürlüğü", "Müdürü"),
            ("Müşavirliği", "Müşaviri"),
            ("Daire Başkanlığı", "Daire Başkanı"),
            ("Dairesi", "Daire Başkanı"),
            ("Başkanlığı", "Başkanı"),
        ]
        for eski, yeni in donusum:
            if b.endswith(eski):
                return b[: -len(eski)] + yeni
        return "Birim Amiri"

    # ------------------------------------------------------------------
    # Format denetimi
    # ------------------------------------------------------------------

    def _validate_format(
        self, draft: str, yazi_turu: str, gizlilik_damgasi: str = ""
    ) -> dict:
        """
        Taslağı MADDE-REFERANSLI yönetmelik kontrol listesinden geçirir.

        Her kural {kural_id, kural, durum, detay, dayanak, agirlik}
        şemasıyla raporlanır; dayanaklar 2646 sayılı Yönetmeliğin resmî
        metninden fıkra düzeyinde doğrulanmıştır (jüri önünde madde
        gösterilebilir). Skor ağırlıklı ortalamadır: bilgi niteliğindeki
        kurallar (yabancı kelime vb.) düşük ağırlık taşır; bazı kurallar
        koşulludur ve bağlam yoksa listeye hiç eklenmez (yanlış alarm ve
        haksız skor cezası üretilmez).

        Returns:
            {"uygun": bool, "skor": float, "kontroller": [
                {kural_id, kural, durum, detay, dayanak, agirlik}]}
        """
        kontroller = []
        low = draft.lower()

        def ekle(
            kural_id: str, kural: str, durum: bool, detay: str,
            dayanak: str, agirlik: float = 1.0,
        ) -> None:
            kontroller.append({
                "kural_id": kural_id,
                "kural": kural,
                "durum": bool(durum),
                "detay": detay,
                "dayanak": dayanak,
                "agirlik": agirlik,
            })

        ekle(
            "tc_basligi",
            "T.C. başlığı",
            draft.lstrip().startswith("T.C."),
            "Başlığın ilk satırına 'T.C.' kısaltması yazılır.",
            "Yön. (2646) m.10/2",
        )
        ekle(
            "sayi_alani",
            "Sayı alanı",
            bool(re.search(r"Say[ıi]\s*:", draft)),
            "Belgelerde sayı bulunması zorunludur; 'Sayı :' alanı bulunmalıdır.",
            "Yön. (2646) m.11/1",
        )

        # Sayı biçimi: değer YA dürüst taslak ibaresi (gerçek sayıyı EBYS
        # verir — taslak sayı uydurmaz) YA m.11 desenine uygun olmalıdır
        sayi_eslesme = _SAYI_SATIRI.search(draft)
        if sayi_eslesme:
            sayi_degeri = sayi_eslesme.group(1).strip()
            sayi_uygun = (
                TASLAK_SAYI_IBARESI in sayi_degeri
                or bool(_SAYI_BICIM_DESENI.search(sayi_degeri))
            )
            ekle(
                "sayi_bicimi",
                "Sayı biçimi (E-DETSİS-SDP-kayıt)",
                sayi_uygun,
                "Sayı; E/Z/O ibaresi + Devlet Teşkilatı Numarası + standart "
                "dosya planı kodu + kayıt numarasından oluşur (örn. "
                "E-67915368-903.07.02-4752); taslakta sayı uydurulmaz, "
                "EBYS ibaresi kabul edilir.",
                "Yön. (2646) m.11/1-2",
                agirlik=0.5,
            )

        ekle(
            "tarih",
            "Tarih bilgisi",
            bool(re.search(r"\b\d{1,2}[./]\d{1,2}[./]\d{4}\b", draft)),
            "Tarih; gün, ay, yıl olarak rakamla ve aralarına nokta konularak "
            "yazılır (GG.AA.YYYY).",
            "Yön. (2646) m.12/1",
        )
        ekle(
            "konu_alani",
            "Konu alanı",
            bool(re.search(r"Konu\s*:", draft)),
            "'Konu :' alanı bulunmalıdır.",
            "Yön. (2646) m.13/1",
        )

        # Konu özlüğü: m.13/2 "kısa ve öz" — katı satır sınırı yönetmelikte
        # yoktur (m.13/1 taşan konuyu da düzenler); eşik mühendislik değeridir
        konu_eslesme = _KONU_SATIRI.search(draft)
        if konu_eslesme:
            konu_degeri = konu_eslesme.group(1).strip()
            ekle(
                "konu_kisa_oz",
                "Konu kısa ve öz",
                0 < len(konu_degeri) <= _KONU_AZAMI_UZUNLUK,
                "Konu, belgenin içeriği hakkında kısa ve öz bilgi barındırır "
                f"(uygulama eşiği {_KONU_AZAMI_UZUNLUK} karakter).",
                "Yön. (2646) m.13/2",
                agirlik=0.5,
            )

        ekle(
            "muhatap",
            "Muhatap satırı",
            bool(
                # Morfolojik yönelme deseni: …MÜDÜRLÜĞÜNE, …MÜŞAVİRLİĞİNE,
                # …BAŞKANLIĞINA, …VALİLİĞİNE vb.
                re.search(r"[A-ZÇĞİÖŞÜ]L[IİUÜ][GĞ][IİUÜ]N[AE]\b", draft)
                # Çoğul yönelme hitabı: …MÜDÜRLÜKLERİNE, …KURUMLARINA
                or re.search(r"[A-ZÇĞİÖŞÜ]L[AE]R[Iİ]?N[AE]\b", draft)
                or re.search(
                    r"\b(?:MAKAMINA|DAİRESİNE|KURULUNA|KURUMUNA|"
                    r"KOMİSYONUNA|BİRİMLERE|BİRİME|İLGİLİLERE|"
                    r"DAĞITIM YERLERİNE)\b",
                    draft,
                )
                or re.search(r"^Sayın\s+\S+", draft, re.MULTILINE)
            ),
            "Muhatap; belgenin gönderildiği idareyi (BÜYÜK HARF hitap) veya "
            "kişiyi ('Sayın ...') belirtir.",
            "Yön. (2646) m.14/1,3,6",
        )
        if yazi_turu in ("cevap_yazisi", "eksik_bilgi_talep", "ust_yazi", "iade_ikmal_notu"):
            ekle(
                "ilgi",
                "İlgi bölümü",
                bool(re.search(r"İlgi\s*:", draft)),
                "Bağlantılı belge bulunan yazıda 'İlgi :' bölümü bulunmalıdır.",
                "Yön. (2646) m.15/1",
            )
        ekle(
            "kapanis",
            "Uygun kapanış ifadesi (arz/rica/saygı)",
            any(
                k in low
                for k in ("arz ederim", "rica ederim", "saygılarımla",
                          "bilgilerinize sunulur", "arz olunur")
            ),
            "Yazı uygun ifadeyle bitmelidir: alt makama 'rica ederim', üst "
            "ve aynı düzeydeki makama 'arz ederim', kişiye 'Saygılarımla.' "
            "veya 'Bilgilerinize sunulur.'.",
            "Yön. (2646) m.16/12",
        )

        # Bitiş ifadesi ↔ muhatap hiyerarşisi tutarlılığı: yalnızca hem
        # muhatap hem gönderen kademesi tespit edilebiliyorsa denetlenir
        muhatap_satiri = self._draft_muhatap_satiri(draft)
        gonderen = self._draft_gonderen_kurum(draft)
        muhatap_kademe = (
            self._muhatap_kademesi(muhatap_satiri) if muhatap_satiri else None
        )
        gonderen_kademe = (
            self._kurum_kademesi(gonderen) if gonderen
            else len(_KURUM_ONCELIK_KADEMELERI)
        )
        if (
            muhatap_kademe is not None
            and gonderen_kademe < len(_KURUM_ONCELIK_KADEMELERI)
        ):
            arz_var = "arz ederim" in low or "arz olunur" in low
            rica_var = "rica ederim" in low
            karma = "arz ve rica ederim" in low or "arz/rica ederim" in low
            beklenen_arz = muhatap_kademe <= gonderen_kademe
            tutarli = karma or (arz_var if beklenen_arz else rica_var)
            ekle(
                "bitis_hiyerarsi",
                "Bitiş ifadesi muhatap hiyerarşisiyle tutarlı",
                tutarli,
                (
                    "Üst ve aynı düzeydeki makama 'arz ederim' kullanılmalıdır."
                    if beklenen_arz
                    else "Alt makama 'rica ederim' kullanılmalıdır."
                ),
                "Yön. (2646) m.16/12-a,b",
            )

        # Yabancı kelime uyarısı (bilgi niteliğinde, düşük ağırlık)
        yabanci = sorted({
            m.group(1).lower()
            for m in _YABANCI_KELIME_DESENI.finditer(draft)
        })
        ekle(
            "yabanci_kelime",
            "Yabancı kelime kullanılmaması",
            not yabanci,
            (
                "Zorunlu olmadıkça yabancı dillerden kelime kullanılmaz"
                + (f" (bulunan: {', '.join(yabanci)})" if yabanci else "")
                + "."
            ),
            "Yön. (2646) m.16/8",
            agirlik=0.25,
        )

        # Maddeleme biçimi: yalnızca harfli maddeleme kullanılmışsa denetlenir
        maddeleme_satirlari = _MADDELEME_SATIRI.findall(draft)
        if maddeleme_satirlari:
            hatalilar = [
                f"{harf}{isaret}"
                for harf, isaret in maddeleme_satirlari
                if isaret == "." or harf.isupper()
            ]
            ekle(
                "maddeleme",
                "Maddeleme biçimi (küçük harf + kapama parantezi)",
                not hatalilar,
                (
                    "Harfli maddelemede Türk alfabesindeki küçük harfler "
                    "kapama parantezi ile kullanılır: 'a)'"
                    + (f" (aykırı: {', '.join(sorted(set(hatalilar)))})"
                       if hatalilar else "")
                    + "."
                ),
                "Yön. (2646) m.16/10",
                agirlik=0.5,
            )

        ekle(
            "imza",
            "İmza bloğu",
            any(
                k in low
                for k in ("müdür", "başkan", "müşavir", "amiri",
                          "e-imza", "genel sekreter", "vali", "rektör")
            ),
            "İmza bloğunda ad-soyad/e-imza ibaresi ve unvan bulunmalıdır.",
            "Yön. (2646) m.17",
        )

        # Yetki devri düzeni: yalnızca taslakta "... a." ibaresi varsa
        # denetlenir (ör. "Vali a." satırının altında imzalayanın unvanı)
        yetki_satiri = _YETKI_DEVRI_SATIRI.search(draft)
        if yetki_satiri:
            kalan = draft[yetki_satiri.end():].lstrip("\n")
            sonraki_satir = kalan.split("\n", 1)[0].strip() if kalan else ""
            ekle(
                "yetki_devri_unvan",
                "Yetki devri imza düzeni ('... a.' + unvan)",
                bool(sonraki_satir),
                "Yetki devrinde '... a.' ibaresinin altında imzalayanın "
                "unvanı yer alır; iç yazışmalarda yetki devredenin unvanı "
                "kullanılmaz.",
                "Yön. (2646) m.17/9",
                agirlik=0.5,
            )

        # Gizlilik dereceli kaynak evrak: taslak damgayı taşımalı ve
        # yalnızca insan onayıyla kullanılmalıdır (kısıtlı mod)
        if gizlilik_damgasi:
            ekle(
                "gizlilik_kisitli",
                f"Gizlilik damgası taşınması ({gizlilik_damgasi})",
                gizlilik_damgasi in draft,
                "Kaynak evrak gizlilik dereceli; taslak aynı damgayı "
                "taşımalı ve insan onayı olmadan kullanılmamalıdır.",
                "Yön. (2646) m.25; m.26/4",
            )

        ekle(
            "yer_tutucu",
            "Boş yer tutucu kalmaması",
            not re.search(r"\[[^\]]+\]", draft) and "{" not in draft and "}" not in draft,
            "Taslakta doldurulmamış yer tutucu ([...] veya {...}) kalmamalıdır.",
            "iç kalite kuralı (halüsinasyon yasağı)",
        )

        toplam_agirlik = sum(k["agirlik"] for k in kontroller)
        skor = (
            round(
                sum(k["agirlik"] for k in kontroller if k["durum"]) / toplam_agirlik, 2
            )
            if toplam_agirlik
            else 0.0
        )
        yer_tutucu_temiz = next(
            (k["durum"] for k in kontroller if k["kural_id"] == "yer_tutucu"),
            False,
        )
        return {
            "uygun": skor >= 0.8 and yer_tutucu_temiz,
            "skor": skor,
            "kontroller": kontroller,
        }

    @staticmethod
    def _draft_muhatap_satiri(draft: str) -> str:
        """
        Taslak metninden muhatap (hitap) satırını çıkarır.

        Hitap; alan satırlarından (Sayı/Konu/İlgi) sonra gelen, BÜYÜK
        HARFLERLE yazılmış yönelme ekli satırdır ('... MÜDÜRLÜĞÜNE') veya
        'Sayın ...' satırıdır. Bulunamazsa "" döner.
        """
        for satir in (draft or "").split("\n"):
            s = satir.strip()
            if not s or ":" in s:
                continue
            if s.startswith("Sayın "):
                return s
            buyuk = s == _tr_upper(s)
            yonelme = bool(
                re.search(r"L[IİUÜ][GĞ][IİUÜ]N[AE]$", s)
                or re.search(r"L[AE]R[Iİ]?N[AE]$", s)
                or s.endswith(("MAKAMINA", "DAĞITIM YERLERİNE"))
            )
            if buyuk and yonelme:
                return s
        return ""

    @staticmethod
    def _draft_gonderen_kurum(draft: str) -> str:
        """
        Taslağın antetinden gönderen kurum adını çıkarır.

        Başlık düzeni m.10/2: ilk satır 'T.C.', ikinci satır idarenin adı.
        'T.C.' ile başlamayan taslakta "" döner (hiyerarşi denetimi yapılmaz).
        """
        satirlar = [s.strip() for s in (draft or "").split("\n") if s.strip()]
        if len(satirlar) >= 2 and satirlar[0].startswith("T.C."):
            return satirlar[1]
        return ""
