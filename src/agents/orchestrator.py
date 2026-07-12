"""
Orkestratör Agent — Tüm agent'ları koordine eden ana yönetici.

Bu agent, evrak işleme sürecindeki tüm alt agent'ları yönetir,
görev sırasını belirler ve sonuçları birleştirir.

Tasarım:
    - Her adım ölçümlenir (süre + durum) → gerçek zamana yakın çalışma kanıtı.
    - Sınıflandırma güven skoru düşükse LLM eskalasyonu sınıflandırma
      agent'ının içinde yapılır; orkestratör güven izleme kaydını tutar.
    - Girdi dosya (OCR üzerinden) veya doğrudan metin olabilir.
    - Akış KOŞULLUDUR (düz sıralı zincir değildir); üç koşullu kapı vardır:
        Kapı 1 — Okunabilirlik: OCR/metin sonrası anlamlı içerik yoksa
          (boş veya çok kısa metin) Görev 1/2 adımları atlanır, sınıflandırma
          "bilinmiyor" işaretlenir ve kullanıcı bilgilendirilir.
        Kapı 2 — Dil sezimi: metin Türkçe görünmüyorsa resmî yazı taslağı
          üretimi (Görev 2) atlanır; sınıflandırma/analiz yine çalışır.
        Kapı 3 — Düşük güven: sınıflandırma veya yönlendirme güveni eşiğin
          altındaysa "insan onayı gerekli" işareti konur ve kullanıcı
          uyarılır (offline modda LLM eskalasyonu çalışamayacağı için bu
          işaret insan kontrolünü zorunlu kılar).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from src.utils.turkish_nlp import is_turkish_text

logger = logging.getLogger("kamu_evrak_ajan.orchestrator")

# ----------------------------------------------------------------------
# Koşullu kapı eşikleri
# ----------------------------------------------------------------------
# Kapı 1: işlenebilir sayılmak için metinde bulunması gereken en az
# anlamlı (harf/rakam) karakter sayısı. Bunun altındaki girdi, geçerli
# bir evrak içeriği taşımaz (boş sayfa, OCR artığı, birkaç kelime).
_MIN_ANLAMLI_KARAKTER = 30

# Kapı 3: bu eşiğin altındaki güven skorları insan kontrolü gerektirir
# (sınıflandırma agent'ının LLM eskalasyon eşiğiyle aynı değerdir;
# offline modda eskalasyon çalışamayacağı için işaret orkestratörde konur).
_INSAN_ONAYI_GUVEN_ESIGI = 0.6

# GÜVENLİK (CWE-400/OWASP LLM04): güvenilmeyen evrak metni için merkezî
# azami uzunluk. Bunun üzerindeki girdi kırpılır; böylece regex tabanlı
# çıkarım ve LLM çağrıları sınırsız kaynak tüketemez. Sınır tipik resmî
# evrağın (birkaç KB) çok üzerindedir; olağan işlevi etkilemez.
_MAX_GIRDI_KARAKTER = 200_000


@dataclass
class AgentState:
    """
    Agent'lar arası paylaşılan durum nesnesi.

    Evrak işleme sürecinin her aşamasında güncellenir ve
    bir sonraki agent'a aktarılır.
    """

    # Giriş
    input_file: str = ""
    raw_text: str = ""

    # Görev 1 sonuçları
    ocr_result: dict = field(default_factory=dict)
    classification: dict = field(default_factory=dict)
    extracted_info: dict = field(default_factory=dict)
    missing_info: list = field(default_factory=list)
    legislation_matches: list = field(default_factory=list)
    # Mevzuat aramasının izlenebilirlik meta bilgisi: kullanılan yöntem
    # (bm25 / bm25+semantik / +rerank / chromadb / kural_tabanli) ve
    # düzeltici (corrective) sorgu genişletme döngüsünün kaydı
    legislation_meta: dict = field(default_factory=dict)
    summary: str = ""
    summary_body: str = ""  # Künye satırı olmadan, cümle bütünlüğü korunmuş özet gövdesi

    # Yenilik modülleri (Görev 1'i güçlendiren ek yetenekler)
    # anonymized_text/anonymization_report: KVKK paylaşım nüshası (6698 sK. bağlamı)
    # triage: aciliyet/yasal süre tespiti ve son işlem tarihi
    anonymized_text: str = ""
    anonymization_report: dict = field(default_factory=dict)
    triage: dict = field(default_factory=dict)

    # Görev 2 sonuçları
    draft_text: str = ""
    draft_type: str = ""
    format_validation: dict = field(default_factory=dict)
    # Bağımsız taslak kalite hakemi sonucu (0-100 puan + bileşenler)
    draft_quality: dict = field(default_factory=dict)
    routing_suggestion: dict = field(default_factory=dict)
    user_notifications: list = field(default_factory=list)
    clarification_requests: list = field(default_factory=list)

    # Meta / izlenebilirlik
    errors: list = field(default_factory=list)
    processing_steps: list = field(default_factory=list)
    confidence_trace: list = field(default_factory=list)

    # Koşullu akış / düşük güven meta alanları
    # workflow_warnings: koşullu kapıların ürettiği kullanıcı uyarıları
    #   [{"kod", "baslik", "mesaj", "seviye"}, ...] — user_info agent'ı
    #   bunları bilgilendirme mesajlarına dönüştürür.
    # human_review_required: güven eşiği altındaki kararlar için insan
    #   kontrolü gerektiğini belirtir; gerekçeleri human_review_reasons'ta.
    workflow_warnings: list = field(default_factory=list)
    human_review_required: bool = False
    human_review_reasons: list = field(default_factory=list)


class OrchestratorAgent:
    """
    Ana orkestratör agent.

    Tüm alt agent'ları yönetir ve evrak işleme iş akışını koordine eder.
    İki ana görev bloğunu sırayla çalıştırır:
      - Görev 1: Evrak Sınıflandırma ve İçerik Analizi
      - Görev 2: Resmi Yazı Taslaklama ve Birim Yönlendirme
    """

    def __init__(self) -> None:
        """Orkestratör agent'ı başlatır ve alt agent'ları yükler."""
        self.agents: dict[str, Any] = {}
        self.state = AgentState()
        logger.info("Orkestratör agent başlatıldı.")
        self._load_agents()

    def _load_agents(self) -> None:
        """Alt agent'ları yükler ve kaydeder."""
        from src.agents.ocr_agent import OCRAgent
        from src.agents.classification_agent import ClassificationAgent
        from src.agents.info_extraction_agent import InfoExtractionAgent
        from src.agents.missing_info_agent import MissingInfoAgent
        from src.agents.legislation_agent import LegislationAgent
        from src.agents.summarization_agent import SummarizationAgent
        from src.agents.draft_writer_agent import DraftWriterAgent
        from src.agents.routing_agent import RoutingAgent
        from src.agents.user_info_agent import UserInfoAgent
        from src.agents.triage_agent import TriageAgent
        from src.agents.anonimlestirme_agent import AnonimlestirmeAgent

        self.agents = {
            "ocr": OCRAgent(),
            "classification": ClassificationAgent(),
            "info_extraction": InfoExtractionAgent(),
            "missing_info": MissingInfoAgent(),
            "legislation": LegislationAgent(),
            "summarization": SummarizationAgent(),
            "draft_writer": DraftWriterAgent(),
            "routing": RoutingAgent(),
            "user_info": UserInfoAgent(),
            "triage": TriageAgent(),
            "anonimlestirme": AnonimlestirmeAgent(),
        }
        logger.info(f"{len(self.agents)} alt agent yüklendi.")

    def process(self, input_file: str, mode: str = "full", on_step=None) -> dict:
        """
        Evrak dosyasını işleme sürecini başlatır.

        Args:
            input_file: İşlenecek evrak dosya yolu
            mode: Çalışma modu ('full', 'classify', 'draft')
            on_step: Opsiyonel geri-çağırım; her ajan adımı TAMAMLANDIĞINDA adım
                sözlüğüyle ({agent, description, status, sure_saniye}) çağrılır —
                canlı akış (streaming) arayüzü için. None ise davranış değişmez.

        Returns:
            Tüm işlem sonuçlarını içeren sözlük
        """
        self._on_step = on_step
        self.state = AgentState(input_file=input_file)
        logger.info(f"Evrak işleme başlatıldı: {input_file} (mod: {mode})")
        self._run_step("ocr", "OCR ile metin çıkarımı")
        return self._run_workflow(mode)

    def process_text(
        self, text: str, mode: str = "full",
        source_name: str = "dogrudan_metin", on_step=None,
    ) -> dict:
        """
        Doğrudan metin girişini işler (dosya/OCR adımı olmadan).

        Args:
            text: İşlenecek evrak metni
            mode: Çalışma modu ('full', 'classify', 'draft')
            source_name: Kaynak etiketi (raporlamada gösterilir)
            on_step: Opsiyonel adım geri-çağırımı (canlı akış için).

        Returns:
            Tüm işlem sonuçlarını içeren sözlük
        """
        self._on_step = on_step
        self.state = AgentState(input_file=source_name, raw_text=text)
        self.state.ocr_result = {
            "source_file": source_name,
            "file_type": "text",
            "character_count": len(text),
            "word_count": len(text.split()),
            "engine_used": "direct",
        }
        logger.info(f"Doğrudan metin işleme başlatıldı ({len(text)} karakter, mod: {mode})")
        return self._run_workflow(mode)

    def _apply_girdi_siniri(self) -> None:
        """
        Güvenilmeyen evrak metnini merkezî azami uzunlukta kırpar.

        # GÜVENLİK: hem dosya (OCR) hem doğrudan metin yolu bu tek noktadan
        # geçtiği için sınır burada uygulanır; aşırı uzun girdi regex/LLM
        # adımlarını sınırsız meşgul edemez (CWE-400 / OWASP LLM04).
        """
        if len(self.state.raw_text) > _MAX_GIRDI_KARAKTER:
            asil = len(self.state.raw_text)
            self.state.raw_text = self.state.raw_text[:_MAX_GIRDI_KARAKTER]
            self.state.workflow_warnings.append({
                "kod": "girdi_kirpildi",
                "baslik": "Girdi Uzunluk Sınırı",
                "mesaj": (
                    f"Evrak metni çok uzun ({asil} karakter); güvenlik/başarım "
                    f"gereği ilk {_MAX_GIRDI_KARAKTER} karakter işlendi."
                ),
                "seviye": "uyari",
            })
            logger.warning(
                f"Girdi metni {asil} karakter; {_MAX_GIRDI_KARAKTER} karaktere kırpıldı."
            )

    def _run_workflow(self, mode: str) -> dict:
        """OCR sonrası ortak iş akışını koşullu kapılarla çalıştırır."""
        self._apply_girdi_siniri()
        try:
            # KOŞULLU KAPI 1: metin okunabilirliği (boş/çok kısa metinde
            # analiz ve taslak adımları çalıştırılmaz; uydurma çıktı üretilmez)
            metin_okunabilir = self._metin_okunabilir_mi()
            if not metin_okunabilir:
                self._uygula_bos_metin_kapisi(mode)

            # KOŞULLU KAPI 2: dil sezimi (yalnızca okunabilir metinde anlamlı)
            metin_turkce = self._metin_turkce_mi() if metin_okunabilir else True

            if mode in ("full", "classify") and metin_okunabilir:
                # GÖREV 1: Evrak Sınıflandırma ve İçerik Analizi
                self._run_step("classification", "Evrak sınıflandırma")
                self._record_confidence("classification", self.state.classification.get("guven"))
                # KOŞULLU KAPI 3a: düşük sınıflandırma güveni → insan onayı
                self._degerlendir_siniflandirma_guveni()
                self._run_step("info_extraction", "Bilgi çıkarma")
                self._run_step("missing_info", "Eksik bilgi tespiti")
                self._run_step("legislation", "Mevzuat eşleştirme")
                self._run_step("triage", "Aciliyet/yasal süre tespiti")
                self._run_step("summarization", "Özet oluşturma")
                self._run_step("anonimlestirme", "KVKK paylaşım nüshası")

            if mode in ("full", "draft"):
                # GÖREV 2: Resmi Yazı Taslaklama ve Birim Yönlendirme
                if metin_okunabilir and metin_turkce:
                    self._run_step("draft_writer", "Yazı taslağı oluşturma")
                elif metin_okunabilir:
                    self._skip_step(
                        "draft_writer", "Yazı taslağı oluşturma",
                        "evrak dili Türkçe görünmüyor",
                    )
                if metin_okunabilir:
                    self._run_step("routing", "Birim yönlendirme")
                    self._record_confidence("routing", self.state.routing_suggestion.get("guven"))
                    # KOŞULLU KAPI 3b: düşük yönlendirme güveni → insan onayı
                    self._degerlendir_yonlendirme_guveni()
                # Kullanıcı bilgilendirme her durumda çalışır: kapı uyarıları
                # (workflow_warnings) kullanıcıya bu adımda iletilir.
                self._run_step("user_info", "Kullanıcı bilgilendirme")

        except Exception as e:
            logger.error(f"İşlem sırasında hata: {e}")
            self.state.errors.append(str(e))

        return self._compile_results()

    # ------------------------------------------------------------------
    # Koşullu kapılar
    # ------------------------------------------------------------------

    def _metin_okunabilir_mi(self) -> bool:
        """
        Kapı 1: metinde işlenmeye yetecek anlamlı içerik var mı?

        Anlamlı karakter = harf veya rakam; boşluk/noktalama sayılmaz.
        """
        anlamli = sum(1 for ch in self.state.raw_text if ch.isalnum())
        return anlamli >= _MIN_ANLAMLI_KARAKTER

    def _uygula_bos_metin_kapisi(self, mode: str) -> None:
        """
        Kapı 1 tetiklendiğinde durumu işaretler.

        Görev 1/2 analiz-taslak adımları için "atlandı" kaydı düşer,
        sınıflandırmayı "bilinmiyor" olarak işaretler ve kullanıcıya
        geçerli bir evrak yüklemesi gerektiği uyarısını hazırlar.
        Sonuç sözlüğü yapısı korunur (ilgili alanlar boş kalır).
        """
        neden = "evrak metni okunamadı veya çok kısa"
        if mode in ("full", "classify"):
            for agent_name, desc in [
                ("classification", "Evrak sınıflandırma"),
                ("info_extraction", "Bilgi çıkarma"),
                ("missing_info", "Eksik bilgi tespiti"),
                ("legislation", "Mevzuat eşleştirme"),
                ("summarization", "Özet oluşturma"),
            ]:
                self._skip_step(agent_name, desc, neden)
        if mode in ("full", "draft"):
            self._skip_step("draft_writer", "Yazı taslağı oluşturma", neden)
            self._skip_step("routing", "Birim yönlendirme", neden)

        self.state.classification = {
            "tur": "bilinmiyor",
            "tur_adi": "Bilinmiyor",
            "guven": 0.0,
            "aciklama": "Evrak metni okunamadı veya sınıflandırma için çok kısa",
            "yontem": "kural_tabanli",
        }
        self.state.workflow_warnings.append({
            "kod": "bos_metin",
            "baslik": "Evrak Metni Okunamadı",
            "mesaj": (
                "Evrak metni okunamadı veya çok kısa (en az "
                f"{_MIN_ANLAMLI_KARAKTER} anlamlı karakter beklenir) — "
                "lütfen geçerli bir evrak yükleyin. Sınıflandırma ve "
                "taslak üretimi adımları bu nedenle atlandı."
            ),
            "seviye": "uyari",
        })
        self._insan_onayi_iste(
            "Evrak metni okunamadı veya çok kısa; geçerli bir evrak "
            "yüklenip işlem tekrarlanmalıdır."
        )
        logger.warning("Kapı 1: evrak metni okunamadı/çok kısa; analiz adımları atlandı.")

    def _metin_turkce_mi(self) -> bool:
        """
        Kapı 2: metin Türkçe görünüyor mu?

        Türkçe görünmüyorsa kullanıcıya dil uyarısı hazırlar ve False
        döndürür (taslak üretimi atlanır; sınıflandırma yine çalışabilir).
        """
        if is_turkish_text(self.state.raw_text):
            return True
        self.state.workflow_warnings.append({
            "kod": "dil_uyarisi",
            "baslik": "Dil Uyarısı",
            "mesaj": (
                "Evrak dili Türkçe görünmüyor; resmî yazı taslağı üretimi "
                "bu nedenle atlandı. Sınıflandırma/analiz sonuçlarını "
                "dikkatle değerlendirin."
            ),
            "seviye": "uyari",
        })
        logger.warning("Kapı 2: evrak dili Türkçe görünmüyor; taslak üretimi atlanacak.")
        return False

    def _degerlendir_siniflandirma_guveni(self) -> None:
        """
        Kapı 3a: sınıflandırma güveni eşiğin altındaysa insan onayı ister.

        Uyarı mesajında en olası iki tür adayı (classification.tum_skorlar
        üzerinden) birlikte gösterilir; böylece düşük güvenli karar tam
        güvenli bir sonuçmuş gibi sunulmaz.
        """
        cls = self.state.classification or {}
        guven = cls.get("guven")
        if guven is None or guven >= _INSAN_ONAYI_GUVEN_ESIGI:
            return

        adaylar = self._tur_adaylari(cls)
        aday_metni = " veya ".join(adaylar) if adaylar else cls.get("tur_adi", "Bilinmiyor")
        self._insan_onayi_iste(
            f"Sınıflandırma güveni eşiğin altında ({guven:.2f} < "
            f"{_INSAN_ONAYI_GUVEN_ESIGI}); tür adayları: {aday_metni}."
        )
        self.state.workflow_warnings.append({
            "kod": "dusuk_guven_siniflandirma",
            "baslik": "Düşük Güven — Sınıflandırma",
            "mesaj": (
                f"⚠ Düşük güven — insan kontrolü önerilir "
                f"(tür adayları: {aday_metni}; güven: {guven:.2f})."
            ),
            "seviye": "uyari",
        })
        logger.warning(
            f"Kapı 3a: sınıflandırma güveni düşük ({guven:.2f}); insan onayı işaretlendi."
        )

    def _degerlendir_yonlendirme_guveni(self) -> None:
        """
        Kapı 3b: yönlendirme güveni eşiğin altındaysa insan onayı ister.

        Uyarıda önerilen birimle birlikte alternatif birimler de listelenir;
        havale kararı insan kontrolüne bırakılır.
        """
        routing = self.state.routing_suggestion or {}
        guven = routing.get("guven")
        if guven is None or guven >= _INSAN_ONAYI_GUVEN_ESIGI:
            return

        birim = routing.get("birim", "Belirsiz")
        alternatifler = [
            a.get("birim", "") for a in (routing.get("alternatifler") or [])
            if a.get("birim")
        ][:3]
        gerekce = (
            f"Yönlendirme güveni eşiğin altında ({guven:.2f} < "
            f"{_INSAN_ONAYI_GUVEN_ESIGI}); önerilen birim: {birim}."
        )
        mesaj = (
            f"⚠ Yönlendirme güveni düşük ({guven:.2f}) — insan kontrolü "
            f"önerilir. Önerilen birim: {birim}."
        )
        if alternatifler:
            ek = f" Alternatif birimler: {', '.join(alternatifler)}."
            gerekce += ek
            mesaj += ek
        self._insan_onayi_iste(gerekce)
        self.state.workflow_warnings.append({
            "kod": "dusuk_guven_yonlendirme",
            "baslik": "Düşük Güven — Yönlendirme",
            "mesaj": mesaj,
            "seviye": "uyari",
        })
        logger.warning(
            f"Kapı 3b: yönlendirme güveni düşük ({guven:.2f}); insan onayı işaretlendi."
        )

    @staticmethod
    def _tur_adaylari(cls: dict, adet: int = 2) -> list:
        """
        classification.tum_skorlar'dan en yüksek skorlu tür adlarını döndürür.

        Args:
            cls: Sınıflandırma sonucu sözlüğü
            adet: Döndürülecek en fazla aday sayısı

        Returns:
            Skor sırasına göre tür adları listesi (en fazla `adet` öğe)
        """
        skorlar = cls.get("tum_skorlar") or {}
        if not skorlar:
            return [cls["tur_adi"]] if cls.get("tur_adi") else []

        from src.agents.classification_agent import EVRAK_TURLERI

        sirali = sorted(skorlar.items(), key=lambda x: x[1], reverse=True)
        adaylar = []
        for tur, skor in sirali[:adet]:
            if skor <= 0:
                continue
            adaylar.append(EVRAK_TURLERI.get(tur, {}).get("ad", tur))
        return adaylar

    def _insan_onayi_iste(self, gerekce: str) -> None:
        """İnsan onayı işaretini koyar ve gerekçesini (tekrarsız) kaydeder."""
        self.state.human_review_required = True
        if gerekce not in self.state.human_review_reasons:
            self.state.human_review_reasons.append(gerekce)

    def _skip_step(self, agent_name: str, description: str, reason: str) -> None:
        """
        Bir adımın koşullu kapı nedeniyle atlandığını kaydeder.

        Args:
            agent_name: Atlanan agent'ın adı
            description: Adım açıklaması
            reason: Atlanma nedeni (kullanıcıya/izlemeye açıklanır)
        """
        self.state.processing_steps.append({
            "agent": agent_name,
            "description": description,
            "status": "atlandi",
            "sure_saniye": 0.0,
            "neden": reason,
        })
        logger.info(f"⤳ {description} atlandı: {reason}")

    def _record_confidence(self, step: str, confidence: Optional[float]) -> None:
        """Bir adımın güven skorunu izleme kaydına ekler."""
        if confidence is None:
            return
        entry = {
            "adim": step,
            "guven": round(float(confidence), 3),
        }
        # Sınıflandırma agent'ı eskalasyon yaptıysa yöntemini de kaydet
        if step == "classification":
            entry["yontem"] = self.state.classification.get("yontem", "")
        self.state.confidence_trace.append(entry)

    def _run_step(self, agent_name: str, description: str) -> None:
        """
        Tek bir agent adımını çalıştırır ve süresini ölçer.

        Args:
            agent_name: Çalıştırılacak agent'ın adı
            description: Adım açıklaması (loglama için)
        """
        logger.info(f"▶ {description}...")
        agent = self.agents.get(agent_name)

        if agent is None:
            logger.warning(f"Agent bulunamadı: {agent_name}")
            return

        started = time.perf_counter()
        try:
            agent.run(self.state)
            elapsed = time.perf_counter() - started
            self.state.processing_steps.append({
                "agent": agent_name,
                "description": description,
                "status": "success",
                "sure_saniye": round(elapsed, 3),
            })
            logger.info(f"✓ {description} tamamlandı ({elapsed:.2f} sn).")
        except Exception as e:
            elapsed = time.perf_counter() - started
            self.state.processing_steps.append({
                "agent": agent_name,
                "description": description,
                "status": "error",
                "sure_saniye": round(elapsed, 3),
                "error": str(e),
            })
            self.state.errors.append(f"{agent_name}: {e}")
            logger.error(f"✗ {description} sırasında hata: {e}")

        # Canlı akış (streaming) kancası: adım tamamlandığında dinleyiciye bildir.
        # Geri-çağırım hatası pipeline'ı ASLA bozmaz (yalnızca sunum katmanı).
        on_step = getattr(self, "_on_step", None)
        if on_step and self.state.processing_steps:
            try:
                on_step(self.state.processing_steps[-1])
            except Exception as cb_hata:
                logger.debug(f"on_step geri-çağırımı hatası (yok sayıldı): {cb_hata}")

    def _compile_results(self) -> dict:
        """Tüm sonuçları derleyerek tek bir sözlük döndürür."""
        return {
            "input_file": self.state.input_file,
            "ocr": self.state.ocr_result,
            "siniflandirma": self.state.classification,
            "bilgi_cikarim": self.state.extracted_info,
            "eksik_bilgiler": self.state.missing_info,
            "mevzuat_eslestirme": self.state.legislation_matches,
            "mevzuat_arama_meta": self.state.legislation_meta,
            "ozet": self.state.summary,
            "yazi_taslagi": self.state.draft_text,
            "yazi_turu": self.state.draft_type,
            "format_denetimi": self.state.format_validation,
            "taslak_kalitesi": self.state.draft_quality,
            "yonlendirme": self.state.routing_suggestion,
            "bilgilendirmeler": self.state.user_notifications,
            "eksik_bilgi_talepleri": self.state.clarification_requests,
            "onceliklendirme": self.state.triage,
            "anonimlestirme": {
                "metin": self.state.anonymized_text,
                "rapor": self.state.anonymization_report,
            },
            "guven_izleme": self.state.confidence_trace,
            "islem_adimlari": self.state.processing_steps,
            "hatalar": self.state.errors,
            # Kapı 3: düşük güvenli kararlar için insan onayı işareti
            "insan_onayi": {
                "gerekli": self.state.human_review_required,
                "gerekceler": list(self.state.human_review_reasons),
            },
        }
