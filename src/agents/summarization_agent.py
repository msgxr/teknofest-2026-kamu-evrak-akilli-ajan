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
from typing import TYPE_CHECKING

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
    "toplantı saati:", "toplantı yeri:", "katılımcılar:", "imzalar:", "sayın ",
)

# Antet satırlarını (kurum adı) gövdeden ayıklamak için kurum ekleri
_KURUM_EKLERI = (
    "bakanlığı", "müdürlüğü", "başkanlığı", "müşavirliği", "dairesi",
    "kurumu", "kurulu", "ajansı", "enstitüsü", "valiliği", "kaymakamlığı",
    "belediyesi", "üniversitesi", "rektörlüğü", "başkanı", "müdürü",
)

# Ana talep/karar bildiren ipucu kalıpları (cümle skoruna bonus)
_IPUCU_KALIPLARI = (
    "arz ederim", "rica ederim", "arz olunur", "kararlaştırıl", "talep",
    "gerekmektedir", "önem taşı", "tespit edil", "uygun bulun",
    "karar veril", "bilgilerinize", "sonuçlanmıştır",
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
            if temiz and temiz[-1] not in ".!?":
                temiz += "."
            parcalar.append(temiz)
        return " ".join(parcalar)

    @staticmethod
    def _extract_body(text: str) -> str:
        """
        Özet için gövde metnini ayıklar: antet, alan satırları (Sayı/Konu/İlgi…),
        büyük harfli başlık/hitap satırları ve imza çizgileri atılır.
        """
        kept = []
        for line in text.split("\n"):
            stripped = line.strip()
            if not stripped:
                kept.append("")
                continue
            # Hiç harf içermeyen satırlar (yalın sayı/referans: "2026/11")
            if not any(c.isalpha() for c in stripped):
                continue
            # ":" etrafını sıkıştırarak önek karşılaştırması yap
            compact = re.sub(r"\s*:\s*", ":", turkish_lower(stripped))
            if any(compact.startswith(onek) for onek in _META_ONEKLERI):
                continue
            # Genel üstveri deseni: kısa 'Etiket :' satırları ("Saat :",
            # "Yer :", "Rapor No :", "Hazırlayan :", "İşin adı :" …)
            # cümle değil alan satırıdır; özet gövdesine alınmaz. Değeri
            # tam cümle olan satırlar ("Gündem 1: … kararlaştırılmıştır.")
            # içerik taşıdığından korunur.
            etiket = re.match(r"^([^:]{1,35}?)\s*:\s*(.*)$", stripped)
            if etiket and len(etiket.group(1).split()) <= 4:
                deger = etiket.group(2).strip()
                if len(deger.split()) <= 5 or deger[-1:] not in ".!?":
                    continue
            # İlgi devam maddeleri: "b) 05/01/2026 tarihli …"
            if re.match(r"^[a-zçğıöşü]\)\s", stripped):
                continue
            # Numaralı liste maddeleri (cümle bütünlüğünü bozan fragmanlar)
            if re.match(r"^\d{1,2}[.)\-]\s", stripped):
                continue
            # Kısa bölüm başlıkları: "Gündem:", "Görüşmeler ve Kararlar:" vb.
            if stripped.endswith(":") and len(stripped.split()) <= 4:
                continue
            # Tamamı büyük harf satırlar (başlık/hitap/antet)
            if stripped == turkish_upper(stripped) and any(c.isalpha() for c in stripped):
                continue
            # Kurum/unvan antet satırları (kısa, kurum ekiyle biten)
            tl_line = turkish_lower(stripped).rstrip(",;.")
            if len(stripped.split()) <= 7 and any(tl_line.endswith(ek) for ek in _KURUM_EKLERI):
                continue
            # İmza çizgisi içeren satırlar
            if re.search(r"_{3,}", stripped):
                continue
            kept.append(stripped)
        return "\n".join(kept)

    @staticmethod
    def _tokenize(text: str) -> list:
        """Durak kelimeleri atılmış, normalize edilmiş belirgin kelimeler döndürür."""
        temiz = remove_stopwords(turkish_lower(text))
        tokens = [t.strip(".,;:!?()\"'-–—") for t in temiz.split()]
        return [t for t in tokens if len(t) > 3]
