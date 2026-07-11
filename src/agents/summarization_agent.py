"""
Özet Oluşturma Agent — Evrak özeti oluşturma.

İki yol:
    1. LLM yolu: tür, konu ve çıkarılan bilgilerle bağlamlandırılmış
       prompt ile 2-4 cümlelik resmî/nesnel özet.
    2. Kural tabanlı yol: gerçek extractive özetleme — cümleler pozisyon
       ağırlığı, konu/anahtar kelime örtüşmesi ve uzunluk normalizasyonu
       ile skorlanır; en iyi 2-4 cümle orijinal sırayla birleştirilir.

İki alan doldurulur:
    - state.summary: başında tek satır künye ("[Tür] | Konu: … | Tarih: …")
      bulunan, ekranda gösterime yönelik özet.
    - state.summary_body: künyesiz, cümle bütünlüğü korunmuş özet gövdesi;
      taslak yazımı gibi metin üreten adımlar YALNIZCA bu alanı kullanır
      (künye ayraçları resmî yazı gövdesine sızmaz).

Şartname Referansı (Görev 1):
    "Evraka ilişkin kısa ve öz bir özet oluşturabilme"
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import TYPE_CHECKING, Optional

from src.utils.turkish_nlp import (
    extract_sentences,
    remove_stopwords,
    turkish_lower,
    turkish_upper,
)

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.summarization")

# Özet gövdesine alınmayacak üstveri/antet satır önekleri
# (":" etrafındaki boşluklar sıkıştırıldıktan sonra karşılaştırılır)
_META_ONEKLERI = (
    "t.c.", "sayı:", "sayi:", "konu:", "tarih:", "ilgi:", "ek:", "ekler:",
    "dağıtım:", "gereği:", "bilgi:", "imza", "ad soyad:", "unvan:", "tel:",
    "telefon:", "e-posta:", "eposta:", "adres:", "toplantı tarihi:",
    "toplantı saati:", "toplantı yeri:", "katılımcılar:", "imzalar:",
)

# Antet satırlarını (kurum adı) gövdeden ayıklamak için kurum ekleri:
# Türk kamu yönetiminde kurum/birim adları iyelik ekli unvan adlarıyla
# ("... Müdürlüğü", "... Koordinatörlüğü", "... Birimi") veya yalın
# kurumsal biçimle ("Genel Sekreterlik", "Genel Müdürlük") biter; antette
# ve imza bloğunda geçen bu satırlar cümle değildir.
_KURUM_EKLERI = (
    "bakanlığı", "müdürlüğü", "başkanlığı", "müşavirliği", "dairesi",
    "kurumu", "kurulu", "ajansı", "enstitüsü", "valiliği", "kaymakamlığı",
    "belediyesi", "üniversitesi", "rektörlüğü", "başkanı", "müdürü",
    "koordinatörlüğü", "sekreterliği", "dekanlığı", "komutanlığı",
    "idaresi", "komisyonu", "amirliği", "şefliği", "birimi",
    "müdürlük", "başkanlık", "sekreterlik", "koordinatörlük", "rektörlük",
    "müşavirlik",
)

# Ana talep/karar bildiren ipucu kalıpları (cümle skoruna bonus)
_IPUCU_KALIPLARI = (
    "arz ederim", "rica ederim", "arz olunur", "kararlaştırıl", "talep",
    "gerekmektedir", "önem taşı", "tespit edil", "uygun bulun",
    "karar veril", "bilgilerinize", "sonuçlanmıştır",
)

# Adres/iletişim satırı tespiti (turkish_lower uygulanmış satırda aranır):
# adres birimi kısaltmaları (mahalle/sokak/cadde/bulvar/apartman), kapı
# numarası kalıbı ("No: 14/3") ve iletişim etiketleri. Dilekçe altındaki
# gönderici adres blokları cümle değildir; özet gövdesine alınmaz.
_ADRES_BIRIM_DESENI = re.compile(
    r"\b(?:mah|mahalle|mahallesi|sok|sk|sokak|sokağı|cad|cadde|caddesi|"
    r"bulv|bulvar|bulvarı|apt|apartman|apartmanı)\b\.?"
)
_KAPI_NO_DESENI = re.compile(r"\bno\s*[:.]?\s*\d")
_ILETISIM_DESENI = re.compile(
    r"\b(?:tel|telefon|gsm|faks|fax)\b\s*[:.]|e-?posta|@"
)

# İmza bloğu tespiti (Resmî Yazışma Yönetmeliği md. 14: imza bloğu
# ad-soyad, unvan ve imza/e-imza ibaresinden oluşur; soyadı BÜYÜK harfle
# yazılır). Bu satırlar cümle değildir; özet gövdesine alınmaz.
_EIMZA_DESENI = re.compile(r"\(\s*(?:e-?\s*)?imza(?:l[ıi]d[ıi]r)?\s*\)", re.IGNORECASE)
# İmza bloğu / katılımcı satırı: "Ad SOYAD" (yönetmelik biçimi: soyadı
# BÜYÜK harfle) ile başlayan ve cümle sonu noktalaması taşımayan satır
# ("Şebnem ALAZLI", "İlker SAZAKLI - Tesisler Birimi Sorumlusu");
# tutanaklarda katılımcı/imza satırları bu biçimdedir, cümle değildir.
_IMZA_AD_DESENI = re.compile(
    r"^(?:[A-ZÇĞİÖŞÜ][\wçğıöşü.]*\s+){1,3}[A-ZÇĞİÖŞÜ]{2,}(?:$|\s*[-–—,:])"
)
# İmza bloğu unvan/rol satırı sonekleri: birim-unvan kısaltmaları
# ("Şb.", "Md.", "Yrd.", "Uzm."), iyelik ekli unvan adları ve
# tutanak/onay rol adları ("Onaylayan", "Düzenleyen") — kısa satır
# sonunda cümle kurmaz.
_IMZA_UNVAN_SONU = re.compile(
    r"(?:\bşb\.?|\bmd\.?|\byrd\.?|\buzm\.?|şefi|memuru|uzmanı|sorumlusu|"
    r"görevlisi|mühendisi|teknisyeni|teknikeri|koordinatörü|"
    r"amiri|onaylayan|düzenleyen|hazırlayan|kontrol eden)$"
)


class SummarizationAgent:
    """
    Özet oluşturma agent'ı.

    Evrak metninden kısa ve öz bir özet üretir. LLM erişilebilirse
    bağlamlı prompt kullanır; aksi halde skorlamalı extractive özetlemeye
    düşer. Her iki yolda da özetin başına künye satırı eklenir.
    """

    def __init__(self) -> None:
        logger.info("Özet Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """
        Evrak metninden özet oluşturur.

        state.summary'ye künyeli (ekran) özet, state.summary_body'ye
        künyesiz gövde yazılır; taslak üretimi gövdeyi kullanır.
        """
        text = state.raw_text
        tur_adi = state.classification.get("tur_adi", "")
        extracted = state.extracted_info or {}

        if not text.strip():
            state.summary = "Metin çıkarılamadığı için özet oluşturulamadı."
            state.summary_body = ""
            return state

        body = self._generate_summary(text, tur_adi, extracted)
        kunye = self._build_kunye(tur_adi, extracted)
        state.summary_body = body
        state.summary = f"{kunye}\n{body}" if kunye else body
        logger.info(f"Özet oluşturuldu: {len(state.summary)} karakter")
        return state

    # ------------------------------------------------------------------
    # Künye
    # ------------------------------------------------------------------

    @staticmethod
    def _build_kunye(tur_adi: str, extracted: dict) -> str:
        """Tek satırlık künye üretir: "[Tür] | Konu: … | Tarih: …" (varsa)."""
        parts = []
        if tur_adi and tur_adi != "Bilinmiyor":
            parts.append(f"[{tur_adi}]")
        konu = (extracted.get("konu") or "").strip()
        if konu:
            parts.append(f"Konu: {konu}")
        tarihler = extracted.get("tarihler") or []
        if tarihler:
            parts.append(f"Tarih: {tarihler[0]}")
        return " | ".join(parts)

    # ------------------------------------------------------------------
    # LLM yolu
    # ------------------------------------------------------------------

    def _generate_summary(self, text: str, evrak_turu: str, extracted: dict) -> str:
        """
        Özet gövdesini üretir: önce LLM denenir, hata/yokluk durumunda
        kural tabanlı extractive özetlemeye düşülür.

        Args:
            text: Evrak metni
            evrak_turu: Belirlenen evrak türü adı
            extracted: Çıkarılan bilgiler

        Returns:
            Özet gövde metni
        """
        try:
            from src.models.llm_wrapper import GUVENLIK_SISTEM_EKI, belge_blogu, get_default_llm

            llm = get_default_llm()
            if not llm.is_available():
                raise RuntimeError("LLM backend'i yok (offline mod)")

            tarihler = ", ".join((extracted.get("tarihler") or [])[:3]) or "-"
            referanslar = ", ".join((extracted.get("referans_numaralari") or [])[:3]) or "-"
            muhatap = extracted.get("muhatap") or "-"
            konu = extracted.get("konu") or "Belirtilmemiş"

            # GÜVENLİK: evrak metni belge_blogu ile "yalnızca veri" olarak
            # işaretlenir (dolaylı prompt injection savunması, OWASP LLM01)
            prompt = f"""Aşağıdaki resmî evrakın kısa bir özetini yaz.

Evrak Türü: {evrak_turu or 'Bilinmiyor'}
Konu: {konu}
Tespit Edilen Tarihler: {tarihler}
Muhatap: {muhatap}
Referans No: {referanslar}

{belge_blogu(text, 4000)}

Kurallar:
1. Özet 2-4 cümle olsun ve tek paragraf halinde yazılsın.
2. Resmî ve nesnel bir üslup kullan; üçüncü şahıs anlatımı tercih et
   (ör. "… talep edilmektedir", "… karara bağlanmıştır").
3. Evrakın ana amacını, talebini veya alınan kararları öne çıkar.
4. Metindeki tarih, sayı ve tutar gibi somut bilgileri koru.
5. Özet dışında hiçbir başlık, açıklama veya madde işareti ekleme."""

            summary = llm.generate(
                prompt,
                system_prompt=(
                    "Sen kamu kurumlarında resmî yazışma ve evrak yönetimi "
                    "konusunda uzman bir asistansın. Yanıtlarını resmî, "
                    "nesnel ve açık bir Türkçe ile verirsin."
                    + GUVENLIK_SISTEM_EKI
                ),
            )
            summary = re.sub(r"\s+", " ", summary).strip()
            if summary:
                return summary
            raise ValueError("LLM boş özet döndürdü")

        except Exception as e:
            logger.info(f"LLM özeti kullanılamadı, extractive yönteme geçildi: {e}")
            return self._extractive_summary(text, extracted.get("konu", ""))

    # ------------------------------------------------------------------
    # Kural tabanlı (extractive) yol
    # ------------------------------------------------------------------

    def _extractive_summary(self, text: str, konu: str = "") -> str:
        """
        Skorlamalı extractive özetleme (LLM kullanılamadığında).

        Cümleler üç bileşenle puanlanır:
            - Pozisyon ağırlığı (giriş cümleleri + kapanış cümlesi öne çıkar)
            - Konu ve belge anahtar kelimeleriyle örtüşme
              (turkish_nlp.remove_stopwords/turkish_lower ile)
            - Uzunluk normalizasyonu (çok kısa/çok uzun cümleler cezalandırılır)
        En iyi 2-4 cümle orijinal sırasıyla birleştirilir.
        """
        body = self._extract_body(text)
        sentences = extract_sentences(body) or extract_sentences(text)
        # Tam cümle filtresi: ':'/';' ile biten öncü (eksiltili) yapılar ve
        # küçük harfle başlayan devam parçaları tek başına özet cümlesi
        # olamaz (Türkçede cümle büyük harfle ya da rakamla başlar).
        adaylar = [s for s in sentences if self._tam_cumle_mi(s)]
        if adaylar:
            sentences = adaylar
        if not sentences:
            kisa = re.sub(r"\s+", " ", text).strip()
            return kisa[:250] if kisa else "Metin çok kısa olduğu için özet oluşturulamadı."

        # Belge anahtar kelimeleri (durak kelimeler atıldıktan sonra en sık geçenler)
        belge_tokenleri = self._tokenize(body)
        frekans = Counter(belge_tokenleri)
        anahtar_kelimeler = {kelime for kelime, _ in frekans.most_common(12)}
        konu_tokenleri = set(self._tokenize(konu)) if konu else set()

        skorlar = []
        for i, sentence in enumerate(sentences):
            tl = turkish_lower(sentence)
            tokens = self._tokenize(sentence)
            kelime_sayisi = len(sentence.split())

            # Pozisyon ağırlığı: ilk cümleler ve kapanış cümlesi önemli
            if i == 0:
                pozisyon = 1.0
            elif i == 1:
                pozisyon = 0.85
            else:
                pozisyon = 0.6
            if i == len(sentences) - 1:
                pozisyon = max(pozisyon, 0.75)

            # Anahtar kelime örtüşmesi (cümle uzunluğuna normalize)
            ortusme = sum(1 for t in tokens if t in anahtar_kelimeler) / (len(tokens) + 1)

            # Konu örtüşmesi
            konu_ortusme = 0.0
            if konu_tokenleri:
                konu_ortusme = min(
                    sum(1 for t in tokens if t in konu_tokenleri), 2
                ) * 0.35

            # İpucu kalıpları (talep/karar cümleleri)
            ipucu = 0.4 if any(k in tl for k in _IPUCU_KALIPLARI) else 0.0

            # Uzunluk normalizasyonu: ideal 6-40 kelime
            uzunluk_carpani = 1.0 if 6 <= kelime_sayisi <= 40 else 0.6

            skor = (pozisyon + 2.0 * ortusme + konu_ortusme + ipucu) * uzunluk_carpani
            skorlar.append((skor, i, sentence))

        # En iyi 2-4 cümleyi seç, orijinal sırayla birleştir
        if len(sentences) <= 4:
            secim_sayisi = min(2, len(sentences)) if len(sentences) < 3 else 2
        elif len(sentences) <= 10:
            secim_sayisi = 3
        else:
            secim_sayisi = 4

        secilenler = sorted(
            sorted(skorlar, key=lambda x: x[0], reverse=True)[:secim_sayisi],
            key=lambda x: x[1],
        )

        parcalar = []
        for _, _, sentence in secilenler:
            temiz = re.sub(r"\s+", " ", sentence).strip()
            # Bağlanma bildiren son noktalama (';', ':', ',') özet
            # cümlesinde bırakılmaz; cümle nokta ile kapatılır.
            temiz = temiz.rstrip(" ;:,-")
            if temiz and temiz[-1] not in ".!?":
                temiz += "."
            if temiz:
                parcalar.append(temiz)
        return " ".join(parcalar)

    @staticmethod
    def _tam_cumle_mi(sentence: str) -> bool:
        """
        Cümlenin tek başına kullanılabilir TAM bir cümle olup olmadığını
        dilbilgisi temelli denetler:
        - ':' veya ';' ile biten yapı kendinden sonraki bloğa bağlanan
          öncü/eksiltili yapıdır; tek başına cümle sayılmaz.
        - Türkçede cümle büyük harfle veya rakamla başlar; küçük harfle
          başlayan parça bir önceki yapının devamıdır (yarım cümle).
        """
        s = sentence.strip()
        if not s:
            return False
        if s[-1] in ";:,":
            return False
        ilk = s.lstrip("(\"'“”‘’ ")[:1]
        if ilk.isalpha() and turkish_upper(ilk) != ilk:
            return False
        return True

    @classmethod
    def _tam_cumle_yapili(cls, govde: str) -> bool:
        """
        Madde işareti soyulmuş liste gövdesinin tek başına TAM bir cümle
        olup olmadığını denetler.

        TDK yazım kurallarına göre madde işaretinden sonra gelen ifade
        tam cümle ise büyük harfle başlar ve nokta ile biter ("1. Tüm
        birimler ... uygulayacaktır."). Bir giriş cümlesine bağlanan
        eksiltili maddeler ise küçük harfle başlar ve virgülle ya da
        noktalamasız biter ("Görevlendirilen personelin; 1) kimlik
        taşıması,"). Bu nedenle hem cümle sonu noktalaması (./!/?) hem
        de _tam_cumle_mi'nin büyük harf/rakam başlangıç şartı aranır.
        """
        g = govde.strip()
        return bool(g) and g[-1] in ".!?" and cls._tam_cumle_mi(g)

    @classmethod
    def _extract_body(cls, text: str) -> str:
        """
        Özet için gövde metnini ayıklar: antet, alan satırları (Sayı/Konu/İlgi…),
        büyük harfli başlık/hitap satırları, adres/iletişim satırları ve
        imza çizgileri atılır.

        İki geçişli çalışır: önce her satır tek başına sınıflandırılır,
        sonra bağlam kuralları uygulanır. Türkçe dilbilgisinde ':' veya ';'
        ile biten satır kendinden sonraki bloğa bağlanan öncü (eksiltili)
        yapıdır; bağlandığı blok (madde listesi vb.) atılmışsa öncü de tek
        başına cümle sayılmaz. Küçük harfle başlayan satır bir önceki
        yapının devamıdır; önceki satır atılmışsa devam parçası da yarım
        kaldığı için atılır. Böylece madde listesi ayıklanan metinlerde
        giriş ve kapanış parçaları birleşerek sahte cümle üretmez.
        """
        satirlar = []
        durumlar = []
        for line in text.split("\n"):
            islenmis = cls._satir_govde(line.strip())
            if islenmis == "":
                satirlar.append("")
                durumlar.append("bos")
            elif islenmis is None:
                satirlar.append(line.strip())
                durumlar.append("at")
            else:
                satirlar.append(islenmis)
                durumlar.append("tut")

        # 2. geçiş: bağlam kuralları (öncü satır / devam parçası)
        kept = []
        onceki_durum = ""  # son boş olmayan satırın (güncellenmiş) durumu
        for i, stripped in enumerate(satirlar):
            durum = durumlar[i]
            if durum == "bos":
                kept.append("")
                continue
            if durum == "tut":
                # Öncü satır: ':'/';' ile bitiyor ve bağlandığı sonraki
                # blok atılmışsa eksiltili parça satırdan çıkarılır;
                # satırda öncüden ÖNCE gelen tam cümleler korunur
                # ("… belirtilmiştir. Görevlendirilen personelin;" →
                # yalnızca son parça atılır). Cümlesiz kalan satır
                # bütünüyle atılır.
                if stripped[-1] in ":;":
                    sonraki = next(
                        (durumlar[j] for j in range(i + 1, len(satirlar))
                         if durumlar[j] != "bos"),
                        "",
                    )
                    if sonraki != "tut":
                        tamlar = [
                            p for p in extract_sentences(stripped)
                            if p.strip()[-1:] in (".", "!", "?")
                        ]
                        if tamlar:
                            stripped = " ".join(tamlar)
                        else:
                            durum = "at"
                # Devam parçası: küçük harfle başlıyor ve önceki yapı
                # atılmışsa yarım parça satır başından atılır; satırın
                # devamındaki tam cümleler korunur ("gerekmektedir.
                # Sürecin takibi …" → "Sürecin takibi …"). Tam cümle
                # kalmıyorsa satır bütünüyle atılır.
                if durum == "tut" and onceki_durum == "at":
                    ilk = next((c for c in stripped if c.isalpha()), "")
                    if ilk and turkish_upper(ilk) != ilk:
                        parcalar = extract_sentences(stripped)
                        while parcalar and not cls._tam_cumle_mi(parcalar[0]):
                            parcalar.pop(0)
                        if parcalar:
                            stripped = " ".join(parcalar)
                        else:
                            durum = "at"
            if durum == "tut":
                kept.append(stripped)
            onceki_durum = durum
        return "\n".join(kept)

    @classmethod
    def _satir_govde(cls, stripped: str) -> Optional[str]:
        """
        Satırın özet gövdesine girecek işlenmiş halini döndürür
        (1. geçiş sınıflandırması):
        - "" → boş satır (paragraf sınırı korunur),
        - None → gövdeye alınmaz,
        - str → gövdeye alınacak metin (madde işareti soyulmuş olabilir).
        """
        if not stripped:
            return ""
        # Hiç harf içermeyen satırlar (yalın sayı/referans: "2026/11")
        if not any(c.isalpha() for c in stripped):
            return None
        # ":" etrafını sıkıştırarak önek karşılaştırması yap
        compact = re.sub(r"\s*:\s*", ":", turkish_lower(stripped))
        if any(compact.startswith(onek) for onek in _META_ONEKLERI):
            return None
        # Hitap satırı: TDK'ya göre hitap sözleri ("Sayın Ali VELİ,")
        # ayrı satıra yazılır ve virgülle biter; cümle değildir → atılır.
        # Hitapla başlayıp TAM cümle içeren satırlar ("Sayın yetkili,
        # mahallemizde … yaşanmaktadır.") içerik taşıdığından korunur.
        if turkish_lower(stripped).startswith("sayın ") and (
            stripped[-1] not in ".!?" or len(stripped.split()) <= 4
        ):
            return None
        # Genel üstveri deseni: kısa 'Etiket :' satırları ("Saat :",
        # "Yer :", "Rapor No :", "Hazırlayan :", "İşin adı :" …)
        # cümle değil alan satırıdır; özet gövdesine alınmaz. Değeri
        # tam cümle olan satırlar ("Gündem 1: … kararlaştırılmıştır.")
        # içerik taşıdığından korunur.
        etiket = re.match(r"^([^:]{1,35}?)\s*:\s*(.*)$", stripped)
        if etiket and len(etiket.group(1).split()) <= 4:
            deger = etiket.group(2).strip()
            if len(deger.split()) <= 5 or deger[-1:] not in ".!?":
                return None
        # Liste maddeleri ("1) …", "a) …", "3. …"): işaret soyulduğunda
        # TAM CÜMLE olan maddeler (genelge talimatı, tutanak kararı gibi
        # "… edilecektir." / "… kararlaştırıldı." biçiminde çekimli
        # yüklemle biten) içerik cümlesidir ve işaretsiz olarak gövdeye
        # alınır; virgülle/eksiltili biten madde parçaları atılır.
        madde = re.match(r"^(?:\d{1,2}[.)\-]|[a-zçğıöşü]\))\s+(.*)$", stripped)
        if madde:
            govde = madde.group(1).strip()
            return govde if cls._tam_cumle_yapili(govde) else None
        # Kısa bölüm başlıkları: "Gündem:", "Görüşmeler ve Kararlar:" vb.
        if stripped.endswith(":") and len(stripped.split()) <= 4:
            return None
        # Tamamı büyük harf satırlar (başlık/hitap/antet)
        if stripped == turkish_upper(stripped):
            return None
        # Kurum/unvan antet satırları (kısa, kurum ekiyle biten) ve
        # yönelme hâlindeki hitap satırları ("… Müdürlüğüne",
        # "… Başkanlığına"): hitap, yazının yöneldiği makamı gösterir,
        # cümle değildir; gövde cümlelerine yapışmaması için atılır.
        tl_line = turkish_lower(stripped)
        tl_kisa = tl_line.rstrip(",;.")
        if len(stripped.split()) <= 7 and any(
            tl_kisa.endswith(ek) or tl_kisa.endswith(ek + "ne")
            or tl_kisa.endswith(ek + "na")
            for ek in _KURUM_EKLERI
        ):
            return None
        # Adres/iletişim satırları: iletişim etiketi, kapı numarası veya
        # birden çok adres birimi içeren ve cümle gibi bitmeyen satırlar
        # gönderici adres bloğudur; gövde cümlesi sayılmaz. Satır sonundaki
        # kısaltma noktası ("… Papatya Sk.") cümle sonu sayılmaz; buna
        # karşılık gerçek cümleler ("… No: 5 adresinde su kesintisi
        # yaşanmaktadır.") korunur.
        cumle_gibi = stripped[-1] in ".!?" and not re.search(
            r"\b(?:mah|sok|sk|cad|cd|bulv|blv|apt|no)\.$", tl_line
        )
        if not cumle_gibi and (
            _ILETISIM_DESENI.search(tl_line)
            or _KAPI_NO_DESENI.search(tl_line)
            or len(_ADRES_BIRIM_DESENI.findall(tl_line)) >= 2
        ):
            return None
        # İmza çizgisi içeren satırlar
        if re.search(r"_{3,}", stripped):
            return None
        # Tamamı parantez içindeki satır ("(İl Makamına sunulmak üzere)",
        # "(e-imzalıdır)"): TDK'ya göre parantez içi ibare cümlenin
        # kurucu ögesi değildir; tek başına satır oluşturan parantezli
        # not/ibare gövde cümlesi sayılmaz.
        if stripped.startswith("(") and stripped.endswith(")"):
            return None
        # İmza bloğu satırları (Resmî Yazışma Yönetmeliği: imza bloğu
        # ad-soyad, unvan ve imza/e-imza ibaresinden oluşur; cümle
        # değildir): e-imza ibaresi taşıyan ve cümle gibi bitmeyen satır,
        # BÜYÜK soyadılı ad-soyad satırı, kısa unvan/rol satırı atılır.
        if _EIMZA_DESENI.search(stripped) and stripped[-1] not in ".!?":
            return None
        if _IMZA_AD_DESENI.match(stripped) and stripped[-1] not in ".!?":
            return None
        if len(stripped.split()) <= 5 and stripped[-1] not in "!?" and (
            _IMZA_UNVAN_SONU.search(turkish_lower(stripped).rstrip("."))
        ):
            return None
        return stripped

    @staticmethod
    def _tokenize(text: str) -> list:
        """Durak kelimeleri atılmış, normalize edilmiş belirgin kelimeler döndürür."""
        temiz = remove_stopwords(turkish_lower(text))
        tokens = [t.strip(".,;:!?()\"'-–—") for t in temiz.split()]
        return [t for t in tokens if len(t) > 3]
