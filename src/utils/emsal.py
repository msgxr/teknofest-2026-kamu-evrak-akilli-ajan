# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Emsal Evrak Arama — kurumsal hafıza (kayıt defteri üzerinde BM25).

Kamu personelinin yeni bir evrak karşısındaki ilk sorusu çoğu zaman
"benzer bir evrak daha önce geldi mi, nasıl işlem görmüş?" olur. Bu modül,
evrak kayıt defterindeki geçmiş işlemlerin metin özleri üzerinde BM25
dizini kurarak bu soruya yanıt verir: yeni evraka en çok benzeyen geçmiş
kayıtlar — türü, yönlendirildiği birim, üretilen yazı türü ve özetiyle —
listelenir. Kayıt defteri böylece salt denetim izi olmaktan çıkıp
KURUMSAL HAFIZAYA dönüşür: personel emsal işlemi görüp tutarlı cevap
verebilir (EBYS'lerdeki "benzer evrak" ihtiyacının yerel karşılığı).

Şartname Referansı:
    - "Gerçek iş akışına uygunluk" → kurumlarda emsal/önceki yazışma
      taraması, cevap yazısı hazırlamanın fiilî ilk adımıdır.
    - Görev 2 (yazı taslaklama): emsal kayıttaki yazı türü ve birim,
      yeni evrak için tutarlılık referansıdır.

Tasarım:
    - Dizin TEMBEL (lazy) kurulur ve kayıt sayısı değiştiğinde yeniden
      kurulur. Sürüm damgası olarak toplam kayıt sayısı yeterlidir çünkü
      kayıt defteri yalnızca ekleme yapılan (append-only) bir denetim
      izidir; silme/güncelleme API'si yoktur.
    - Benzerlik MUTLAK ölçektedir (0-1): legislation_agent'taki doygunluk
      yaklaşımı uygulanır — skor, sorgunun IDF kütlesinden türeyen
      doygunluk noktasına oranlanıp 1.0'a kırpılır. Göreli normalizasyon
      (skor / en_iyi_skor) en zayıf eşleşmeyi bile 1.0'a şişirirdi; "%97
      benzer emsal" diye sunulan alakasız bir kayıt personeli yanlış
      işleme yönlendirebilir (etik risk). Şişirme yoktur.
    - Küçük defter düzeltmeleri (mevzuat korpusundan farkı): kayıt defteri
      mevzuat korpusu gibi büyük ve çeşitli değildir; birkaç kayıtlık
      defterde standart IDF yozlaşır. Bu yüzden (a) IDF +1 yumuşatmalı
      biçimde yeniden hesaplanır — her kayıtta geçen sözcük bile tamamen
      bilgisiz sayılmaz; (b) sorgunun defter dağarcığında HİÇ görülmemiş
      sözcükleri doygunluk paydasına df=0 ağırlığıyla katılır — defterin
      hiç görmediği sözcüklerle dolu bir evrak, tek bir ortak sıradan
      sözcük yüzünden yüksek benzerlik alamaz (şişirme önlemi).
    - Kendini eleme: aynı dosya yeniden işlendiyse defterde sorgunun
      kendisi de kayıtlıdır; metin özü sorgu özüyle birebir aynı olan
      kayıtlar (ve istenirse haric_kaynak ile ad üzerinden dışlanan
      kaynak) sonuçlara girmez — "en benzer evrak: kendisi" sonucu
      kullanıcıya hiçbir şey söylemez.
    - Aynı kaynak adı sonuç listesinde en fazla bir kez görünür (en
      yüksek benzerlikli kaydıyla); aynı dosyanın tekrar işlenmesi
      listeyi kopyalarla doldurmaz.
"""

from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional

from src.utils.bm25 import BM25Okapi, tokenize
from src.utils.kayit_defteri import METIN_OZU_KARAKTER, KayitDefteri

logger = logging.getLogger("kamu_evrak_ajan.emsal")

# Mutlak benzerlik doygunluk katsayısı — legislation_agent.DOYGUNLUK_KATSAYISI
# ile aynı değer ve gerekçe: BM25'te ortalama uzunluktaki belgede tek geçiş
# (tf=1) yaklaşık idf katkısı verir; 1.5 katsayısı "tam benzerlik" tanımını
# sorgu sözcüklerinin belgede merkezî (tekrarlı) kullanımına bağlar. Ölçek
# korpus istatistiğine (IDF) dayanır, veri kümesine özel ezber içermez.
DOYGUNLUK_KATSAYISI = 1.5

# Bu mutlak eşiğin altındaki eşleşmeler gürültü sayılır ve listeye girmez:
# tek bir ortak sıradan sözcük bile sıfırdan büyük BM25 skoru üretir; böyle
# bir kaydı "emsal" diye sunmak yanıltıcı olur. Eşik bilinçli olarak düşük
# tutulmuştur (kısmî ama gerçek benzerlikler elenmesin); arayüz benzerlik
# yüzdesini ayrıca gösterdiği için son değerlendirme kullanıcıdadır.
ASGARI_BENZERLIK = 0.05

# Tek aramada döndürülecek azami emsal sayısı (limit üst sınırı): emsal
# listesi bir öneri panelidir, sayfalı arşiv taraması değil.
_AZAMI_LIMIT = 20


def _tur_adi(tur: str) -> str:
    """
    Evrak türü kodunu görüntü adına çevirir (örn. 'dilekce' → 'Dilekçe').

    Ad sözlüğü sınıflandırma agent'ında tanımlıdır; burada kopyalamak
    yerine tembel içe aktarma ile oradan okunur (tek doğruluk kaynağı).
    İçe aktarma başarısız olursa kod olduğu gibi döner — emsal arama
    görüntü adı yüzünden düşmez.
    """
    kod = str(tur or "")
    try:
        from src.agents.classification_agent import EVRAK_TURLERI

        bilgi = EVRAK_TURLERI.get(kod)
        if isinstance(bilgi, dict) and bilgi.get("ad"):
            return str(bilgi["ad"])
    except Exception:  # pragma: no cover - içe aktarma ortam sorunları
        pass
    return kod


class EmsalArama:
    """
    Kayıt defteri üzerinde emsal (benzer geçmiş evrak) araması.

    Kullanım:
        arama = EmsalArama(kayit_defteri)   # veya EmsalArama() → varsayılan defter
        emsaller = arama.ara(evrak_metni, limit=3)

    Dizin ilk aramada kurulur; kayıt sayısı değişmediği sürece sonraki
    aramalar aynı dizini kullanır (bkz. modül tasarım notu).
    """

    def __init__(self, kayit_defteri: Optional[KayitDefteri] = None) -> None:
        """
        Args:
            kayit_defteri: Aranacak KayitDefteri örneği (None → varsayılan
                data/processed/kayit_defteri.db üzerinde yeni örnek).
        """
        self.kayit_defteri = (
            kayit_defteri if kayit_defteri is not None else KayitDefteri()
        )
        self._bm25: Optional[BM25Okapi] = None
        self._kayitlar: List[dict] = []
        self._surum: int = -1  # dizinin kurulduğu andaki toplam kayıt sayısı
        self._oov_agirlik: float = 0.0  # dağarcık dışı sorgu sözcüğü ağırlığı

    # ------------------------------------------------------------------
    # Dizin
    # ------------------------------------------------------------------

    @staticmethod
    def _belge_metni(kayit: dict) -> str:
        """
        Kaydın dizine girecek belge metnini seçer.

        Öncelik metin özündedir (evrakın kendisi); şema geçişinden önce
        yazılmış eski kayıtlarda metin özü boş olduğundan özet alanına
        düşülür — eski kayıtlar da emsal olarak bulunabilir kalır.
        """
        metin_ozu = str(kayit.get("metin_ozu") or "").strip()
        if metin_ozu:
            return metin_ozu
        return str(kayit.get("ozet_ilk_200") or "").strip()

    def _dizini_tazele(self) -> None:
        """
        Dizini gerekiyorsa (ilk kullanım veya kayıt sayısı değiştiyse) kurar.

        Sürüm damgası toplam kayıt sayısıdır: defter yalnızca ekleme yapılan
        bir denetim izi olduğundan sayı değişmediyse içerik de değişmemiştir.

        Küçük korpus IDF düzeltmesi: BM25Okapi'nin standart IDF'i, birkaç
        kayıtlık ve birbirine benzer içerikli defterde yozlaşır (her kayıtta
        geçen sözcük için df=N → idf≈0; gerçek konu benzerliği görünmez
        olur). Dizin kurulduktan sonra IDF sözlüğü +1 yumuşatmalı değerlerle
        yeniden yazılır:

            idf(t) = ln(1 + (N + 1) / (df(t) + 0.5))

        Bu değer df=N'de bile pozitif kalır (≈ln 2) ve df küçüldükçe düzgün
        artar; df=0 (dağarcık dışı) değeri _oov_agirlik olarak saklanır ve
        doygunluk paydasında kullanılır (bkz. modül tasarım notu).
        """
        kayitlar = self.kayit_defteri.tum_kayitlar_emsal_icin()
        if self._bm25 is not None and len(kayitlar) == self._surum:
            return
        self._kayitlar = kayitlar
        self._surum = len(kayitlar)
        bm25 = BM25Okapi([tokenize(self._belge_metni(k)) for k in kayitlar])

        # Belge frekanslarını (df) belge başına terim frekanslarından türet
        df: Dict[str, int] = {}
        for freqs in bm25.doc_freqs:
            for token in freqs:
                df[token] = df.get(token, 0) + 1
        n = bm25.corpus_size
        bm25.idf = {
            token: math.log(1.0 + (n + 1) / (adet + 0.5))
            for token, adet in df.items()
        }
        self._oov_agirlik = math.log(1.0 + (n + 1) / 0.5) if n else 0.0
        self._bm25 = bm25
        logger.info(f"Emsal dizini kuruldu: {self._surum} kayıt.")

    # ------------------------------------------------------------------
    # Arama
    # ------------------------------------------------------------------

    def ara(self, metin: str, limit: int = 3, haric_kaynak: str = "") -> "list[dict]":
        """
        Verilen evrak metnine en çok benzeyen geçmiş kayıtları bulur.

        Args:
            metin: Yeni evrakın metni (sorgu).
            limit: Döndürülecek azami emsal sayısı (1..20 aralığına kırpılır).
            haric_kaynak: Bu kaynak adına sahip kayıtlar sonuçlardan
                dışlanır (evrak zaten defterdeyse kendisini bulmaması için;
                metin özü birebir eşleşen kayıtlar ayrıca her durumda elenir).

        Returns:
            Benzerliğe göre azalan sıralı sonuç listesi; her öğe:
            {kaynak, tur, tur_adi, birim, benzerlik (0-1 mutlak ölçek),
             ozet, zaman, yazi_turu}. Boş defter/sorgu → boş liste.
        """
        metin = str(metin or "")
        self._dizini_tazele()
        if not self._kayitlar or not metin.strip():
            return []

        sorgu_tokenlari = tokenize(metin)
        if not sorgu_tokenlari or self._bm25 is None:
            return []

        # Mutlak doygunluk noktası: sorgunun TÜM benzersiz sözcüklerinin IDF
        # kütlesi. Dağarcıkta olmayan sözcükler df=0 ağırlığıyla paydaya
        # katılır — kayıt, sorgunun yalnız küçük bir kısmını karşılıyorsa
        # benzerlik orantılı olarak düşük kalır (şişirme önlemi).
        toplam_idf = sum(
            self._bm25.idf.get(t, self._oov_agirlik) for t in set(sorgu_tokenlari)
        )
        if toplam_idf <= 0:
            return []
        doygunluk = DOYGUNLUK_KATSAYISI * toplam_idf

        try:
            guvenli_limit = max(1, min(_AZAMI_LIMIT, int(limit)))
        except (TypeError, ValueError):
            guvenli_limit = 3

        skorlar = self._bm25.get_scores(sorgu_tokenlari)
        sirali = sorted(range(len(skorlar)), key=lambda i: skorlar[i], reverse=True)

        # Kendini eleme karşılaştırması: kaydedilen öz ile aynı kırpma/kırpım
        sorgu_ozu = metin.strip()[:METIN_OZU_KARAKTER]
        haric = str(haric_kaynak or "").strip()

        sonuclar: "list[dict]" = []
        gorulen_kaynaklar: set = set()
        for i in sirali:
            if skorlar[i] <= 0:
                break
            # Skor azalan sıralı olduğundan benzerlik de azalır; eşiğin
            # altına inildiğinde kalan adaylar da eşiğin altındadır.
            benzerlik = min(1.0, skorlar[i] / doygunluk)
            if benzerlik < ASGARI_BENZERLIK:
                break

            kayit = self._kayitlar[i]
            kaynak = str(kayit.get("kaynak") or "")
            if haric and kaynak == haric:
                continue  # kendini eleme (kaynak adı üzerinden)
            if sorgu_ozu and str(kayit.get("metin_ozu") or "") == sorgu_ozu:
                continue  # kendini eleme (birebir aynı metin özü)
            if kaynak and kaynak in gorulen_kaynaklar:
                continue  # aynı dosyanın tekrar kaydı: en iyisi zaten listede

            sonuclar.append({
                "kaynak": kaynak,
                "tur": str(kayit.get("tur") or ""),
                "tur_adi": _tur_adi(kayit.get("tur")),
                "birim": str(kayit.get("birim") or ""),
                "benzerlik": round(benzerlik, 3),
                "ozet": str(kayit.get("ozet_ilk_200") or ""),
                "zaman": str(kayit.get("zaman") or ""),
                "yazi_turu": str(kayit.get("yazi_turu") or ""),
            })
            if kaynak:
                gorulen_kaynaklar.add(kaynak)
            if len(sonuclar) >= guvenli_limit:
                break

        logger.info(
            f"Emsal arama: {len(sonuclar)} sonuç "
            f"(defter: {self._surum} kayıt, limit: {guvenli_limit})."
        )
        return sonuclar


# Varsayılan defter üzerinde çalışan paylaşılan örnek: modül düzeyi
# emsal_ara çağrıları arasında dizin önbelleği korunur (lazy kuruluş).
_varsayilan_arama: Optional[EmsalArama] = None


def emsal_ara(
    metin: str,
    limit: int = 3,
    kayit_defteri: Optional[KayitDefteri] = None,
    haric_kaynak: str = "",
) -> "list[dict]":
    """
    Kolay kullanım fonksiyonu: kayıt defterinde emsal evrak arar.

    Args:
        metin: Yeni evrakın metni (sorgu).
        limit: Döndürülecek azami emsal sayısı.
        kayit_defteri: Aranacak defter (None → varsayılan
            data/processed/kayit_defteri.db; bu durumda dizin önbelleği
            çağrılar arasında paylaşılır).
        haric_kaynak: Sonuçlardan dışlanacak kaynak adı (kendini eleme).

    Returns:
        EmsalArama.ara ile aynı biçimde sonuç listesi; boş defterde boş liste.
    """
    global _varsayilan_arama
    if kayit_defteri is not None:
        return EmsalArama(kayit_defteri).ara(
            metin, limit=limit, haric_kaynak=haric_kaynak
        )
    if _varsayilan_arama is None:
        _varsayilan_arama = EmsalArama()
    return _varsayilan_arama.ara(metin, limit=limit, haric_kaynak=haric_kaynak)
