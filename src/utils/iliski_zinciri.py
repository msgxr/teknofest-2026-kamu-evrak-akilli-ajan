"""
Evrak İlişki Zinciri — yazışma zincirlerinin otomatik tespiti (saf fonksiyonlar).

Gerçek kamu evrak akışında yazışmalar tekil değildir; zincir oluşturur:
dilekçe → cevap yazısı → itiraz → üst yazı. Resmî yazışma usulünde bu
zincir "İlgi :" satırlarıyla kurulur (bir yazı, önceki yazının tarih ve
sayısına ilgi verir). Bu modül, uçtan uca pipeline'ın ürettiği sonuç
sözlüklerinden bu zinciri OTOMATİK kurar — 'gerçek iş akışıyla uyum'
(şartname m6.3/6.6) kanıtıdır: sistem evrakları yalnız tek tek değil,
aralarındaki süreç bağlamıyla birlikte görür.

Sinyal tasarımı (ilkesel — neden bu iki sinyal?):
    (a) GÜÇLÜ — "ilgi_referansi": Bir evrakın kendi numarası
        (bilgi_cikarim.evrak_sayisi / referans_numaralari), diğer evrakın
        "İlgi :" metinlerinde geçiyorsa bağ KESİNE yakındır; çünkü resmî
        yazışmada ilgi tutma, önceki evraka bilinçli ve biçimsel bir
        atıftır (Resmî Yazışma Usul ve Esasları). Yanlış pozitifleri
        önlemek için çok kısa numaralar ve yalın yıl değerleri ("2026")
        aday sayılmaz — bunlar hemen her evrakta geçer.
    (b) ORTA — "konu_benzerligi": İlgi satırı eksik/başarısız çıkarılmış
        olsa bile aynı sürecin evrakları konu satırını büyük ölçüde
        paylaşır ("... talebi" → "... talebiniz hakkında"). Tek başına
        konu benzerliği yeterli değildir (iki ayrı kurumda benzer konular
        olabilir); bu yüzden AYNI TARAF (muhatap/kurum kesişimi) şartı
        birlikte aranır. Benzerlik, bm25.tokenize üzerinden Jaccard ile
        ölçülür — durak kelimeler ve noktalama zaten elenir.

Zincir kurma:
    Sinyaller evraklar arasında KENARLAR üretir; zincirler bu kenarların
    bağlı bileşenleridir (connected components). Bileşenler ziyaret
    kümesiyle (BFS) gezilir — döngü güvenlidir (A→B→C→A gibi karşılıklı
    ilgiler sonsuz döngü yaratmaz). Boş liste ve tek evrak güvenlidir.

Bu modüldeki fonksiyonlar SAFTIR: dosya/ağ/arayüz yan etkisi yoktur;
eksik anahtarlara ve bozuk kayıtlara toleranslıdır (kokpit.py deseni).
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Set, Tuple

from src.utils.bm25 import tokenize
from src.utils.turkish_nlp import turkish_lower

logger = logging.getLogger("kamu_evrak_ajan.iliski_zinciri")

# --- Eşikler (ilkesel gerekçeleriyle) ---------------------------------------

# Konu benzerliği eşiği: Jaccard >= 0.5, iki konunun ayırt edici token'larının
# en az yarısının ortak olmasını ister. Daha düşük eşikler tek ortak kelimeyle
# ("talep", "hizmet") sahte bağ üretir; daha yüksek eşikler ek/çekim
# farklarını ("talebi" / "talebiniz") cezalandırıp gerçek bağları kaçırır.
KONU_JACCARD_ESIK = 0.5

# Taraf (muhatap/kurum) eşleşme eşiği: token kapsama oranı (küçük kümenin
# ne kadarı ortak). Tam dizgi eşitliği Türkçe hâl ekleri yüzünden kırılgandır
# ("BELEDİYE BAŞKANLIĞI" ↔ "BELEDİYE BAŞKANLIĞINA"); token kapsaması bu
# morfolojik farkı morfolojik çözümleme yapmadan tolere eder.
TARAF_KAPSAMA_ESIK = 0.6

# İlgi eşleşmesinde aday numara için asgari uzunluk: "8842" gibi kısa sayılar
# ve yalın yıllar rastlantısal olarak başka metinlerde geçebilir; resmî evrak
# sayıları (E-XXXXXXXX-XXX.XX-YYYY/NNN) belirgin biçimde daha uzundur.
MIN_NUMARA_UZUNLUGU = 5

# Yalın yıl deseni ("2026" gibi) — her evrakta geçer, aday numara olamaz.
_YALIN_YIL_DESENI = re.compile(r"^(19|20)\d{2}$")


# --- Yardımcılar --------------------------------------------------------------


def _guvenli_sozluk(kayit: Any) -> dict:
    """Kaydı sözlüğe indirger; sözlük değilse boş sözlük döndürür."""
    return kayit if isinstance(kayit, dict) else {}


def _evrak_adi(sonuc: dict, sira: int) -> str:
    """
    Sonuçtan görüntülenecek evrak adını üretir (input_file'ın taban adı).

    input_file bir yol ise taban ad (basename) alınır; yalın bir etiketse
    (process_text kaynağı gibi) olduğu gibi döner. Boşsa sıra numarasıyla
    anlaşılır bir yer tutucu üretilir — rapor hiçbir kayıtta boş ad göstermez.
    """
    ad = str(sonuc.get("input_file") or "").strip()
    if not ad:
        return f"evrak_{sira + 1}"
    return Path(ad).name


def _aday_numaralar(bilgi: dict) -> List[str]:
    """
    Evrakın kendi kimlik numarası adaylarını (normalize edilmiş) döndürür.

    evrak_sayisi + referans_numaralari birlikte taranır; çok kısa olan,
    rakam içermeyen veya yalın yıl olan değerler elenir (modül docstring'i:
    yanlış pozitif önlemi).
    """
    hamlar: List[str] = []
    sayi = bilgi.get("evrak_sayisi")
    if isinstance(sayi, str):
        hamlar.append(sayi)
    refler = bilgi.get("referans_numaralari")
    if isinstance(refler, (list, tuple)):
        hamlar.extend(str(r) for r in refler)

    adaylar: List[str] = []
    for ham in hamlar:
        numara = turkish_lower(ham).strip()
        if len(numara) < MIN_NUMARA_UZUNLUGU:
            continue
        if not any(ch.isdigit() for ch in numara):
            continue
        if _YALIN_YIL_DESENI.match(numara):
            continue
        if numara not in adaylar:
            adaylar.append(numara)
    return adaylar


def _ilgi_metni(bilgi: dict) -> str:
    """İlgi referans satırlarını tek bir normalize metinde birleştirir."""
    ilgiler = bilgi.get("ilgi_referanslari")
    if not isinstance(ilgiler, (list, tuple)):
        return ""
    return turkish_lower(" | ".join(str(i) for i in ilgiler))


def _taraf_kumeleri(bilgi: dict) -> List[FrozenSet[str]]:
    """
    Evrakın taraflarını (muhatap + kurum adları) token kümeleri olarak verir.

    Her taraf adı ayrı bir küme olur; böylece "aynı taraf" karşılaştırması
    ad bazında yapılır ve uzun kurum listeleri birbirine karışmaz.
    """
    adlar: List[str] = []
    muhatap = bilgi.get("muhatap")
    if isinstance(muhatap, str) and muhatap.strip():
        adlar.append(muhatap)
    kurumlar = bilgi.get("kurum_adlari")
    if isinstance(kurumlar, (list, tuple)):
        adlar.extend(str(k) for k in kurumlar if str(k).strip())

    kumeler: List[FrozenSet[str]] = []
    for ad in adlar:
        tokenlar = frozenset(tokenize(ad))
        if tokenlar:
            kumeler.append(tokenlar)
    return kumeler


def _ortak_taraf_var_mi(
    taraflar_a: List[FrozenSet[str]], taraflar_b: List[FrozenSet[str]]
) -> bool:
    """
    İki evrakın taraf listelerinde eşleşen bir ad çifti var mı?

    Eşleşme ölçüsü token KAPSAMA oranıdır (kesişim / küçük kümenin boyu):
    "doğuşehir belediye başkanlığına" ↔ "doğuşehir belediye başkanlığı"
    hâl eki farkına rağmen eşleşir; "akçova valiliği" ↔ "akçova belediye
    başkanlığı" yalnız il adını paylaştığı için eşleşmez.
    """
    for a in taraflar_a:
        for b in taraflar_b:
            kesisim = len(a & b)
            if kesisim == 0:
                continue
            if kesisim / min(len(a), len(b)) >= TARAF_KAPSAMA_ESIK:
                return True
    return False


def _konu_jaccard(tokenlar_a: Set[str], tokenlar_b: Set[str]) -> float:
    """İki konu token kümesinin Jaccard benzerliğini döndürür (0-1)."""
    if not tokenlar_a or not tokenlar_b:
        return 0.0
    birlesim = tokenlar_a | tokenlar_b
    if not birlesim:
        return 0.0
    return len(tokenlar_a & tokenlar_b) / len(birlesim)


def _bagli_bilesenler(dugum_sayisi: int, kenarlar: Dict[Tuple[int, int], dict]) -> List[List[int]]:
    """
    Kenar listesinden bağlı bileşenleri (connected components) çıkarır.

    Ziyaret kümesiyle BFS: her düğüm en fazla bir kez kuyruklanır, bu
    yüzden karşılıklı/dairesel bağlarda (A↔B↔C↔A) döngü güvenlidir.
    Yalnızca en az bir kenara değen düğümler bileşen üyesidir.
    """
    komsular: Dict[int, Set[int]] = {}
    for (i, j) in kenarlar:
        komsular.setdefault(i, set()).add(j)
        komsular.setdefault(j, set()).add(i)

    ziyaret: Set[int] = set()
    bilesenler: List[List[int]] = []
    for baslangic in range(dugum_sayisi):
        if baslangic in ziyaret or baslangic not in komsular:
            continue
        bilesen: List[int] = []
        kuyruk: List[int] = [baslangic]
        ziyaret.add(baslangic)
        while kuyruk:
            dugum = kuyruk.pop(0)
            bilesen.append(dugum)
            for komsu in sorted(komsular.get(dugum, ())):
                if komsu not in ziyaret:
                    ziyaret.add(komsu)
                    kuyruk.append(komsu)
        bilesenler.append(sorted(bilesen))
    return bilesenler


# --- Ana API ------------------------------------------------------------------


def zincir_kur(sonuclar: "list[dict]") -> dict:
    """
    Pipeline sonuç listesinden evraklar arası ilişki zincirlerini kurar.

    Args:
        sonuclar: EndToEndPipeline.process/process_batch çıktısı sözlükler.
            Eksik anahtarlı veya sözlük olmayan kayıtlar tolere edilir;
            boş liste ve tek elemanlı liste güvenlidir.

    Returns:
        {
            "zincirler": [
                {
                    "evraklar": [input_file taban adları, girdi sırasıyla],
                    "baglanti_turu": "ilgi_referansi" | "konu_benzerligi",
                    "aciklama": str,   # bağın nasıl kurulduğunun özeti
                },
                ...
            ],
            "bagimsiz": [hiçbir zincire girmeyen evrak adları],
        }

    Not (bağlantı türü önceliği): Bir bileşende hem güçlü (ilgi) hem orta
    (konu) kenar varsa zincirin türü "ilgi_referansi" raporlanır — zincirin
    varlık kanıtı en güçlü sinyaldir; açıklama tüm kenarları sayar.
    """
    if not isinstance(sonuclar, (list, tuple)):
        logger.warning(
            "zincir_kur: liste beklenirken %s alındı.", type(sonuclar).__name__
        )
        sonuclar = []

    # Evrak başına önden çıkarılan sinyaller (O(n) hazırlık, O(n^2) kıyas)
    adlar: List[str] = []
    numaralar: List[List[str]] = []
    ilgiler: List[str] = []
    konular: List[Set[str]] = []
    taraflar: List[List[FrozenSet[str]]] = []
    for sira, kayit in enumerate(sonuclar):
        sonuc = _guvenli_sozluk(kayit)
        bilgi = _guvenli_sozluk(sonuc.get("bilgi_cikarim"))
        adlar.append(_evrak_adi(sonuc, sira))
        numaralar.append(_aday_numaralar(bilgi))
        ilgiler.append(_ilgi_metni(bilgi))
        konular.append(set(tokenize(str(bilgi.get("konu") or ""))))
        taraflar.append(_taraf_kumeleri(bilgi))

    # Kenarları kur: her sırasız çift için önce güçlü, sonra orta sinyal
    kenarlar: Dict[Tuple[int, int], dict] = {}
    n = len(sonuclar)
    for i in range(n):
        for j in range(i + 1, n):
            kenar = None

            # (a) GÜÇLÜ: numara ↔ ilgi eşleşmesi (iki yönlü denenir)
            for kaynak, hedef in ((i, j), (j, i)):
                if kenar is not None:
                    break
                for numara in numaralar[kaynak]:
                    if numara and numara in ilgiler[hedef]:
                        kenar = {
                            "tur": "ilgi_referansi",
                            "aciklama": (
                                f"'{adlar[hedef]}' evrakının ilgi satırı, "
                                f"'{adlar[kaynak]}' evrakının sayısına "
                                f"({numara}) atıf yapıyor"
                            ),
                        }
                        break

            # (b) ORTA: konu benzerliği VE ortak taraf
            if kenar is None:
                jaccard = _konu_jaccard(konular[i], konular[j])
                if jaccard >= KONU_JACCARD_ESIK and _ortak_taraf_var_mi(
                    taraflar[i], taraflar[j]
                ):
                    kenar = {
                        "tur": "konu_benzerligi",
                        "aciklama": (
                            f"'{adlar[i]}' ile '{adlar[j]}' konuları benzer "
                            f"(Jaccard={jaccard:.2f}) ve taraflar ortak"
                        ),
                    }

            if kenar is not None:
                kenarlar[(i, j)] = kenar

    # Bağlı bileşenlerden zincirleri üret
    zincirler: List[dict] = []
    zincir_uyeleri: Set[int] = set()
    for bilesen in _bagli_bilesenler(n, kenarlar):
        zincir_uyeleri.update(bilesen)
        bilesen_kumesi = set(bilesen)
        bilesen_kenarlari = [
            kenar
            for (i, j), kenar in kenarlar.items()
            if i in bilesen_kumesi and j in bilesen_kumesi
        ]
        guclu_var = any(k["tur"] == "ilgi_referansi" for k in bilesen_kenarlari)
        zincirler.append(
            {
                "evraklar": [adlar[i] for i in bilesen],
                "baglanti_turu": "ilgi_referansi" if guclu_var else "konu_benzerligi",
                "aciklama": "; ".join(k["aciklama"] for k in bilesen_kenarlari),
            }
        )

    bagimsiz = [adlar[i] for i in range(n) if i not in zincir_uyeleri]

    logger.info(
        "İlişki zinciri kuruldu: %d evrak → %d zincir, %d bağımsız.",
        n,
        len(zincirler),
        len(bagimsiz),
    )
    return {"zincirler": zincirler, "bagimsiz": bagimsiz}
