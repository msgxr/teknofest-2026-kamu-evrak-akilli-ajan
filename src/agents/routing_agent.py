"""
Birim Yönlendirme Agent — Evrakı doğru birime yönlendirme.

Şartname Referansı (Görev 2):
    "Evrakın içeriğine göre doğru birime yönlendirme önerisinde bulunması"

Skorlama tasarımı:
    - Anahtar kelime ağırlıkları: güçlü sinyal kelimeler 2-3x ağırlıklıdır.
    - Kelimeler sözcük başı sınırında aranır (Türkçe ek çekimlerine izin
      verilir: "bütçe" → "bütçesinin"); böylece alakasız köklerin içindeki
      rastlantısal parçalar ("vatandaş" içindeki "atan" gibi) sinyal üretmez.
    - Konu alanındaki eşleşmeye ekstra ağırlık verilir.
    - Muhatap (hitap satırı) içinde birim adı geçiyorsa güçlü bonus; metinde
      (kurum_adlari) yalnızca adı geçen birimlere zayıf bonus uygulanır —
      resmî bir evrakta adı geçen her birim evrakın muhatabı değildir.
    - Evrak türü bonusları eklenir. Makam oluru/onaylı belgede genel
      müdürlük bonusu, en yüksek içerik skoruna ORANTILI hesaplanır
      (karar mercii ile işi yürüten birim ayrımı): içerik sinyali zayıfsa
      üst yönetim önde kalır, baskın konu sinyali (örn. ihale onay
      belgesi → satınalma, stratejik plan oluru → strateji) kazanabilir.
    - Güven, en iyi skorun ilk iki skorun toplamına oranı (ayrışma) ile
      sinyal kapsamının birleşiminden hesaplanır.
    - İki birim skoru çok yakınsa (fark < %15) ve LLM varsa nihai karar
      LLM'e sorulur; kullanılan yöntem 'yontem' alanına yazılır.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Optional

from src.utils.turkish_nlp import TR_KUCUK_HARF_SINIFI, govde_desen

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.routing")

# Kamu kurumlarında tipik birim yapısı.
# "anahtar_kelimeler": kelime → ağırlık (güçlü/ayırt edici sinyaller 2-3x).
BIRIMLER = {
    "yazi_isleri": {
        "ad": "Yazı İşleri Müdürlüğü",
        "aciklama": "Genel yazışma ve evrak yönetimi",
        "anahtar_kelimeler": {
            "yazışma": 1.5, "evrak": 1.0, "arşiv": 2.0, "dosyalama": 2.0,
            "kayıt": 1.0, "evrak takip": 2.5, "resmi yazışma": 2.5,
            "gelen evrak": 2.5, "havale": 1.5,
        },
    },
    "hukuk": {
        "ad": "Hukuk Müşavirliği",
        "aciklama": "Hukuki konular ve mevzuat danışmanlığı",
        # İlke: Sorumluluk/tazminat hukukunun resmî terimleri (yasal işlem
        # başlatılması, zararın tazmini, kusur tespiti, üçüncü şahıs) idari
        # süreçlerde hukuk birimine sevkin tipik gerekçeleridir.
        "anahtar_kelimeler": {
            "hukuk": 2.5, "dava": 3.0, "mahkeme": 3.0, "mevzuat": 1.5,
            "kanun": 1.0, "yönetmelik": 1.0, "itiraz": 2.0, "icra": 2.5,
            "tebligat": 2.0, "sözleşme": 1.5, "hukuki görüş": 3.0,
            "savunma": 2.0, "yasal işlem": 3.0, "tazmin": 2.5,
            "kusur": 2.0, "üçüncü şahıs": 2.0,
        },
    },
    "insan_kaynaklari": {
        "ad": "İnsan Kaynakları Müdürlüğü",
        "aciklama": "Personel işlemleri ve özlük hakları",
        # İlke: Kamu teşkilatında personel yaşam döngüsünün tamamı (işe alım,
        # atama/nakil, intibak, terfi, izin, hizmet içi eğitim, performans
        # değerlendirme, emeklilik) İK biriminin görev alanıdır. Bu süreçlerin
        # resmî terminolojisi ("personel alımı", "naklen atanma", "kademe
        # ilerlemesi", "eğitim ihtiyaç analizi") güçlü sinyaldir.
        "anahtar_kelimeler": {
            "personel": 2.0, "atama": 2.5, "atan": 2.0, "naklen": 2.5,
            "terfi": 3.0, "izin": 1.5, "sicil": 2.5, "özlük": 3.0,
            "emeklilik": 2.5, "kadro": 2.5, "intibak": 3.0,
            "kademe ilerleme": 3.0, "görevlendirme": 2.0, "işe alım": 3.0,
            "personel alım": 3.0, "disiplin": 2.0, "insan kaynakları": 3.0,
            "uzaktan çalışma": 2.0, "performans değerlendirme": 2.5,
            "hizmet içi eğitim": 3.0, "eğitim ihtiyaç": 2.5,
            "eğitim plan": 2.0, "hizmet belgesi": 2.5,
        },
    },
    "mali_hizmetler": {
        "ad": "Mali Hizmetler Müdürlüğü",
        "aciklama": "Mali işlemler ve bütçe yönetimi",
        # İlke: 5018 sayılı Kamu Mali Yönetimi terminolojisi (bütçe, ödenek,
        # tahakkuk, tasarruf tedbirleri, hakediş) mali hizmetler biriminin
        # görev alanını tanımlar. "mali" tam sözcük olarak aranır (bkz.
        # TAM_KELIMELER: "maliyet" bir ihale/satınalma terimidir).
        "anahtar_kelimeler": {
            "bütçe": 3.0, "ödeme": 2.0, "mali": 2.0, "finans": 2.0,
            "harcama": 2.5, "gelir": 1.5, "vergi": 2.5, "ödenek": 3.0,
            "tahsis": 2.0, "fatura": 2.5, "muhasebe": 3.0, "tahakkuk": 3.0,
            "tasarruf": 2.5, "hakediş": 3.0,
        },
    },
    "bilgi_islem": {
        "ad": "Bilgi İşlem Müdürlüğü",
        "aciklama": "Bilgi teknolojileri ve dijital altyapı",
        "anahtar_kelimeler": {
            "bilişim": 3.0, "yazılım": 2.5, "donanım": 2.5, "sistem": 0.5,
            "ağ bağlantısı": 3.0, "ağ altyapısı": 3.0, "siber": 3.0,
            "bilgi güvenliği": 3.0, "teknoloji": 1.5, "sunucu": 2.5,
            "ebys": 2.5, "e-imza": 1.5, "internet": 2.0, "lisans": 1.5,
            "antivirüs": 3.0, "veri tabanı": 2.5, "bulut": 2.0,
            "bilgi işlem": 2.5,
        },
    },
    "strateji": {
        "ad": "Strateji Geliştirme Dairesi",
        "aciklama": "Stratejik planlama ve kurumsal performans",
        # İlke: "planlama" ve "performans" tek başına genel sözcüklerdir —
        # her birim plan yapar, personel performansı ise İK konusudur. Bu
        # yüzden düşük ağırlıklıdır; strateji birimine özgü mevzuat
        # terimleri (stratejik plan, kurumsal performans programı, performans
        # göstergesi, faaliyet raporu, iç kontrol) güçlü sinyaldir.
        "anahtar_kelimeler": {
            "strateji": 3.0, "stratejik plan": 3.0, "planlama": 1.0,
            "performans": 1.0, "performans gösterge": 3.0,
            "performans program": 3.0, "kurumsal performans": 3.0,
            "kalkınma plan": 2.5, "eylem plan": 2.0, "kalite": 2.0,
            "istatistik": 2.5, "faaliyet raporu": 2.5, "iç kontrol": 2.5,
            "hedef": 1.0,
        },
    },
    "basin_halkla_iliskiler": {
        "ad": "Basın ve Halkla İlişkiler Müdürlüğü",
        "aciklama": "Basın ilişkileri ve vatandaş başvuruları",
        "anahtar_kelimeler": {
            "basın": 3.0, "medya": 2.5, "halkla ilişkiler": 3.0,
            "şikayet": 2.0, "vatandaş": 1.5, "dilekçe": 1.0, "duyuru": 1.5,
            "basın bülteni": 3.0, "cimer": 3.0, "bilgi edinme": 2.0,
        },
    },
    "destek_hizmetleri": {
        "ad": "Destek Hizmetleri Müdürlüğü",
        "aciklama": "Satınalma, ihale ve destek hizmetleri",
        # İlke: Kamu ihale mevzuatının süreç terimleri (mal/hizmet alımı,
        # yaklaşık maliyet, teknik şartname, doğrudan temin, muayene ve
        # kabul) ile idari destek hizmetleri (taşınır/demirbaş, taşınma,
        # personel servisi, yemekhane, temizlik, güvenlik hizmeti) bu
        # birimin görev alanıdır.
        "anahtar_kelimeler": {
            "ihale": 3.0, "satınalma": 3.0, "satın alma": 3.0,
            "hizmet alımı": 2.5, "mal alımı": 2.5, "doğrudan temin": 3.0,
            "yaklaşık maliyet": 2.5, "teknik şartname": 2.0,
            "muayene ve kabul": 3.0, "lojistik": 2.5, "taşınır": 2.5,
            "demirbaş": 2.5, "kırtasiye": 2.5, "bakım": 1.5, "onarım": 2.0,
            "temizlik": 2.0, "tedarik": 2.5, "malzeme": 1.5,
            "taşınma": 2.0, "servis": 1.5, "yemekhane": 2.5,
            "hizmet binası": 2.0, "güvenlik hizmeti": 2.0,
            "destek hizmetleri": 2.5,
        },
    },
    "genel_mudurluk": {
        "ad": "Genel Müdürlük",
        "aciklama": "Üst yönetim kararları",
        # İlke: Makam oluru akışının resmî kalıpları ("... olurlarınıza arz
        # ederim", "Uygun görüşle arz ederim", onay bloğundaki "Onaylayan"
        # ibaresi, makama hitap) evrakın üst yönetim kararı gerektirdiğini
        # gösterir; bunlar kurumdan bağımsız, yazışma usulüne dayalı
        # sinyallerdir.
        "anahtar_kelimeler": {
            "makam": 1.5, "onay": 1.0, "direktif": 2.5, "talimat": 1.5,
            "üst yönetim": 3.0, "genel müdür": 2.0, "olurlarınıza": 2.5,
            "olurlarına": 2.5, "onayınıza arz": 2.5, "onaylayan": 1.5,
            "uygun görüşle": 1.5, "makam oluru": 3.0, "başkanlık oluru": 3.0,
        },
    },
}

# Evrak türüne göre sabit birim bonusları.
# genelge bonusu düşüktür: genelgeyi üst yönetim yayımlar ama evrak,
# konusunu yürüten birime yönlendirilir.
# onayli_belge → genel_mudurluk bonusu bu tabloda DEĞİLDİR; içerik
# skoruna orantılı hesaplanır (bkz. ONAYLI_BELGE_BONUS_ORANI).
TUR_BONUSLARI = {
    ("dilekce", "basin_halkla_iliskiler"): 2.0,
    ("dilekce", "yazi_isleri"): 1.0,
    ("tutanak", "hukuk"): 1.5,
    ("rapor", "strateji"): 1.5,
    ("genelge", "genel_mudurluk"): 1.0,
    ("ust_yazi", "yazi_isleri"): 0.5,
}

# Onaylı belge (makam oluru) bonusu — İLKE: makam oluru, KARAR MERCİİ
# (üst yönetim) ile İŞİ YÜRÜTEN birimi ayırır. Olur kalıpları
# ("olurlarınıza arz ederim", "Onaylayan", "uygun görüşle") HER makam
# olurunda bulunur; bunlar evrakın türünü gösterir, konuyu yürüten
# birimi göstermez. Bu yüzden genel müdürlük bonusu sabit bir değer
# yerine evraktaki EN YÜKSEK içerik skoruna orantılı verilir:
#     bonus = ORAN × max(içerik skorları)
# Böylece karar akışı şuna indirgenir: bir birimin konu sinyali, üst
# yönetimin karar-mercii sinyalinin yaklaşık 1/(1-ORAN) katını (0.4 için
# ~1.7x) aşıyorsa evrak işi yürüten birime havale edilir (örn. ihale
# onay belgesi → satınalma, stratejik plan oluru → strateji); konu
# sinyali zayıf kaldığında ise bonus üst yönetimi önde tutar. Sabit
# bonus (+5) güçlü konu sinyalini körlemesine bastırıyordu; orantılı
# bonus içerikten bağımsız bir tavan koymaz.
ONAYLI_BELGE_BONUS_ORANI = 0.4

# Tam sözcük eşleşmesi gerektiren kısa kökler: bu sözcükler başka anlamdaki
# köklerin ÖNEKİ olduğu için ek çekimine izin verilmez. Örn. "mali"
# (finansal) sözcüğü, ihale/satınalma terimi olan "maliyet"in önekidir;
# önek eşleşmesine izin verilirse her ihale evrakı mali birime kayar.
TAM_KELIMELER = {"mali"}

# LLM ayrıştırmasının devreye gireceği göreli skor farkı eşiği
LLM_ESIK = 0.15


def _tr_lower(text: str) -> str:
    """Türkçe'ye uygun küçük harfe çevirme (İ→i, I→ı)."""
    return (text or "").replace("İ", "i").replace("I", "ı").lower()


# Türkçe küçük harf kümesi (_tr_lower sonrası metin için)
_TR_HARF = TR_KUCUK_HARF_SINIFI
_DESEN_CACHE: dict = {}


def _kelime_adedi(text_lower: str, kelime: str) -> int:
    """
    Anahtar kelimenin metindeki geçiş sayısını sözcük sınırına saygılı sayar.

    Resmî yazışma Türkçesi eklerle çekimlenir ("bütçe" → "bütçesinin",
    "görevlendirme onayı" → konu satırında aynen); bu yüzden kelimenin
    SONUNDA ek çekimine izin verilir (önek eşleşmesi). Kelimenin BAŞI ise
    bir sözcük sınırında olmalıdır; aksi halde alakasız köklerin içindeki
    rastlantısal parçalar ("vatandaş" içindeki "atan" gibi) yanlış sinyal
    üretir. Desen `govde_desen` ile üretilir: süreksiz sert ünsüzle
    (p, ç, t, k) biten kökler ünlüyle başlayan ek önünde yumuşadığından
    ("lojistik" → "lojistiği", "sonuç" → "sonucu") çekimli biçimler de
    yakalanır. TAM_KELIMELER'deki kökler için ek çekimine (dolayısıyla
    yumuşamaya) izin verilmez.
    """
    desen = _DESEN_CACHE.get(kelime)
    if desen is None:
        if kelime in TAM_KELIMELER:
            kaynak = "(?<![%s])%s(?![%s])" % (_TR_HARF, re.escape(kelime), _TR_HARF)
        else:
            kaynak = govde_desen(kelime, _TR_HARF)
        desen = re.compile(kaynak)
        _DESEN_CACHE[kelime] = desen
    return len(desen.findall(text_lower))


class RoutingAgent:
    """
    Birim yönlendirme agent'ı.

    Evrak içeriğini ağırlıklı anahtar kelime skorlaması, konu/muhatap
    sinyalleri ve evrak türü bonuslarıyla analiz ederek hangi birime
    yönlendirilmesi gerektiğini belirler ve açıklayıcı gerekçe sunar.
    """

    def __init__(self) -> None:
        logger.info("Yönlendirme Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Evrakı uygun birime yönlendirir."""
        suggestion = self._determine_routing(
            state.raw_text,
            state.classification.get("tur", ""),
            state.extracted_info or {},
        )
        state.routing_suggestion = suggestion

        logger.info(
            f"Yönlendirme önerisi: {suggestion.get('birim', 'Belirsiz')} "
            f"(güven: {suggestion.get('guven', 0):.2f}, "
            f"yöntem: {suggestion.get('yontem', '')})"
        )
        return state

    # ------------------------------------------------------------------
    # Skorlama
    # ------------------------------------------------------------------

    def _determine_routing(self, text: str, evrak_turu: str, extracted: dict) -> dict:
        """Evrak için yönlendirme önerisi oluşturur."""
        text_lower = _tr_lower(text)
        konu_lower = _tr_lower(extracted.get("konu") or "")
        muhatap_lower = _tr_lower(str(extracted.get("muhatap") or ""))
        kurum_muhatap = _tr_lower(
            " ".join(extracted.get("kurum_adlari") or [])
            + " " + str(extracted.get("muhatap") or "")
        )

        scores = {}
        signals = {}
        for birim_key, birim_info in BIRIMLER.items():
            skor, sinyaller = self._score_birim(
                birim_key, birim_info, text_lower, konu_lower,
                kurum_muhatap, muhatap_lower,
            )
            scores[birim_key] = skor
            signals[birim_key] = sinyaller

        # Evrak türü bonusları içerik skorlarının ÜZERİNE eklenir; onaylı
        # belge bonusu en yüksek içerik skoruna orantılı olduğundan önce
        # tüm birimlerin içerik skorları hesaplanmış olmalıdır.
        max_icerik = max(scores.values()) if scores else 0.0
        for birim_key in BIRIMLER:
            tur_bonus = self._tur_bonusu(evrak_turu, birim_key, max_icerik)
            if tur_bonus > 0:
                scores[birim_key] += tur_bonus
                signals[birim_key].append(
                    (f"evrak türü ({evrak_turu}) katkısı", tur_bonus)
                )
                signals[birim_key].sort(key=lambda x: x[1], reverse=True)

        if not scores or max(scores.values()) <= 0:
            return {
                "birim": BIRIMLER["yazi_isleri"]["ad"],
                "birim_kodu": "yazi_isleri",
                "gerekce": (
                    "Evrak içeriğinde belirli bir birime işaret eden sinyal "
                    "bulunamadı; genel yazışma birimi olan Yazı İşleri "
                    "Müdürlüğüne yönlendirilmesi önerildi."
                ),
                "guven": 0.3,
                "alternatifler": [],
                "yontem": "kural_tabanli",
            }

        sirali = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        best_key, best_score = sirali[0]
        second_score = sirali[1][1] if len(sirali) > 1 else 0.0
        yontem = "kural_tabanli"

        # Skorlar çok yakınsa LLM'e danış (opsiyonel)
        if second_score > 0 and (best_score - second_score) < LLM_ESIK * best_score:
            llm_key = self._llm_tiebreak(text, sirali[:3])
            if llm_key and llm_key in BIRIMLER:
                if llm_key != best_key:
                    logger.info(f"LLM ayrıştırması birimi değiştirdi: {best_key} → {llm_key}")
                best_key = llm_key
                best_score = scores[llm_key]
                yontem = "llm_ayristirma"

        guven = self._compute_confidence(best_score, second_score)
        gerekce = self._build_rationale(
            best_key, signals[best_key], evrak_turu, best_score
        )
        alternatifler = [
            {"birim": BIRIMLER[k]["ad"], "birim_kodu": k, "skor": round(v, 2)}
            for k, v in sirali[1:4]
            if v > 0 and k != best_key
        ]

        return {
            "birim": BIRIMLER[best_key]["ad"],
            "birim_kodu": best_key,
            "gerekce": gerekce,
            "guven": guven,
            "alternatifler": alternatifler,
            "yontem": yontem,
            "eslesen_sinyaller": [
                {"sinyal": s, "katki": round(k, 2)}
                for s, k in signals[best_key][:5]
            ],
        }

    def _score_birim(
        self,
        birim_key: str,
        birim_info: dict,
        text_lower: str,
        konu_lower: str,
        kurum_muhatap: str,
        muhatap_lower: str,
    ) -> tuple:
        """
        Tek bir birim için ağırlıklı İÇERİK skoru hesaplar (tür bonusu
        hariç; tür bonusları _determine_routing'de içerik skorlarının
        üzerine eklenir).

        Returns:
            (toplam_skor, [(sinyal_aciklamasi, katki), ...]) — katkıya göre sıralı
        """
        skor = 0.0
        sinyaller = []

        # 1) Ağırlıklı anahtar kelime eşleşmesi (tekrar sayısı küçük bonus verir)
        for kelime, agirlik in birim_info["anahtar_kelimeler"].items():
            adet = _kelime_adedi(text_lower, kelime)
            if adet <= 0:
                continue
            katki = agirlik * (1.0 + 0.25 * min(adet - 1, 3))
            # Konu alanında geçen kelimeye ekstra ağırlık
            if konu_lower and _kelime_adedi(konu_lower, kelime) > 0:
                katki += agirlik
                sinyaller.append((f"'{kelime}' (Konu alanında)", katki))
            else:
                sinyaller.append((f"'{kelime}'", katki))
            skor += katki

        # 2) Birim adının geçtiği yere göre kademeli bonus:
        #    - Muhatap (hitap satırı): evrak doğrudan o birime yazılmıştır →
        #      güçlü bonus.
        #    - Konu alanı: evrakın konusu o birimle ilgilidir → orta bonus.
        #    - Metin gövdesi (kurum_adlari): resmî bir evrakta adı geçen her
        #      birim muhatap değildir (taşınan/katılan/görüş veren birimler
        #      de anılır) → zayıf bonus.
        kisa_ad = self._kisa_birim_adi(birim_info["ad"])
        if kisa_ad and kisa_ad in muhatap_lower:
            skor += 4.0
            sinyaller.append(("birim adı muhatap (hitap) bilgisinde geçiyor", 4.0))
        elif kisa_ad and konu_lower and kisa_ad in konu_lower:
            skor += 3.0
            sinyaller.append(("birim adı Konu alanında geçiyor", 3.0))
        elif kisa_ad and kisa_ad in kurum_muhatap:
            skor += 2.0
            sinyaller.append(("birim adı evrak metninde geçiyor", 2.0))

        sinyaller.sort(key=lambda x: x[1], reverse=True)
        return skor, sinyaller

    @staticmethod
    def _tur_bonusu(evrak_turu: str, birim_key: str, max_icerik: float) -> float:
        """
        Evrak türüne göre birim bonusunu hesaplar.

        Onaylı belge (makam oluru) → genel müdürlük bonusu sabit değil,
        evraktaki en yüksek içerik skoruna orantılıdır (gerekçe için bkz.
        ONAYLI_BELGE_BONUS_ORANI): karar mercii üst yönetim olsa da,
        baskın konu sinyali işi yürüten birimi gösteriyorsa evrak o birime
        havale edilir. Diğer tür bonusları TUR_BONUSLARI tablosundan gelir.
        """
        if (evrak_turu, birim_key) == ("onayli_belge", "genel_mudurluk"):
            return round(ONAYLI_BELGE_BONUS_ORANI * max_icerik, 2)
        return TUR_BONUSLARI.get((evrak_turu, birim_key), 0.0)

    @staticmethod
    def _kisa_birim_adi(ad: str) -> str:
        """Birim adının ayırt edici kısa halini döndürür ('... Müdürlüğü' → '...')."""
        kisa = _tr_lower(ad)
        for ek in (" müdürlüğü", " müşavirliği", " dairesi"):
            if kisa.endswith(ek):
                return kisa[: -len(ek)].strip()
        return kisa

    @staticmethod
    def _compute_confidence(best: float, second: float) -> float:
        """
        Güven skorunu hesaplar.

        Ayrışma (en iyi skorun ilk iki skor toplamına oranı) ile sinyal
        kapsamı (skor büyüklüğü) birleştirilir; böylece tek zayıf sinyalle
        yüksek güven üretilmez.
        """
        if best <= 0:
            return 0.3
        ayrisma = best / (best + second) if (best + second) > 0 else 1.0
        kapsam = min(best / 8.0, 1.0)
        guven = ayrisma * (0.6 + 0.4 * kapsam)
        return round(max(0.3, min(guven, 0.97)), 2)

    def _build_rationale(
        self, birim_key: str, sinyaller: list, evrak_turu: str, skor: float
    ) -> str:
        """Açıklayıcı gerekçe metni üretir (eşleşen ilk 3 sinyal + tür katkısı)."""
        birim = BIRIMLER[birim_key]
        kelime_sinyalleri = [s for s, _ in sinyaller if s.startswith("'")][:3]

        parcalar = [
            f"Evrak içeriği '{birim['aciklama']}' kapsamında değerlendirilmiştir"
        ]
        if kelime_sinyalleri:
            parcalar.append(
                f"metinde {', '.join(kelime_sinyalleri)} sinyalleri eşleşti"
            )
        if any("muhatap (hitap)" in s for s, _ in sinyaller):
            parcalar.append("muhatap/hitap bilgisinde birim adı doğrudan geçiyor")
        if any(s.startswith("evrak türü") for s, _ in sinyaller):
            parcalar.append(f"evrak türü ({evrak_turu}) bu birimi destekliyor")
        parcalar.append(f"toplam skor {skor:.1f}")
        return "; ".join(parcalar) + "."

    # ------------------------------------------------------------------
    # LLM ayrıştırması (opsiyonel)
    # ------------------------------------------------------------------

    def _llm_tiebreak(self, text: str, adaylar: list) -> Optional[str]:
        """
        Skorları yakın olan birimler arasında LLM ile karar verir.

        LLM yoksa veya hata oluşursa None döner (kural tabanlı sonuç korunur).
        """
        try:
            from src.models.llm_wrapper import GUVENLIK_SISTEM_EKI, belge_blogu, get_default_llm

            llm = get_default_llm()
            if not llm.is_available():
                return None

            aday_str = "\n".join(
                f"- {key}: {BIRIMLER[key]['ad']} — {BIRIMLER[key]['aciklama']} "
                f"(skor: {skor:.1f})"
                for key, skor in adaylar
            )
            # GÜVENLİK: evrak metni belge_blogu ile "yalnızca veri" olarak
            # işaretlenir; seçim zaten aday listesiyle sınırlı doğrulanır
            # (dolaylı prompt injection savunması, OWASP LLM01)
            prompt = f"""Aşağıdaki evrak metninin hangi birime yönlendirilmesi gerektiğine karar ver.

{belge_blogu(text, 2000)}

Skorları birbirine yakın aday birimler:
{aday_str}

Evrakın ana talebini/konusunu dikkate alarak yalnızca bu adaylar arasından en uygun birimi seç."""

            result = llm.generate_json(
                prompt,
                schema_hint='{"birim_kodu": "aday_birim_key", "gerekce": "kısa açıklama"}',
                system_prompt=(
                    "Sen kamu kurumlarında evrak havalesi yapan bir yönlendirme asistanısın."
                    + GUVENLIK_SISTEM_EKI
                ),
            )
            secim = str(result.get("birim_kodu", "")).strip()
            if secim in dict(adaylar):
                return secim
            logger.warning(f"LLM geçersiz birim kodu döndürdü: {secim}")
            return None
        except Exception as e:
            logger.warning(f"LLM ayrıştırması başarısız, kural tabanlı sonuç korunuyor: {e}")
            return None
