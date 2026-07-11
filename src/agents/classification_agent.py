"""
Sınıflandırma Agent — Evrak türü belirleme.

Evrak metnini analiz ederek türünü (dilekçe, üst yazı, cevap yazısı,
tutanak, rapor vb.) belirleyen agent.

Yöntem (üçlü hibrit: kural + istatistiksel öğrenme + opsiyonel LLM):
    1. Ağırlıklı kural tabanlı skorlama:
       - Ağırlıklı anahtar kelimeler (tür başına kalibre edilmiş katkılar)
       - Yapısal sinyaller (regex çapaları): "TUTANAK" başlığı, "GENELGE"
         başlığı, "İlgi :" satırı, "Sayı :"/"Konu :" alanları, T.C. antet,
         dilekçe hitap kalıpları, tutanak imza blokları vb.
       - Skorlar softmax benzeri normalize edilir; en yüksek olasılık
         güven skoru (0-1) olarak raporlanır.
    2. Hibrit ensemble: eğitilmiş istatistiksel model (saf Python
       Multinomial Naive Bayes, src/models/istatistiksel_siniflandirici)
       varsa kural ve ML olasılık dağılımları ağırlıklı ortalama ile
       birleştirilir (kural %60 / ML %40). Model dosyası yoksa saf kural
       tabanlı sonuç korunur (zarif bozulma).
    3. LLM eskalasyonu: nihai güven < 0.6 ve bir LLM backend'i
       kullanılabilir ise `generate_json` ile sınıflandırma doğrulanır.
       LLM hatasında ensemble/kural sonucu korunur (offline modda sistem
       LLM'siz tam çalışır).

Şartname Referansı (Görev 1):
    "Metni anlamlandırarak evrakın türünü belirleme"
"""

from __future__ import annotations

import logging
import math
import re
from typing import TYPE_CHECKING

from src.utils.turkish_nlp import turkish_lower

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.classification")

# Desteklenen evrak türleri (anahtarlar tüm modüllerle ortak sözlüktür).
# Skorlamada kullanılan anahtar kelimeler AGIRLIKLI_KELIMELER'de tanımlıdır;
# buradaki girdiler yalnızca ad/açıklama meta bilgisini taşır.
EVRAK_TURLERI = {
    "dilekce": {
        "ad": "Dilekçe",
        "aciklama": "Vatandaş veya kurumlardan gelen talep/şikayet belgesi",
    },
    "ust_yazi": {
        "ad": "Üst Yazı",
        "aciklama": "Bir evrakın üst makama sunulması için hazırlanan yazı",
    },
    "cevap_yazisi": {
        "ad": "Cevap Yazısı",
        "aciklama": "Gelen bir evrak veya yazıya yanıt olarak hazırlanan resmi yazı",
    },
    "bilgilendirme": {
        "ad": "Bilgilendirme Yazısı",
        "aciklama": "Bilgi aktarımı veya duyuru amaçlı yazı",
    },
    "tutanak": {
        "ad": "Tutanak",
        "aciklama": "Toplantı veya inceleme sonuçlarını belgeleyen yazı",
    },
    "rapor": {
        "ad": "Rapor",
        "aciklama": "İnceleme, araştırma veya değerlendirme sonuçlarını içeren belge",
    },
    "genelge": {
        "ad": "Genelge",
        "aciklama": "Tüm birimlere yönelik genel talimat veya bilgilendirme",
    },
    "onayli_belge": {
        "ad": "Onaylı Belge",
        "aciklama": "Resmi onay veya tasdik içeren belge",
    },
    "diger": {
        "ad": "Diğer",
        "aciklama": "Yukarıdaki kategorilere girmeyen evrak",
    },
}

# ----------------------------------------------------------------------
# Ağırlıklı anahtar kelimeler (turkish_lower uygulanmış metinde alt dizi
# eşleşmesi yapılır; ağırlıklar tür başına kalibre edilmiştir)
# ----------------------------------------------------------------------
AGIRLIKLI_KELIMELER = {
    "dilekce": {
        # "dilekçe" sözcüğü cevap yazılarında da geçer ("ilgi dilekçeniz");
        # ağırlığı tek başına belirleyici olmayacak şekilde tutulur.
        "dilekçe": 2.2,
        "arz ederim": 1.2,
        "rica ederim": 0.8,
        "talep": 1.2,
        "taleb": 1.2,
        # Birinci tekil şahıs talep dili: dilekçe vatandaşın kendi ağzından
        # yazılır ("talep ediyorum"), kurum yazıları edilgen/3. şahıs kullanır.
        "talep ediyorum": 1.5,
        "başvuru": 1.2,
        "istirham": 2.0,
        "şikayet": 1.5,
        "mağdur": 1.2,
        # Vatandaşın kendini tanıtma kalıpları (3071 sayılı Dilekçe Hakkı
        # Kanunu'na uygun dilekçelerde başvuran kendini ikametiyle tanıtır).
        "ikamet": 1.0,
        "vatandaş olarak": 1.5,
        "gereğinin yapılması": 1.8,
        "saygılarımla": 0.8,
    },
    "ust_yazi": {
        "üst yazı": 2.0,
        "ekte sunul": 2.5,
        "ekte gönderil": 2.0,
        "makamınıza": 2.0,
        "makamlarınıza": 2.0,
        "arz ederim": 0.8,
        "gereğini rica ederim": 1.5,
        "havale": 0.8,
    },
    "cevap_yazisi": {
        "ilgide kayıtlı": 3.0,
        "cevaben": 2.5,
        "yanıt olarak": 2.0,
        "cevap olarak": 2.0,
        "yazınıza istinaden": 2.5,
        "istinaden": 1.0,
        "ilgi yazı": 1.5,
        "sayılı yazınız": 1.8,
        # İkinci şahıs iyelikli belge atıfları: cevap yazısı, MUHATABIN
        # belgesine atıf yapar ("başvurunuz", "dilekçeniz", "yazınız").
        # Üst yazı ise kendi belgesine atıf yapar ("yazımız") — bu ek,
        # cevap yazısını üst yazıdan ayıran temel resmî yazışma sinyalidir.
        "başvurunuz": 1.8,
        "dilekçeniz": 2.0,
        "yazınız": 1.8,
        "talebiniz": 1.5,
        "müracaatınız": 1.8,
        "itirazınız": 1.8,
        # Birinci çoğul iyelikli görüş/değerlendirme bildirme: cevap yazısı
        # sorulan hususa kurumun görüşünü/cevabını iletir.
        "görüşümüz": 1.5,
        "değerlendirmemiz": 1.0,
        "cevabımız": 1.8,
        # Başvurunun incelenip sonuçlandırıldığını bildiren kalıplar.
        "yapılan inceleme sonucunda": 1.0,
        "yapılan değerlendirme sonucunda": 1.0,
        # Muhatabın kuruma SUNDUĞU talebe atıf: İlgi bloğu olmayan cevap
        # yazılarında gelen başvuruya atıf bu kalıplarla yapılır
        # ("Başkanlığımıza sunduğunuz talep ... görüşülmüştür").
        "sunduğunuz talep": 2.0,
        "sunduğunuz başvuru": 2.0,
        "iletmiş olduğunuz": 1.5,
    },
    "bilgilendirme": {
        "bilgilerinize sunulur": 2.5,
        "bilgilerinize arz": 1.5,
        "bilgilerinize": 1.0,
        # "Bilgilerinizi ... rica ederim" kapanışı (bilgi verme amaçlı yazı).
        "bilgilerinizi": 1.0,
        "duyurulur": 2.5,
        "duyuru": 1.5,
        # "duyurulması/duyurulacaktır" çekimleri: içeriğin ilgililere
        # duyurulması amacı bilgilendirme yazısının tanımlayıcı işlevidir.
        "duyurul": 1.0,
        "bilgilendirme": 2.0,
        "bilginize": 1.5,
        "hatırlatma": 1.0,
    },
    "tutanak": {
        "tutanak": 2.5,
        "tutanağı": 2.0,
        "iş bu tutanak": 3.0,
        "işbu tutanak": 3.0,
        "toplantı": 1.0,
        "katılımcılar": 1.5,
        "gündem": 1.2,
        "hazır bulunan": 1.5,
        "imza altına alın": 1.8,
    },
    "rapor": {
        "rapor": 2.5,
        "inceleme": 1.0,
        "değerlendirme": 0.8,
        "bulgular": 1.5,
        "tespitler": 1.2,
        "sonuç ve öneriler": 2.0,
        "yönetici özeti": 2.0,
        "analiz": 0.8,
        # Raporun kendine atıf yapan giriş kalıbı ("Bu rapor, ... amacıyla
        # hazırlanmıştır") — rapor metinlerinin standart açılışıdır.
        "bu rapor": 1.5,
        "işbu rapor": 2.0,
    },
    "genelge": {
        "genelge": 3.0,
        "tamim": 2.5,
        "genel talimat": 2.0,
        "tüm birimlere": 1.5,
        "talimat": 1.0,
        "uyulması": 1.0,
        "yürürlüğe": 1.0,
    },
    "onayli_belge": {
        "uygun görülmüştür": 2.5,
        "onaylanmıştır": 2.5,
        "tasdik": 2.0,
        "makam oluru": 2.5,
        "onay": 1.2,
        # Makam oluru kapanış kalıbı: teklif "olurlarınıza arz" edilir
        # (Resmî Yazışma Usulleri Yönetmeliği'ndeki olur yazısı biçimi).
        "olurlarınıza": 3.0,
        # Ara kademe onay şerhi: olur belgelerinde amirin katıldığını
        # gösteren standart ifade.
        "uygun görüşle arz": 2.5,
        # Olur/onay bloğundaki imza rolü etiketi.
        "onaylayan": 1.5,
        # "İhale onay belgesi" gibi başlıklar: belgenin kendisi onay belgesidir.
        "onay belgesi": 2.5,
        "onayına sunul": 1.2,
    },
    "diger": {},
}

# ----------------------------------------------------------------------
# Yapısal sinyaller: (derlenmiş regex, {tur: ağırlık}, etiket)
# Regex'ler orijinal metin üzerinde MULTILINE modda çalışır.
# ----------------------------------------------------------------------
# Dilekçe hitap ekleri: vatandaş dilekçeleri makam ADINA değil kurum/birime
# yönelme haliyle hitap eder ("… MÜDÜRLÜĞÜNE"). "MAKAMINA" hitabı kurum içi
# sunuş/olur yazılarına özgü olduğundan bu listeden çıkarılmıştır (aşağıda
# ayrı bir yapısal sinyal olarak ele alınır).
_HITAP_EKLERI = (
    "MÜDÜRLÜĞÜNE|MÜDÜRLÜĞÜNÜZE|BAŞKANLIĞINA|BAŞKANLIĞINIZA|"
    "VALİLİĞİNE|KAYMAKAMLIĞINA|REKTÖRLÜĞÜNE|DEKANLIĞINA|BAKANLIĞINA|"
    "Müdürlüğüne|Müdürlüğünüze|Başkanlığına|Başkanlığınıza|"
    "Valiliğine|Kaymakamlığına|Rektörlüğüne|Dekanlığına|Bakanlığına"
)

_YAPISAL_SINYALLER = [
    (
        re.compile(r"^\s*(?:TOPLANTI\s+|İNCELEME\s+|TESPİT\s+)?TUTANA(?:ĞI(?:DIR)?|KTIR|K)\s*$", re.MULTILINE),
        {"tutanak": 3.0},
        "TUTANAK başlığı",
    ),
    (
        re.compile(r"^\s*GENELGE(?:\s*[(\[]?\s*(?:NO|SAYI|\d).{0,20})?\s*$", re.MULTILINE),
        {"genelge": 3.0},
        "GENELGE başlığı",
    ),
    (
        # Rapor başlıkları çoğunlukla "… DEĞERLENDİRME RAPORU" gibi uzun
        # niteleyiciler taşır; önek payı 60 karaktere çıkarıldı.
        re.compile(r"^\s*(?:.{0,60}\s)?RAPOR(?:U|UDUR)?\s*$", re.MULTILINE),
        {"rapor": 2.5},
        "RAPOR başlığı",
    ),
    (
        # Rapor üst bilgi alanları: kurumsal rapor formatında belge,
        # "Rapor Tarihi/No" ve "Hazırlayan" alanlarıyla tanımlanır.
        re.compile(r"^\s*(?:Rapor\s+(?:Tarihi|No)|Haz[ıi]rlayan[ıi]?)\s*:", re.MULTILINE),
        {"rapor": 1.5},
        "rapor üst bilgi alanları (Rapor Tarihi/No, Hazırlayan)",
    ),
    (
        # Rapor gövdesinin standart BÜYÜK HARFLİ bölüm başlıkları
        # (ÖZET / BULGULAR / SONUÇ [VE ÖNERİLER] / DEĞERLENDİRME / GİRİŞ).
        re.compile(
            r"^\s*(?:ÖZET|GİRİŞ|BULGULAR|TESPİTLER|DEĞERLENDİRME|ÖNERİLER|"
            r"SONUÇ(?:\s+VE\s+ÖNERİLER)?)\s*$",
            re.MULTILINE,
        ),
        {"rapor": 1.5},
        "rapor bölüm başlığı (ÖZET/BULGULAR/SONUÇ…)",
    ),
    (
        re.compile(r"^\s*DUYURU\s*$", re.MULTILINE),
        {"bilgilendirme": 2.5},
        "DUYURU başlığı",
    ),
    (
        # Olur (onay) bloğu: makam olurlarında "OLUR" ibaresi genellikle
        # harf araları açılarak ("O L U R") ayrı satırda yazılır.
        re.compile(r"^\s*O\s*L\s*U\s*R\s*$", re.MULTILINE),
        {"onayli_belge": 3.5},
        "OLUR (olur bloğu) bölümü",
    ),
    (
        # "… MAKAMINA" hitabı: bir hususun üst makamın onayına/bilgisine
        # sunulduğu kurum içi yazıların (özellikle olur yazılarının) hitabıdır.
        re.compile(r"^\s*[^\n]{0,50}MAKAMINA\s*$", re.MULTILINE),
        {"onayli_belge": 1.2, "ust_yazi": 0.6, "dilekce": 0.5},
        "'… MAKAMINA' hitabı",
    ),
    (
        # Genel dağıtımlı hitap ("TÜM BİRİMLERE/MÜDÜRLÜKLERE/PERSONELE"):
        # kuruluş genelini muhatap alan duyuru/bilgilendirme yazısı işareti.
        re.compile(r"^\s*TÜM\s+[A-ZÇĞİÖŞÜ]+E\s*$", re.MULTILINE),
        {"bilgilendirme": 2.0, "genelge": 0.5},
        "'TÜM …E' genel hitap satırı",
    ),
    (
        # "İlgi :" bloğu belge zinciri kurar: yazışma trafiğinin (üst yazı /
        # cevap yazısı) ayırt edici alanıdır; duyuru niteliğindeki
        # bilgilendirme yazılarında bulunmaz.
        re.compile(r"^\s*[İI]lgi\s*:", re.MULTILINE),
        {"ust_yazi": 2.0, "cevap_yazisi": 1.2},
        "'İlgi :' satırı",
    ),
    (
        # İlgi satırında muhatabın belgesine ikinci şahıs iyelikli atıf
        # ("İlgi : … başvurunuz/dilekçeniz/yazınız"): gelen belgeye cevap
        # verildiğinin en güçlü yapısal kanıtıdır.
        re.compile(
            r"^\s*[İI]lgi\s*:[^\n]*(?:başvurunuz|dilekçeniz|yazınız|"
            r"talebiniz|müracaatınız|itirazınız)",
            re.MULTILINE,
        ),
        {"cevap_yazisi": 3.0},
        "İlgi satırında muhatap belgesine atıf (…nız/…niz)",
    ),
    (
        # Talep üzerine görüş bildiren yazı: "istenen/sorulan … görüş"
        # kalıbı, bir soruya karşılık verildiğini (cevap yazısı) gösterir.
        re.compile(r"(?:istenen|istenilen|sorulan|talep edilen)\s+[^\n]{0,40}görüş"),
        {"cevap_yazisi": 2.5},
        "istenen/sorulan görüşe karşılık verme kalıbı",
    ),
    (
        # Konu satırında "cevap/cevabı/yanıt" ifadesi: belge, konusunu
        # bizzat bir talebe/başvuruya CEVAP olarak tanımlıyor demektir
        # ("Konu : ... talebinize cevap"). İlgi bloğu olmayan cevap
        # yazılarının en güçlü yapısal işaretidir.
        re.compile(r"^\s*Konu\s*:[^\n]*(?:cevap|cevabı|yanıt)", re.MULTILINE | re.IGNORECASE),
        {"cevap_yazisi": 3.0},
        "Konu satırında 'cevap/yanıt' ifadesi",
    ),
    (
        # "Sayı :" kurum kayıt numarasıdır; vatandaş dilekçesi kurumsal
        # antet ve sayı taşımaz — bu alanın varlığı dilekçe ihtimalini düşürür.
        re.compile(r"^\s*Say[ıi]\s*:", re.MULTILINE),
        {
            "ust_yazi": 0.8,
            "cevap_yazisi": 0.8,
            # Genelge "GENELGE" başlığıyla tanımlanır; genel antet alanları
            # genelge lehine düşük tutulur ki her antetli yazı genelgeye kaymasın.
            "genelge": 0.5,
            "bilgilendirme": 0.6,
            "dilekce": -1.8,
        },
        "'Sayı :' alanı",
    ),
    (
        re.compile(r"^\s*Konu\s*:", re.MULTILINE),
        {"ust_yazi": 0.6, "cevap_yazisi": 0.6, "genelge": 0.6, "bilgilendirme": 0.6},
        "'Konu :' alanı",
    ),
    (
        re.compile(r"^\s*T\.\s?C\.?\s*$", re.MULTILINE),
        {"ust_yazi": 0.5, "cevap_yazisi": 0.5, "genelge": 0.4, "bilgilendirme": 0.4},
        "T.C. antet yapısı",
    ),
    (
        re.compile(r"^\s*(?:Sayın\s+|SAYIN\s+)?[^\n]{0,60}(?:" + _HITAP_EKLERI + r")\s*[,;]?\s*$", re.MULTILINE),
        {"dilekce": 2.0},
        "dilekçe hitap kalıbı (…Müdürlüğüne/Başkanlığına)",
    ),
    (
        re.compile(r"^\s*Sayın\s+[^\n]{2,60},\s*$", re.MULTILINE),
        {"dilekce": 1.5},
        "'Sayın …,' hitap satırı",
    ),
    (
        re.compile(r"^\s*Dağıtım\s*:?", re.MULTILINE),
        {"ust_yazi": 0.8, "genelge": 0.6, "bilgilendirme": 0.6},
        "'Dağıtım' bölümü",
    ),
    (
        re.compile(r"^\s*Gereği\s*:", re.MULTILINE),
        {"ust_yazi": 0.6, "genelge": 0.6},
        "'Gereği :' satırı",
    ),
    (
        re.compile(r"^\s*Ek(?:ler)?\s*:", re.MULTILINE),
        {"ust_yazi": 1.2},
        "'Ek :' bölümü",
    ),
    (
        re.compile(r"Toplantı\s+(?:[Tt]arihi|[Ss]aati|[Yy]eri)", re.MULTILINE),
        {"tutanak": 1.0},
        "toplantı tarih/saat/yer alanları",
    ),
    (
        re.compile(r"^\s*(?:İmzalar|İMZALAR)\s*:?\s*$", re.MULTILINE),
        {"tutanak": 1.5},
        "'İmzalar' bölümü",
    ),
]

# ----------------------------------------------------------------------
# Dilekçe kimlik/iletişim bloğu alanları: 3071 sayılı Dilekçe Hakkı Kanunu
# uyarınca dilekçede başvuranın adı-soyadı, imzası ve adresi bulunur.
# Belge sonunda bu etiketli alanlardan EN AZ İKİSİNİN birlikte bulunması,
# metnin bir vatandaş dilekçesi olduğuna dair güçlü yapısal kanıttır
# (kurum yazılarında imza bloğu unvan/e-imza şerhi ile kurulur, bu etiketli
# kişisel alanlar yer almaz).
# ----------------------------------------------------------------------
_KIMLIK_ALANLARI = [
    re.compile(r"^\s*Ad[ıi]?\s+Soyad[ıi]?\s*:", re.MULTILINE),
    re.compile(r"^\s*T\.?\s?C\.?\s*Kimlik\s*No[^\n:]*:", re.MULTILINE),
    re.compile(r"^\s*Adres[i]?\s*:", re.MULTILINE),
    re.compile(r"^\s*Telefon[u]?\s*:", re.MULTILINE),
    re.compile(r"^\s*[İI]mza\s*:", re.MULTILINE),
]

# Eskalasyon eşiği ve softmax sıcaklığı (kalibrasyon parametreleri)
_ESKALASYON_ESIGI = 0.6
_SOFTMAX_SICAKLIK = 2.0

# ----------------------------------------------------------------------
# Hibrit ensemble ağırlıkları (kural + istatistiksel model birleşimi)
#
# Nihai olasılık, iki yöntemin olasılık dağılımlarının ağırlıklı
# aritmetik ortalamasıdır (mixture). Gerekçe:
# - Kural katmanı Resmî Yazışma Usulleri Yönetmeliği'ne dayalı alan
#   bilgisi kodlar (yapısal çapalar: başlık, İlgi/Sayı blokları, hitap
#   kalıpları) ve görülmemiş belgelerde de geçerli genel kurallardır;
#   bu yüzden çoğunluk ağırlığı (0.6) taşır.
# - İstatistiksel model küçük bir korpusta eğitilmiştir (yüksek
#   varyans); kelime/karakter-n-gram dağılımlarından kuralların
#   kodlamadığı sözcüksel örüntüleri öğrenir ve azınlık ağırlığı (0.4)
#   ile kuralların kararsız kaldığı durumlarda dengeyi değiştirir.
# - Aritmetik ortalama, aşırı güvenli tek bir bileşenin (ör. 1.0
#   olasılık veren model) kararı tek başına belirlemesini sınırlar:
#   hiçbir bileşen nihai skora kendi ağırlığından fazla katkı veremez.
# ----------------------------------------------------------------------
_ENSEMBLE_KURAL_AGIRLIGI = 0.6
_ENSEMBLE_ML_AGIRLIGI = 0.4


class ClassificationAgent:
    """
    Evrak sınıflandırma agent'ı.

    Gelen evrakın türünü belirler. Üçlü hibrit mimari:
    1. Kural tabanlı (ağırlıklı anahtar kelime + yapısal sinyal skorlaması)
    2. İstatistiksel model (Multinomial NB) ile ensemble birleşimi
       (model dosyası varsa; yoksa saf kural tabanlı sonuç korunur)
    3. LLM eskalasyonu (nihai güven < 0.6 ise LLM ile doğrulama)
    """

    def __init__(self, method: str = "llm") -> None:
        """
        Sınıflandırma agent'ını başlatır.

        Args:
            method: Sınıflandırma yöntemi ('rule_based' veya 'llm').
                'llm' (varsayılan) modunda kural tabanlı skorlama yapılır,
                eğitilmiş istatistiksel model varsa hibrit ensemble kurulur
                ve LLM yalnızca düşük güvende eskalasyon olarak devreye
                girer. 'rule_based' modu karşılaştırma/test amaçlı SAF
                kural tabanlı çalışır (ML ve LLM devre dışı).
        """
        self.method = method
        logger.info(f"Sınıflandırma Agent başlatıldı (yöntem: {method})")

    def run(self, state: "AgentState") -> "AgentState":
        """
        Evrak metnini sınıflandırır.

        Args:
            state: Mevcut agent durumu

        Returns:
            Güncellenen agent durumu
        """
        text = state.raw_text

        if not text.strip():
            state.classification = {
                "tur": "bilinmiyor",
                "tur_adi": "Bilinmiyor",
                "guven": 0.0,
                "aciklama": "Metin çıkarılamadı",
                "yontem": "kural_tabanli",
            }
            return state

        result = self._classify_rule_based(text)
        result["yontem"] = "kural_tabanli"

        # HİBRİT ENSEMBLE: eğitilmiş istatistiksel model varsa kural ve
        # ML olasılıkları birleştirilir ('rule_based' modu saf kural kalır)
        if self.method != "rule_based":
            result = self._ensemble_ile_birlestir(text, result)

        # ESKALASYON: nihai güven düşükse ve LLM erişilebilirse
        # (eşik ve davranış korunur; modelsiz kurulumda nihai güven ==
        # kural tabanlı güven olduğundan mevcut davranışla birebir aynıdır)
        if self.method != "rule_based" and result["guven"] < _ESKALASYON_ESIGI:
            try:
                from src.models.llm_wrapper import get_default_llm

                llm = get_default_llm()
                if llm.is_available():
                    logger.info(
                        f"Nihai güven düşük ({result['guven']:.2f} < "
                        f"{_ESKALASYON_ESIGI}); LLM eskalasyonu deneniyor."
                    )
                    llm_result = self._classify_with_llm(text, result)
                    llm_result["yontem"] = "llm_eskalasyon"
                    llm_result["tum_skorlar"] = result.get("tum_skorlar", {})
                    llm_result["ham_skorlar"] = result.get("ham_skorlar", {})
                    # Ensemble ara sonuç alanları raporda korunur
                    for alan in ("kural_guven", "kural_tur", "ml_guven", "ml_tur"):
                        if alan in result:
                            llm_result[alan] = result[alan]
                    result = llm_result
            except Exception as exc:  # LLM hatasında kural sonucu korunur
                logger.warning(f"LLM eskalasyonu başarısız, kural tabanlı sonuç korunuyor: {exc}")

        state.classification = result
        logger.info(
            f"Sınıflandırma sonucu: {result['tur_adi']} "
            f"(güven: {result['guven']:.2f}, yöntem: {result['yontem']})"
        )
        return state

    # ------------------------------------------------------------------
    # Kural tabanlı skorlama
    # ------------------------------------------------------------------

    def _classify_rule_based(self, text: str) -> dict:
        """
        Ağırlıklı kural tabanlı sınıflandırma.

        Anahtar kelime ağırlıkları ve yapısal regex sinyalleri toplanır,
        skorlar softmax benzeri normalize edilir ve en yüksek olasılık
        güven skoru olarak raporlanır.

        Args:
            text: Evrak metni

        Returns:
            Sınıflandırma sonucu sözlüğü
        """
        text_lower = turkish_lower(text)
        raw_scores: dict = {tur: 0.0 for tur in EVRAK_TURLERI}
        eslesmeler: dict = {tur: [] for tur in EVRAK_TURLERI}

        # 1) Ağırlıklı anahtar kelimeler
        for tur, kelimeler in AGIRLIKLI_KELIMELER.items():
            for kelime, agirlik in kelimeler.items():
                if kelime in text_lower:
                    raw_scores[tur] += agirlik
                    eslesmeler[tur].append(f"anahtar kelime '{kelime}' (+{agirlik:.1f})")

        # 2) Yapısal sinyaller (regex çapaları; ağırlık negatif olabilir —
        #    ör. "Sayı :" antetinin dilekçe skorunu düşürmesi)
        for pattern, katkılar, etiket in _YAPISAL_SINYALLER:
            if pattern.search(text):
                for tur, agirlik in katkılar.items():
                    raw_scores[tur] += agirlik
                    eslesmeler[tur].append(f"yapısal: {etiket} ({agirlik:+.1f})")

        # 3) Tutanak imza blokları (birden fazla altçizgi dizisi)
        imza_cizgileri = re.findall(r"_{4,}", text)
        if len(imza_cizgileri) >= 2:
            raw_scores["tutanak"] += 2.0
            eslesmeler["tutanak"].append(
                f"yapısal: {len(imza_cizgileri)} adet imza çizgisi bloğu (+2.0)"
            )

        # 4) Dilekçe kimlik/iletişim bloğu: etiketli kişisel alanlardan
        #    (Ad Soyad / T.C. Kimlik No / Adres / Telefon / İmza) en az iki
        #    FARKLI alanın bulunması vatandaş dilekçesi göstergesidir.
        #    Tek alan (ör. yalnız "İmza :") kurum belgelerinde de görülebilir,
        #    bu yüzden puanlanmaz.
        kimlik_alan_sayisi = sum(1 for p in _KIMLIK_ALANLARI if p.search(text))
        if kimlik_alan_sayisi >= 2:
            bonus = min(0.9 * kimlik_alan_sayisi, 2.7)
            raw_scores["dilekce"] += bonus
            eslesmeler["dilekce"].append(
                f"yapısal: {kimlik_alan_sayisi} adet kişisel kimlik/iletişim alanı (+{bonus:.1f})"
            )

        # 5) Softmax benzeri normalizasyon
        probs = self._softmax(raw_scores)

        if max(raw_scores.values()) <= 0:
            best_type = "diger"
            confidence = 0.1
            gerekce = "Belirleyici anahtar kelime veya yapısal sinyal bulunamadı."
        else:
            best_type = max(raw_scores, key=lambda t: raw_scores[t])
            confidence = probs[best_type]
            gerekce = "; ".join(eslesmeler[best_type][:6])

        tur_info = EVRAK_TURLERI[best_type]
        return {
            "tur": best_type,
            "tur_adi": tur_info["ad"],
            "guven": round(min(max(confidence, 0.0), 1.0), 3),
            "aciklama": tur_info["aciklama"],
            "gerekce": gerekce,
            "tum_skorlar": {t: round(p, 3) for t, p in probs.items()},
            "ham_skorlar": {t: round(s, 2) for t, s in raw_scores.items()},
        }

    @staticmethod
    def _softmax(scores: dict) -> dict:
        """Ham skorları softmax benzeri olasılık dağılımına çevirir."""
        exps = {t: math.exp(s / _SOFTMAX_SICAKLIK) for t, s in scores.items()}
        total = sum(exps.values()) or 1.0
        return {t: v / total for t, v in exps.items()}

    # ------------------------------------------------------------------
    # Hibrit ensemble (kural + istatistiksel model)
    # ------------------------------------------------------------------

    def _ensemble_ile_birlestir(self, text: str, kural_sonuc: dict) -> dict:
        """
        Kural tabanlı olasılıkları istatistiksel model ile birleştirir.

        Nihai dağılım: 0.6 x kural + 0.4 x ML (ağırlık gerekçesi modül
        başındaki _ENSEMBLE_* sabitlerinde). Model dosyası yoksa veya
        tahmin başarısız olursa kural tabanlı sonuç değişmeden döner
        (yontem 'kural_tabanli' kalır — zarif bozulma).

        Args:
            text: Evrak metni.
            kural_sonuc: _classify_rule_based çıktısı.

        Returns:
            'yontem': 'hibrit_ensemble' + kural_guven/ml_guven ara sonuç
            alanlarını içeren sınıflandırma sözlüğü (veya kural sonucu).
        """
        from src.models.istatistiksel_siniflandirici import (
            IstatistikselSiniflandirici,
            tahmin,
        )

        model = IstatistikselSiniflandirici.yukle()
        if model is None:
            logger.debug("İstatistiksel model bulunamadı; saf kural tabanlı mod.")
            return kural_sonuc

        try:
            ml_tur, ml_olasiliklar = tahmin(model, text)
        except Exception as exc:  # bozuk model dosyası vb.
            logger.warning(f"ML tahmini başarısız, kural tabanlı sonuç korunuyor: {exc}")
            return kural_sonuc

        kural_olasiliklar = kural_sonuc.get("tum_skorlar", {})
        birlesik = {
            tur: (
                _ENSEMBLE_KURAL_AGIRLIGI * kural_olasiliklar.get(tur, 0.0)
                + _ENSEMBLE_ML_AGIRLIGI * ml_olasiliklar.get(tur, 0.0)
            )
            for tur in EVRAK_TURLERI
        }

        best_type = max(birlesik, key=lambda t: birlesik[t])
        confidence = birlesik[best_type]
        ml_guven = max(ml_olasiliklar.values()) if ml_olasiliklar else 0.0

        gerekce_parcalari = []
        if kural_sonuc.get("gerekce"):
            gerekce_parcalari.append(f"kural: {kural_sonuc['gerekce']}")
        gerekce_parcalari.append(
            f"istatistiksel model (NB): {ml_tur} (güven {ml_guven:.2f})"
        )

        tur_info = EVRAK_TURLERI[best_type]
        return {
            "tur": best_type,
            "tur_adi": tur_info["ad"],
            "guven": round(min(max(confidence, 0.0), 1.0), 3),
            "aciklama": tur_info["aciklama"],
            "gerekce": "; ".join(gerekce_parcalari),
            "yontem": "hibrit_ensemble",
            "kural_guven": kural_sonuc.get("guven", 0.0),
            "kural_tur": kural_sonuc.get("tur", ""),
            "ml_guven": round(ml_guven, 3),
            "ml_tur": ml_tur,
            "tum_skorlar": {t: round(p, 3) for t, p in birlesik.items()},
            "ham_skorlar": kural_sonuc.get("ham_skorlar", {}),
            "ml_skorlar": {t: round(p, 3) for t, p in ml_olasiliklar.items()},
        }

    # ------------------------------------------------------------------
    # LLM eskalasyonu
    # ------------------------------------------------------------------

    def _classify_with_llm(self, text: str, rule_result: dict) -> dict:
        """
        LLM tabanlı sınıflandırma (yapılandırılmış JSON çıktısıyla).

        Args:
            text: Evrak metni
            rule_result: Kural tabanlı ön değerlendirme (bağlam için)

        Returns:
            Sınıflandırma sonucu

        Raises:
            Exception: LLM erişilemezse veya geçersiz yanıt dönerse
            (çağıran taraf kural tabanlı sonuca düşer).
        """
        from src.models.llm_wrapper import GUVENLIK_SISTEM_EKI, belge_blogu, get_default_llm

        llm = get_default_llm()

        turler_listesi = "\n".join(
            f"- {key}: {info['ad']} — {info['aciklama']}"
            for key, info in EVRAK_TURLERI.items()
        )

        schema_hint = (
            '{"tur": "<evrak_turu_key>", "guven": <0.0-1.0 arası sayı>, '
            '"gerekce": "<tek cümlelik sınıflandırma gerekçesi>"}'
        )

        # GÜVENLİK: evrak metni belge_blogu ile "yalnızca veri" olarak
        # işaretlenir (dolaylı prompt injection savunması, OWASP LLM01)
        prompt = f"""Aşağıdaki kamu evrakı metnini analiz et ve evrak türünü belirle.

Desteklenen evrak türleri (yalnızca bu key'lerden birini kullan):
{turler_listesi}

Kural tabanlı ön değerlendirme: {rule_result['tur']} (güven: {rule_result['guven']:.2f})
Bu ön değerlendirme düşük güvenli olduğu için senden kesin karar isteniyor.

{belge_blogu(text, 3000)}"""

        data = llm.generate_json(
            prompt,
            schema_hint=schema_hint,
            system_prompt=(
                "Sen kamu kurumlarında resmî yazışma ve evrak yönetimi "
                "konusunda uzman bir sınıflandırma asistanısın."
                + GUVENLIK_SISTEM_EKI
            ),
        )

        tur_key = str(data.get("tur", "")).strip().lower()
        if tur_key not in EVRAK_TURLERI:
            raise ValueError(f"LLM geçersiz evrak türü döndürdü: {tur_key!r}")

        try:
            guven = float(data.get("guven", 0.7))
        except (TypeError, ValueError):
            guven = 0.7
        guven = min(max(guven, 0.0), 1.0)

        tur_info = EVRAK_TURLERI[tur_key]
        return {
            "tur": tur_key,
            "tur_adi": tur_info["ad"],
            "guven": round(guven, 3),
            "aciklama": tur_info["aciklama"],
            "gerekce": str(data.get("gerekce", "")).strip(),
        }
