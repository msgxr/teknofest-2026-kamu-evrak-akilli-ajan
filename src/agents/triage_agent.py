"""
Triage (Akıllı Önceliklendirme) Agent — Evrakın aciliyetini ve yasal
işlem süresini tespit edip son işlem tarihini hesaplama.

Kamu kurumlarında "süreli evrak" takibi gerçek bir acı noktasıdır:
yasal cevap sürelerinin (dilekçe, bilgi edinme, idari dava vb.)
kaçırılması idari sorumluluk doğurur. Bu agent gelen evrakı üç
İLKESEL sinyal katmanıyla önceliklendirir (veri setine özel ezber yok;
her kural resmî/kamusal gerçekliğe dayanır):

1. Açık aciliyet ibareleri — Resmî Yazışmalarda Uygulanacak Usul ve
   Esaslar Hakkında Yönetmelik'e göre yazının aciliyeti "ÇOK İVEDİ" /
   "İVEDİ" damgasıyla, süreli oluşu "GÜNLÜDÜR" ibaresiyle belirtilir;
   uygulamada "ACELE" ve "SÜRELİDİR" ibareleri de aynı işlevi görür.
   Bu damgalar doğrudan ivedi/yüksek öncelik üretir. ("ACİL" sözcüğü
   bilinçli olarak sinyal sayılmaz: "acil durum planı" gibi konusal
   kullanımlarda yanlış pozitif üretir.)

2. Metin içi açık süre / son tarih — Yazıyı gönderen makamın koyduğu
   süre kayıtları: "en geç <tarih>", "<tarih> tarihine kadar",
   "<n> gün içinde/içerisinde", "<n> iş günü içinde" (sayı rakamla
   veya yazıyla olabilir). Göreli süreler evrak tarihine eklenerek,
   açık tarihler doğrudan alınarak son işlem tarihine çevrilir.

3. Yasal süre tablosu — Türün/içeriğin işaret ettiği kanuni cevap
   süreleri (modül sabiti YASAL_SURE_TABLOSU, her satırda "kaynak"):
   bilgi edinme → 4982 s. Kanun m.11 (15 iş günü); CİMER başvurusu →
   30 gün (CİMER uygulaması, 3071/4982 çerçevesi); idari itiraz/dava
   içeriği → 2577 s. İYUK m.7 (60 gün); dilekçe → 3071 s. Dilekçe
   Hakkı Kanunu m.7 (30 gün içinde cevap). 3071/4982/CİMER süreleri
   idareye yöneltilmiş bir BAŞVURUYU cevaplama yükümlülüğünden doğduğu
   için yalnızca başvuru niteliği taşıyan evraka uygulanır (tür=dilekçe
   veya metinde başvuru sözcüğü + istem ifadesi); tutanak/rapor/genelge/
   onaylı belge/iç bilgilendirmeye kanuni cevap süresi atanmaz.

İş günü hesabında hafta sonları (Cumartesi/Pazar) atlanır; resmî tatil
listesi TUTULMAZ — ulusal/dinî tatiller yıla ve hicri takvime bağlı
değiştiğinden offline sabit bir listeyle güvenilir izlenemez; hesap bu
nedenle "yaklaşık en geç tarih"tir ve gerekçede şeffaftır. Evrak tarihi
tespit edilemezse göreli/yasal süreler hesaplanamaz → "son_tarih": null
ve açıklayıcı "not" alanı üretilir. Birden fazla aday son tarih varsa
EN ERKEN olanı bağlayıcıdır (süre kaçırma riski en erken tarihte doğar).

Çıktı: state.triage = {"oncelik", "skor", "sinyaller", "yasal_sure",
"son_tarih", "kalan_gun", "gerekce", "not"}.

Şartname Referansı (Görev 1 + yenilikçilik ölçütü):
    "Evrak içeriğini analiz etme" — içerikten aciliyet/sürelilik
    çıkarımı ve süreli evrak takibi (özgün katkı).
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import TYPE_CHECKING, List, Optional, Tuple

from src.utils.turkish_nlp import turkish_lower

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.triage")

# ----------------------------------------------------------------------
# Tarih desenleri (turkish_lower uygulanmış metinde aranır)
# ----------------------------------------------------------------------
_AY_ADLARI = {
    "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5,
    "haziran": 6, "temmuz": 7, "ağustos": 8, "eylül": 9, "ekim": 10,
    "kasım": 11, "aralık": 12,
}
_AY_ALTERNATIF = "|".join(_AY_ADLARI)

# Desteklenen tarih biçimleri: 15.08.2026 / 15/08/2026 / 15-08-2026,
# "15 ağustos 2026", ISO 2026-08-15
_TARIH_STR = (
    r"(?:\d{1,2}[./-]\d{1,2}[./-]\d{4}"
    r"|\d{1,2}\s+(?:" + _AY_ALTERNATIF + r")\s+\d{4}"
    r"|\d{4}-\d{2}-\d{2})"
)

# ----------------------------------------------------------------------
# Katman 1 — Açık aciliyet ibareleri (resmî yazışma süre/ivedilik damgaları)
#
# Skorlar damganın resmî ağırlığını yansıtır: "ÇOK İVEDİ" en üst derece,
# "İVEDİ"/"ACELE" ivedi işlem, "GÜNLÜDÜR"/"SÜRELİDİR" yazının süreye
# bağlı olduğunu bildirir (tek başına ivedilik değil, süre takibi ister).
# "ivedi" kökü eklemeli biçimleri de kapsar (ivedilikle, ividir...):
# gövde metnindeki "ivedilikle sonuçlandırılması" da bir aciliyet talebidir.
# ----------------------------------------------------------------------
_ACILIYET_DAMGALARI: List[Tuple[re.Pattern, str, float]] = [
    (re.compile(r"\bçok\s+ivedi\b"), "ÇOK İVEDİ", 1.0),
    (re.compile(r"\bivedi\w*\b"), "İVEDİ", 0.9),
    (re.compile(r"\bacele\b"), "ACELE", 0.85),
    (re.compile(r"\bgünlüdür\b"), "GÜNLÜDÜR", 0.75),
    (re.compile(r"\bsürelidir\b"), "SÜRELİDİR", 0.75),
]

# ----------------------------------------------------------------------
# Katman 2 — Metin içi açık süre / son tarih desenleri
# ----------------------------------------------------------------------
# Açık son tarih: "en geç 15/08/2026", "24/07/2026 tarihine kadar",
# "30 eylül 2026 günü mesai bitimine kadar"
_ACIK_SON_TARIH_DESENLERI = [
    re.compile(r"en\s+geç\s+(" + _TARIH_STR + r")"),
    re.compile(
        r"(" + _TARIH_STR + r")\s+"
        r"(?:tarihine|gününe|günü\s+(?:mesai\s+bitimine|sonuna))\s+kadar"
    ),
]

# Göreli süre: "15 gün içinde", "5 iş günü içerisinde", "on beş gün içinde".
# Sayı rakamla (1-999) veya yazıyla (bir-iki kelime; sayı sözlüğüyle
# çözülür, çözülemeyen sözcükler — "birkaç gün içinde" — elenir).
_GORELI_SURE = re.compile(
    r"\b(?P<sayi>\d{1,3}(?!\d)|[a-zçğıöşü]+(?:\s+[a-zçğıöşü]+)?)\s+"
    r"(?P<is>iş\s+)?(?:takvim\s+)?gün[üu]?\s+iç(?:inde|erisinde)\b"
)

# Türkçe sayı sözlüğü (resmî metinlerde süreler sıkça yazıyla verilir:
# "otuz gün içinde", "on beş iş günü içinde"). 1-99 aralığı, ayrık
# ("on beş") ve bitişik ("onbeş") yazımlar desteklenir.
_SAYI_BIRLER = {
    "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5,
    "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9,
}
_SAYI_ONLAR = {
    "on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50,
    "altmış": 60, "yetmiş": 70, "seksen": 80, "doksan": 90,
}

# ----------------------------------------------------------------------
# Katman 3 — Yasal süre tablosu
#
# Her satır: ad, kaynak (mevzuat dayanağı), sure_gun, tip (takvim|is_gunu),
# anahtar_kelimeler (turkish_lower metinde aranır), turler (classification
# türü eşleşmesi), kanun_no (legislation_matches başlığı doğrulaması için),
# basvuru_kosulu (satırın yalnızca başvuru niteliği taşıyan evrakta
# uygulanması). SIRALAMA ÖNEMLİDİR: özel içerik kuralları (bilgi edinme,
# CİMER, İYUK) genel tür kuralından (dilekçe) önce denenir; böylece "bilgi
# edinme başvurusu" içerikli bir dilekçe 30 güne değil 15 iş gününe bağlanır.
#
# Başvuru niteliği ön koşulu (basvuru_kosulu=True): 3071 m.7, 4982 m.11 ve
# CİMER cevap süreleri idareye yöneltilmiş bir BAŞVURUYU cevaplama
# yükümlülüğünden doğar — kanun metinlerinde süre "başvuru/dilekçe" üzerine
# işler. Başvuru niteliği taşımayan iç belgeler (tutanak, rapor, genelge,
# onaylı belge, iç bilgilendirme) bu sürelere tabi değildir: bir faaliyet
# raporunun CİMER'den söz etmesi ortada cevaplanacak bir başvuru olduğu
# anlamına gelmez. 2577 satırında koşul aranmaz: dava açma süresi başvuru
# değil, işlemin tebliği üzerine işler. Metin içi açık süre kayıtları
# (Katman 2) her evrak türünde çalışmaya devam eder.
#
# Not (İYUK): 60 günlük dava açma süresi hukuken TEBLİĞ tarihinden başlar;
# tebliğ tarihi evraktan bilinemediği için evrak tarihi yaklaşık başlangıç
# alınır ve bu yaklaşım kaynak metninde belirtilir.
# ----------------------------------------------------------------------
YASAL_SURE_TABLOSU: List[dict] = [
    {
        "ad": "bilgi_edinme",
        "kaynak": "4982 sayılı Bilgi Edinme Hakkı Kanunu m.11 — başvuruya 15 iş günü içinde cevap verilir",
        "sure_gun": 15,
        "tip": "is_gunu",
        "anahtar_kelimeler": ["bilgi edinme", "4982"],
        "turler": [],
        "kanun_no": "4982",
        "basvuru_kosulu": True,
    },
    {
        "ad": "cimer_basvurusu",
        "kaynak": "CİMER başvuru uygulaması (3071/4982 çerçevesi) — 30 gün içinde cevap verilir",
        "sure_gun": 30,
        "tip": "takvim",
        "anahtar_kelimeler": ["cimer", "cumhurbaşkanlığı iletişim merkezi"],
        "turler": [],
        "kanun_no": "cimer",
        "basvuru_kosulu": True,
    },
    {
        "ad": "idari_dava_itiraz",
        "kaynak": "2577 sayılı İdari Yargılama Usulü Kanunu m.7 — dava açma süresi 60 gündür (süre hukuken tebliğle başlar; tebliğ tarihi bilinemediğinden evrak tarihi yaklaşık başlangıç alınmıştır)",
        "sure_gun": 60,
        "tip": "takvim",
        "anahtar_kelimeler": [
            "2577", "idari yargılama", "iptal davası", "tam yargı davası",
            "yürütmenin durdurulması", "dava açma süresi", "idare mahkemesi",
        ],
        "turler": [],
        "kanun_no": "2577",
        "basvuru_kosulu": False,
    },
    {
        "ad": "dilekce_cevabi",
        "kaynak": "3071 sayılı Dilekçe Hakkı Kanunu m.7 — sonuç 30 gün içinde gerekçeli olarak bildirilir",
        "sure_gun": 30,
        "tip": "takvim",
        "anahtar_kelimeler": ["3071"],
        "turler": ["dilekce"],
        "kanun_no": "3071",
        "basvuru_kosulu": True,
    },
]

# Başvuru niteliği taşımayan evrak türleri: tutanak/rapor/genelge/onaylı
# belge kurum işleyişinin kayıt ve düzenleme belgeleridir, bilgilendirme
# yazısı cevap beklemeyen iç bilgi paylaşımıdır; hiçbiri idareye
# yöneltilmiş bir başvuru değildir ve kanuni cevap süresi doğurmaz.
_BASVURU_DISI_TURLER = frozenset(
    {"tutanak", "rapor", "genelge", "onayli_belge", "bilgilendirme"}
)

# Tür bilgisi başvuru niteliğini tek başına belirlemiyorsa (üst yazı,
# cevap yazısı, diger...) metinden dilbilgisel kanıt aranır: "başvuru /
# müracaat / dilekçe" sözcük ailesinden bir sözcüğün bir istem ifadesiyle
# ("talep", "arz", "rica", "istirham") BİRLİKTE geçmesi, evrakın bir
# başvuruyu konu edindiğini gösterir (ör. CİMER havale yazısı: "başvuruda
# ... talep etmektedir"). Tek başına kapanış nezaketi ("bilgilerinize arz
# ederim") her resmî yazıda bulunduğundan başvuru kanıtı sayılmaz.
_BASVURU_SOZCUGU = re.compile(r"\b(?:başvur|müracaat|dilekçe)\w*")
_ISTEM_IFADESI = re.compile(r"\b(?:talep|arz|rica|istirham)\w*")

# legislation_matches doğrulaması için asgari benzerlik: bu eşiğin
# altındaki mevzuat eşleşmeleri yasal süre kanıtı sayılmaz.
_MEVZUAT_BENZERLIK_ESIGI = 0.6

# ----------------------------------------------------------------------
# Skor ağırlıkları ve öncelik eşikleri
#
# Skor = sinyallerin azamisi (en güçlü kanıt önceliği belirler).
# Ağırlık sırası ilkeseldir: resmî ivedilik damgası > gönderenin koyduğu
# açık süre > kanuni takip süresi. Yaklaşan/geçmiş son tarih ayrıca
# eskalasyon sinyali üretir (süre kaçırma riski büyüdükçe öncelik artar).
# ----------------------------------------------------------------------
_SKOR_ACIK_SURE = 0.6      # metin içi açık süre / son tarih
_SKOR_YASAL_SURE = 0.4     # kanuni süre (standart iş yükü; tek başına acil değil)
_SKOR_SURE_GECMIS = 1.0    # son tarih geçmiş → derhal işlem
_SKOR_SURE_KRITIK = 0.85   # kalan ≤ 3 gün
_SKOR_SURE_YAKIN = 0.7     # kalan ≤ 7 gün

_ESIK_IVEDI = 0.8
_ESIK_YUKSEK = 0.55


def _sayi_coz(ifade: str) -> Optional[int]:
    """
    Rakamla veya yazıyla verilmiş bir sayıyı çözer ("15", "on beş",
    "onbeş", "otuz" → int). Çözülemeyen ifadeler için None döner.

    İki kelimelik adaylarda tam ifade çözülemezse son kelime denenir
    ("geç yedi" → 7): göreli süre deseni bir önceki bağlam sözcüğünü
    yanlışlıkla yakalayabilir.
    """

    def tek_kelime(k: str) -> Optional[int]:
        if k in _SAYI_ONLAR:
            return _SAYI_ONLAR[k]
        if k in _SAYI_BIRLER:
            return _SAYI_BIRLER[k]
        # Bitişik yazım: "onbeş", "yirmibeş"
        for on_kelime, on_deger in _SAYI_ONLAR.items():
            kalan = k[len(on_kelime):]
            if k.startswith(on_kelime) and kalan in _SAYI_BIRLER:
                return on_deger + _SAYI_BIRLER[kalan]
        return None

    ifade = ifade.strip()
    if ifade.isdigit():
        deger = int(ifade)
        return deger if deger > 0 else None
    kelimeler = ifade.split()
    if len(kelimeler) == 2:
        onlar, birler = tek_kelime(kelimeler[0]), tek_kelime(kelimeler[1])
        if onlar is not None and onlar % 10 == 0 and birler is not None and birler < 10:
            return onlar + birler
        return tek_kelime(kelimeler[1])
    if len(kelimeler) == 1:
        return tek_kelime(kelimeler[0])
    return None


def _tarih_coz(metin: str) -> Optional[date]:
    """
    Tarih dizgesini datetime.date'e çevirir; geçersiz/tanınmayan
    biçimlerde None döner. Desteklenen biçimler: gg.aa.yyyy (./-/),
    "15 ağustos 2026" (Türkçe ay adı), ISO yyyy-mm-dd.
    """
    s = turkish_lower(metin.strip())

    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None

    m = re.fullmatch(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            return None

    m = re.fullmatch(r"(\d{1,2})\s+(" + _AY_ALTERNATIF + r")\s+(\d{4})", s)
    if m:
        try:
            return date(int(m.group(3)), _AY_ADLARI[m.group(2)], int(m.group(1)))
        except ValueError:
            return None
    return None


def is_gunu_ekle(baslangic: date, gun_sayisi: int) -> date:
    """
    Başlangıç tarihine hafta sonlarını (Cumartesi/Pazar) atlayarak
    n iş günü ekler.

    Resmî tatil listesi tutulmaz: ulusal/dinî tatiller yıla ve hicri
    takvime bağlı değiştiğinden offline sabit listeyle güvenilir
    izlenemez. Sonuç bu nedenle "yaklaşık en geç" tarihtir; tatile denk
    gelen günler gerçek süreyi yalnızca İLERİ atar, yani hesap ihtiyatlı
    (erken) taraftadır ve süre kaçırma riski doğurmaz.
    """
    gun = baslangic
    kalan = gun_sayisi
    while kalan > 0:
        gun += timedelta(days=1)
        if gun.weekday() < 5:  # 0-4: Pazartesi-Cuma
            kalan -= 1
    return gun


class TriageAgent:
    """
    Akıllı önceliklendirme (triage) agent'ı.

    raw_text, classification, extracted_info ve legislation_matches
    girdilerinden aciliyet damgalarını, metin içi süre kayıtlarını ve
    kanuni cevap sürelerini çıkarır; son işlem tarihini hesaplayıp
    state.triage sözlüğüne yazar.
    """

    def __init__(self, bugun: Optional[date] = None) -> None:
        """
        Args:
            bugun: "Kalan gün" hesabının referans günü. Verilmezse
                gerçek sistem tarihi kullanılır (parametre test ve
                geçmişe dönük simülasyon içindir).
        """
        self._bugun = bugun
        logger.info("Triage (Önceliklendirme) Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Evrakı önceliklendirir ve sonucu state.triage'a yazar."""
        text = state.raw_text or ""
        tl = turkish_lower(text)
        bugun = self._bugun or date.today()

        sinyaller: List[dict] = []
        not_mesaji: Optional[str] = None

        # Katman 1 — açık aciliyet ibareleri
        skorlar = self._damga_sinyalleri(tl, sinyaller)

        # Evrak tarihi (göreli/yasal süre hesabının başlangıcı)
        evrak_tarihi = self._evrak_tarihi_coz(state, text)

        # Katman 2 — metin içi açık süre / son tarih
        son_tarih_adaylari: List[Tuple[date, str]] = []
        goreli_sure_var = self._acik_sureler(
            tl, evrak_tarihi, sinyaller, skorlar, son_tarih_adaylari
        )

        # Katman 3 — yasal süre tablosu
        yasal_sure = self._yasal_sure_bul(
            tl, state.classification or {}, state.legislation_matches or []
        )
        yasal_sure_cikti = None
        if yasal_sure:
            yasal_sure_cikti = {
                "kaynak": yasal_sure["kaynak"],
                "sure_gun": yasal_sure["sure_gun"],
                "tip": yasal_sure["tip"],
            }
            birim = "iş günü" if yasal_sure["tip"] == "is_gunu" else "gün"
            sinyaller.append({
                "tip": "yasal_sure",
                "deger": f"{yasal_sure['sure_gun']} {birim}",
                "aciklama": yasal_sure["kaynak"],
            })
            skorlar.append(_SKOR_YASAL_SURE)
            if evrak_tarihi:
                if yasal_sure["tip"] == "is_gunu":
                    hedef = is_gunu_ekle(evrak_tarihi, yasal_sure["sure_gun"])
                else:
                    hedef = evrak_tarihi + timedelta(days=yasal_sure["sure_gun"])
                son_tarih_adaylari.append((hedef, yasal_sure["kaynak"]))

        # Evrak tarihi yokken hesaplanamayan süreler için not düş
        if evrak_tarihi is None and (goreli_sure_var or yasal_sure):
            not_mesaji = (
                "Evrak tarihi tespit edilemediği için göreli/yasal süreden "
                "son işlem tarihi hesaplanamadı; evrak tarihini doğrulayıp "
                "süreyi elle takibe alın."
            )

        # Son tarih: birden fazla aday varsa EN ERKEN olanı bağlayıcıdır
        son_tarih: Optional[date] = None
        son_tarih_kaynagi = ""
        if son_tarih_adaylari:
            son_tarih, son_tarih_kaynagi = min(son_tarih_adaylari, key=lambda a: a[0])

        kalan_gun: Optional[int] = None
        if son_tarih is not None:
            kalan_gun = (son_tarih - bugun).days
            self._sure_eskalasyonu(kalan_gun, sinyaller, skorlar)

        skor = round(max(skorlar), 2) if skorlar else 0.0
        oncelik = self._oncelik_belirle(skor)
        gerekce = self._gerekce_olustur(
            oncelik, sinyaller, son_tarih, son_tarih_kaynagi, kalan_gun, not_mesaji
        )

        state.triage = {
            "oncelik": oncelik,
            "skor": skor,
            "sinyaller": sinyaller,
            "yasal_sure": yasal_sure_cikti,
            "son_tarih": son_tarih.isoformat() if son_tarih else None,
            "kalan_gun": kalan_gun,
            "gerekce": gerekce,
            "not": not_mesaji,
        }
        logger.info(
            f"Triage: oncelik={oncelik}, skor={skor}, "
            f"son_tarih={state.triage['son_tarih']}, kalan_gun={kalan_gun}"
        )
        return state

    # ------------------------------------------------------------------
    # Sinyal katmanları
    # ------------------------------------------------------------------

    @staticmethod
    def _damga_sinyalleri(tl: str, sinyaller: List[dict]) -> List[float]:
        """
        Katman 1: açık aciliyet ibarelerini toplar; skor listesi döndürür.

        "ÇOK İVEDİ" eşleşince yalın "İVEDİ" deseni atlanır (aynı damganın
        alt dizgisi olduğundan çift sinyal üretmemek için).
        """
        skorlar: List[float] = []
        cok_ivedi_eslesti = False
        for desen, etiket, skor in _ACILIYET_DAMGALARI:
            if etiket == "İVEDİ" and cok_ivedi_eslesti:
                continue
            if desen.search(tl):
                if etiket == "ÇOK İVEDİ":
                    cok_ivedi_eslesti = True
                sinyaller.append({
                    "tip": "aciliyet_damgasi",
                    "deger": etiket,
                    "aciklama": (
                        f"Resmî yazışma aciliyet/süre ibaresi tespit edildi: {etiket} "
                        "(Resmî Yazışmalarda Uygulanacak Usul ve Esaslar Hk. Yönetmelik)."
                    ),
                })
                skorlar.append(skor)
        return skorlar

    def _evrak_tarihi_coz(self, state: "AgentState", text: str) -> Optional[date]:
        """
        Evrak tarihini date olarak döndürür.

        Öncelik sırası: extracted_info.evrak_tarihi (bilgi çıkarım
        agent'ının atıf tarihlerinden ayrıştırdığı asıl tarih) →
        extracted_info.tarihler'in ilk öğesi ("Tarih :" alanı listenin
        başına alınır) → ham metindeki "Tarih :" satırı (agent tek
        başına çalıştırıldığında asgari yedek).
        """
        extracted = state.extracted_info or {}
        adaylar = [extracted.get("evrak_tarihi", "")]
        tarihler = extracted.get("tarihler") or []
        if tarihler:
            adaylar.append(tarihler[0])
        for aday in adaylar:
            if aday:
                cozulen = _tarih_coz(str(aday))
                if cozulen:
                    return cozulen

        # Yedek: "Tarih :" alan satırı (bilgi çıkarımı çalışmamışsa)
        m = re.search(
            r"(?m)^\s*tarih[i]?\s*:\s*(" + _TARIH_STR + r")",
            turkish_lower(text),
        )
        if m:
            return _tarih_coz(m.group(1))
        return None

    @staticmethod
    def _acik_sureler(
        tl: str,
        evrak_tarihi: Optional[date],
        sinyaller: List[dict],
        skorlar: List[float],
        son_tarih_adaylari: List[Tuple[date, str]],
    ) -> bool:
        """
        Katman 2: açık son tarihleri ve göreli süreleri toplar.

        Açık tarihler doğrudan aday listesine girer; göreli süreler
        evrak tarihi biliniyorsa takvim/iş günü hesabıyla tarihe
        çevrilir. Evrak tarihi olmadan çevrilemeyen göreli süre varsa
        True döndürülür (çağıran "not" alanını doldurur).
        """
        gorulen_tarihler = set()
        for desen in _ACIK_SON_TARIH_DESENLERI:
            for m in desen.finditer(tl):
                hedef = _tarih_coz(m.group(1))
                if hedef is None or hedef in gorulen_tarihler:
                    continue
                gorulen_tarihler.add(hedef)
                sinyaller.append({
                    "tip": "acik_son_tarih",
                    "deger": hedef.isoformat(),
                    "aciklama": (
                        f'Metinde açık son tarih kaydı bulundu: "{m.group(0)}".'
                    ),
                })
                skorlar.append(_SKOR_ACIK_SURE)
                son_tarih_adaylari.append(
                    (hedef, f'metindeki açık süre kaydı ("{m.group(0)}")')
                )

        hesaplanamayan_var = False
        gorulen_sureler = set()
        for m in _GORELI_SURE.finditer(tl):
            gun_sayisi = _sayi_coz(m.group("sayi"))
            if gun_sayisi is None:
                continue  # "birkaç gün içinde" gibi sayısal olmayan ifadeler
            is_gunu_mu = bool(m.group("is"))
            if (gun_sayisi, is_gunu_mu) in gorulen_sureler:
                continue
            gorulen_sureler.add((gun_sayisi, is_gunu_mu))
            birim = "iş günü" if is_gunu_mu else "gün"
            if evrak_tarihi:
                if is_gunu_mu:
                    hedef = is_gunu_ekle(evrak_tarihi, gun_sayisi)
                else:
                    hedef = evrak_tarihi + timedelta(days=gun_sayisi)
                aciklama = (
                    f'Metin içi süre kaydı ("{m.group(0)}"): evrak tarihine '
                    f"{gun_sayisi} {birim} eklenerek son tarih {hedef.isoformat()} "
                    "hesaplandı."
                )
                son_tarih_adaylari.append(
                    (hedef, f'metindeki süre kaydı ("{m.group(0)}")')
                )
            else:
                hesaplanamayan_var = True
                aciklama = (
                    f'Metin içi süre kaydı ("{m.group(0)}") bulundu ancak evrak '
                    "tarihi tespit edilemediği için son tarih hesaplanamadı."
                )
            sinyaller.append({
                "tip": "metin_ici_sure",
                "deger": f"{gun_sayisi} {birim}",
                "aciklama": aciklama,
            })
            skorlar.append(_SKOR_ACIK_SURE)
        return hesaplanamayan_var

    @staticmethod
    def _basvuru_niteligi(tl: str, tur: str) -> bool:
        """
        Evrakın "başvuru niteliği" taşıyıp taşımadığını belirler.

        Kanuni cevap süreleri (3071/4982/CİMER) idareye yöneltilmiş bir
        başvuruyu cevaplama yükümlülüğünden doğar; bu yüzden:
          - dilekçe türü tanım gereği başvurudur → True,
          - tutanak/rapor/genelge/onaylı belge/bilgilendirme kurum içi
            kayıt-bilgi belgeleridir, başvuru değildir → False,
          - diğer türlerde (üst yazı, cevap yazısı, diger...) metinden
            dilbilgisel kanıt aranır: başvuru sözcük ailesi + istem
            ifadesi birlikte geçmelidir (bkz. _BASVURU_SOZCUGU).
        """
        if tur == "dilekce":
            return True
        if tur in _BASVURU_DISI_TURLER:
            return False
        return bool(_BASVURU_SOZCUGU.search(tl) and _ISTEM_IFADESI.search(tl))

    @staticmethod
    def _yasal_sure_bul(
        tl: str, classification: dict, legislation_matches: list
    ) -> Optional[dict]:
        """
        Katman 3: yasal süre tablosundan ilk eşleşen satırı döndürür.

        basvuru_kosulu=True satırlar yalnızca başvuru niteliği taşıyan
        evrakta değerlendirilir (bkz. _basvuru_niteligi): kanuni cevap
        süresi, başvuru olmayan iç belgeye (tutanak/rapor/genelge vb.)
        atanmaz. Koşulu geçen satırlar için eşleşme kanıtları (herhangi
        biri yeter): (a) anahtar kelime metinde geçer, (b) evrak türü
        satırın türler listesindedir, (c) mevzuat agent'ı ilgili kanunu
        yeterli benzerlikle eşleştirmiştir. Tablo sırası özelden genele
        gittiği için ilk eşleşme en özgül kuraldır.
        """
        tur = classification.get("tur", "")
        basvuru_niteligi = TriageAgent._basvuru_niteligi(tl, tur)
        mevzuat_basliklari = [
            turkish_lower(m.get("baslik", ""))
            for m in legislation_matches
            if m.get("benzerlik", 0) >= _MEVZUAT_BENZERLIK_ESIGI
        ]
        for satir in YASAL_SURE_TABLOSU:
            if satir.get("basvuru_kosulu") and not basvuru_niteligi:
                continue
            if any(anahtar in tl for anahtar in satir["anahtar_kelimeler"]):
                return satir
            if tur in satir["turler"]:
                return satir
            if any(satir["kanun_no"] in baslik for baslik in mevzuat_basliklari):
                return satir
        return None

    @staticmethod
    def _sure_eskalasyonu(
        kalan_gun: int, sinyaller: List[dict], skorlar: List[float]
    ) -> None:
        """
        Son tarihe kalan güne göre eskalasyon sinyali üretir.

        Süre kaçırma riski yaklaştıkça öncelik yükselir: geçmiş →
        derhal işlem (idari sorumluluk doğmuş olabilir), ≤3 gün →
        kritik, ≤7 gün → yakın takip.
        """
        if kalan_gun < 0:
            sinyaller.append({
                "tip": "sure_durumu",
                "deger": f"{-kalan_gun} gün gecikmiş",
                "aciklama": (
                    "Son işlem tarihi GEÇMİŞ: derhal işlem yapılmalı; süre "
                    "aşımı idari sorumluluk doğurabilir."
                ),
            })
            skorlar.append(_SKOR_SURE_GECMIS)
        elif kalan_gun <= 3:
            sinyaller.append({
                "tip": "sure_durumu",
                "deger": f"kalan {kalan_gun} gün",
                "aciklama": "Son işlem tarihine 3 gün veya daha az kaldı.",
            })
            skorlar.append(_SKOR_SURE_KRITIK)
        elif kalan_gun <= 7:
            sinyaller.append({
                "tip": "sure_durumu",
                "deger": f"kalan {kalan_gun} gün",
                "aciklama": "Son işlem tarihine 7 gün veya daha az kaldı.",
            })
            skorlar.append(_SKOR_SURE_YAKIN)

    # ------------------------------------------------------------------
    # Öncelik ve gerekçe
    # ------------------------------------------------------------------

    @staticmethod
    def _oncelik_belirle(skor: float) -> str:
        """Skoru öncelik sınıfına çevirir (ivedi ≥ 0.8, yüksek ≥ 0.55)."""
        if skor >= _ESIK_IVEDI:
            return "ivedi"
        if skor >= _ESIK_YUKSEK:
            return "yuksek"
        return "normal"

    @staticmethod
    def _gerekce_olustur(
        oncelik: str,
        sinyaller: List[dict],
        son_tarih: Optional[date],
        son_tarih_kaynagi: str,
        kalan_gun: Optional[int],
        not_mesaji: Optional[str],
    ) -> str:
        """İnsan tarafından okunabilir tek paragraflık gerekçe üretir."""
        parcalar: List[str] = []
        etiketler = {
            "aciliyet_damgasi": "aciliyet ibaresi",
            "acik_son_tarih": "açık son tarih",
            "metin_ici_sure": "metin içi süre",
            "yasal_sure": "yasal süre",
            "sure_durumu": "süre durumu",
        }
        for s in sinyaller:
            parcalar.append(f"{etiketler.get(s['tip'], s['tip'])}: {s['deger']}")

        gerekce = f"Öncelik '{oncelik}'"
        if parcalar:
            gerekce += " — " + "; ".join(parcalar)
        else:
            gerekce += (
                " — aciliyet ibaresi, metin içi süre kaydı veya yasal süre "
                "bulunmadı; olağan işlem sırası uygulanır"
            )
        if son_tarih:
            gerekce += f". Son işlem tarihi: {son_tarih.isoformat()}"
            if son_tarih_kaynagi:
                gerekce += f" ({son_tarih_kaynagi})"
            if kalan_gun is not None:
                gerekce += (
                    f", kalan {kalan_gun} gün" if kalan_gun >= 0
                    else f", {-kalan_gun} gün gecikmiş"
                )
        if not_mesaji:
            gerekce += f". Not: {not_mesaji}"
        return gerekce + "."
