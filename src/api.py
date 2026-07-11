"""
REST API — EBYS entegrasyonu için hafif HTTP servisi (yalnızca stdlib).

Kamu kurumlarının Elektronik Belge Yönetim Sistemleri (EBYS), evrak
işleme yeteneklerini ağ üzerinden çağırabilsin diye tasarlanmış,
sıfır ek bağımlılıklı (http.server tabanlı) JSON API'si.

Uçlar:
    GET  /saglik              → servis durumu, sürüm, LLM backend, ajan sayısı
    POST /evrak/isle          → {"metin", "mod"} → uçtan uca pipeline sonucu
    POST /evrak/anonimlestir  → {"metin"} → KVKK paylaşım nüshası + rapor
    GET  /birimler            → yönlendirme birim kataloğu
    GET  /evrak-turleri       → evrak türü kataloğu

Güvenlik / sağlamlık ilkeleri:
    - Varsayılan bind adresi 127.0.0.1'dir: servis, ters proxy veya EBYS
      sunucusuyla aynı makinede çalışacak şekilde dışa kapalı başlar
      (kamu ağlarında doğrudan internete açık servis istenmez).
    - Gövde boyutu üst sınırı 1 MB'dir (CWE-400: kaynak tüketimi);
      aşan istekler bellek tüketmeden 413 ile reddedilir.
    - Geçersiz JSON → 400, bilinmeyen uç → 404; hata mesajları Türkçedir
      ve iç ayrıntı (stack trace) sızdırmaz.
    - Pipeline modül düzeyinde bir kez, tembel (lazy) kurulur; orkestratör
      paylaşılan durum tuttuğu için istekler bir kilitle sıralanır
      (ThreadingHTTPServer eşzamanlı bağlantı kabul eder, evrak işleme
      adımı ise durum tutarlılığı için tek tek yürütülür).
    - Her istek loglanır (kamu denetim izi pratiği).

Başlatma:
    python3 -m src.api                 # 127.0.0.1:8765
    python3 -m src.api --port 9000     # farklı port
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

logger = logging.getLogger("kamu_evrak_ajan.api")

# ----------------------------------------------------------------------
# Sabitler
# ----------------------------------------------------------------------

# GÜVENLİK (CWE-400): istek gövdesi üst sınırı. Tipik resmî evrak birkaç
# KB'dir; 1 MB sınırı en uzun evrakları bile fazlasıyla karşılar, buna
# karşın kötü niyetli/dev gövdelerin belleği doldurmasını engeller.
MAX_GOVDE_BAYT = 1_000_000

# 413 yanıtı öncesi gövdeden okunup atılacak azami bayt: istemcinin
# gönderim tamponu boşalsın diye sınırlı miktarda okunur (bağlantı kaba
# biçimde kesilmez), ama sınırsız akıtmaya da izin verilmez.
_ATIK_OKUMA_SINIRI = 8_000_000
_ATIK_OKUMA_PARCA = 65_536

# Geçerli işleme modları (pipeline sözleşmesiyle birebir aynı)
_GECERLI_MODLAR = ("full", "classify", "draft")

# ----------------------------------------------------------------------
# Pipeline: modül düzeyi tembel tekil örnek
# ----------------------------------------------------------------------

_pipeline = None
# Orkestratör, istekler arasında paylaşılan AgentState tuttuğu için hem
# kurulum hem kullanım tek kilitle korunur (eşzamanlı isteklerde durum
# karışması / yarış koşulu önlenir).
_pipeline_kilidi = threading.Lock()


def _pipeline_getir():
    """Uçtan uca pipeline'ı döndürür; ilk çağrıda bir kez kurar."""
    global _pipeline
    if _pipeline is None:
        from src.pipelines.end_to_end_pipeline import EndToEndPipeline

        _pipeline = EndToEndPipeline()
        logger.info("API pipeline'ı kuruldu (tekil örnek).")
    return _pipeline


# ----------------------------------------------------------------------
# Uç işlevleri (HTTP'den bağımsız iş mantığı — test edilebilirlik için ayrı)
# ----------------------------------------------------------------------


def _saglik_bilgisi() -> dict:
    """Servis sağlık özetini üretir (sürüm, LLM backend, ajan sayısı)."""
    from src import __version__

    with _pipeline_kilidi:
        pipeline = _pipeline_getir()
        ajan_sayisi = len(pipeline.orchestrator.agents)

    try:
        from src.models.llm_wrapper import get_default_llm

        llm_backend = get_default_llm().backend
    except Exception:
        # LLM tamamen opsiyoneldir; tespit hatası sağlık durumunu düşürmez.
        llm_backend = "bilinmiyor"

    return {
        "durum": "calisiyor",
        "surum": __version__,
        "llm_backend": llm_backend,
        "ajan_sayisi": ajan_sayisi,
    }


def _evrak_isle(metin: str, mod: str) -> dict:
    """Evrak metnini uçtan uca pipeline ile işler (kilit altında)."""
    with _pipeline_kilidi:
        pipeline = _pipeline_getir()
        return pipeline.process_text(metin, mode=mod, source_name="api_istegi")


def _evrak_anonimlestir(metin: str) -> dict:
    """
    Evrak metninin KVKK paylaşım nüshasını üretir.

    Tam pipeline yerine yalnızca gerekli iki ajan çalıştırılır:
    bilgi çıkarımı (kişi adı/iletişim adayları) + anonimleştirme.
    Girdi, orkestratörün merkezî uzunluk sınırıyla tutarlı biçimde
    kırpılır (bu uç orkestratör akışını atladığı için sınır burada
    ayrıca uygulanır).
    """
    from src.agents.orchestrator import _MAX_GIRDI_KARAKTER, AgentState

    metin = metin[:_MAX_GIRDI_KARAKTER]
    with _pipeline_kilidi:
        pipeline = _pipeline_getir()
        state = AgentState(input_file="api_anonimlestirme", raw_text=metin)
        pipeline.orchestrator.agents["info_extraction"].run(state)
        pipeline.orchestrator.agents["anonimlestirme"].run(state)

    return {
        "anonim_metin": state.anonymized_text,
        "rapor": state.anonymization_report,
    }


def _birim_katalogu() -> dict:
    """Yönlendirme ajanının tanıdığı birimlerin kataloğunu döndürür."""
    from src.agents.routing_agent import BIRIMLER

    birimler = [
        {"kod": kod, "ad": bilgi.get("ad", kod), "aciklama": bilgi.get("aciklama", "")}
        for kod, bilgi in BIRIMLER.items()
    ]
    return {"birimler": birimler, "adet": len(birimler)}


def _evrak_turu_katalogu() -> dict:
    """Sınıflandırma ajanının tanıdığı evrak türlerinin kataloğunu döndürür."""
    from src.agents.classification_agent import EVRAK_TURLERI

    turler = [
        {"kod": kod, "ad": bilgi.get("ad", kod), "aciklama": bilgi.get("aciklama", "")}
        for kod, bilgi in EVRAK_TURLERI.items()
    ]
    return {"evrak_turleri": turler, "adet": len(turler)}


# ----------------------------------------------------------------------
# HTTP katmanı
# ----------------------------------------------------------------------


class EvrakAPIHandler(BaseHTTPRequestHandler):
    """
    Evrak API'sinin HTTP istek işleyicisi.

    Tüm yanıtlar UTF-8 JSON'dur; hata gövdeleri {"hata": "..."} biçiminde
    Türkçe açıklama taşır ve iç ayrıntı sızdırmaz.
    """

    server_version = "KamuEvrakAjanAPI/1.0"
    protocol_version = "HTTP/1.1"
    # GÜVENLİK: yavaş/bağlı kalan istemcilerin işleyici thread'ini süresiz
    # meşgul etmemesi için soket zaman aşımı (slowloris benzeri durumlar).
    timeout = 60

    # ------------------------------------------------------------------
    # Yanıt yardımcıları
    # ------------------------------------------------------------------

    def _json_yanit(self, durum_kodu: int, veri: dict, baglanti_kapat: bool = False) -> None:
        """JSON gövdeli HTTP yanıtı gönderir (UTF-8, Content-Length'li)."""
        govde = json.dumps(veri, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(durum_kodu)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(govde)))
        if baglanti_kapat:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(govde)

    def _hata_yanit(self, durum_kodu: int, mesaj: str, baglanti_kapat: bool = False) -> None:
        """Türkçe hata mesajlı JSON yanıtı gönderir."""
        self._json_yanit(durum_kodu, {"hata": mesaj}, baglanti_kapat=baglanti_kapat)

    def log_message(self, format: str, *args: Any) -> None:
        """İstek loglarını proje logger'ına yönlendirir (denetim izi)."""
        logger.info("%s - %s", self.address_string(), format % args)

    # ------------------------------------------------------------------
    # Gövde okuma / doğrulama
    # ------------------------------------------------------------------

    def _govde_oku(self) -> Optional[bytes]:
        """
        İstek gövdesini boyut sınırı denetimiyle okur.

        Sınır aşımında 413, Content-Length yokluğunda 411, geçersiz
        değerde 400 yanıtı gönderilir ve None döndürülür.
        """
        uzunluk_ham = self.headers.get("Content-Length")
        if uzunluk_ham is None:
            self._hata_yanit(411, "Content-Length başlığı zorunludur.")
            return None
        try:
            uzunluk = int(uzunluk_ham)
        except (TypeError, ValueError):
            self._hata_yanit(400, "Content-Length başlığı geçersiz.")
            return None
        if uzunluk < 0:
            self._hata_yanit(400, "Content-Length başlığı geçersiz.")
            return None
        if uzunluk > MAX_GOVDE_BAYT:
            # GÜVENLİK: dev gövde belleğe alınmaz. İstemcinin gönderimi
            # kilitlenmesin diye sınırlı miktarı parça parça okunup atılır,
            # ardından 413 gönderilir ve bağlantı kapatılır.
            self._govdeyi_at(min(uzunluk, _ATIK_OKUMA_SINIRI))
            self._hata_yanit(
                413,
                f"İstek gövdesi çok büyük (sınır: {MAX_GOVDE_BAYT} bayt).",
                baglanti_kapat=True,
            )
            return None
        return self.rfile.read(uzunluk)

    def _govdeyi_at(self, bayt: int) -> None:
        """Gövdeden en fazla `bayt` baytı sabit bellek kullanımıyla okuyup atar."""
        kalan = bayt
        try:
            while kalan > 0:
                parca = self.rfile.read(min(_ATIK_OKUMA_PARCA, kalan))
                if not parca:
                    break
                kalan -= len(parca)
        except Exception:
            # Atık okuma başarısızlığı yanıtı engellemez.
            pass

    def _json_govde(self) -> Optional[dict]:
        """Gövdeyi JSON nesnesi olarak çözümler; hatada yanıtı kendisi gönderir."""
        govde = self._govde_oku()
        if govde is None:
            return None
        try:
            veri = json.loads(govde.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._hata_yanit(400, "İstek gövdesi geçerli bir JSON değil.")
            return None
        if not isinstance(veri, dict):
            self._hata_yanit(400, "İstek gövdesi bir JSON nesnesi (sözlük) olmalıdır.")
            return None
        return veri

    def _metin_al(self, veri: dict) -> Optional[str]:
        """'metin' alanını doğrular; geçersizse 400 yanıtı gönderir."""
        metin = veri.get("metin")
        if not isinstance(metin, str) or not metin.strip():
            self._hata_yanit(400, "'metin' alanı zorunludur ve boş olmayan bir metin olmalıdır.")
            return None
        return metin

    # ------------------------------------------------------------------
    # HTTP fiilleri
    # ------------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 (http.server sözleşmesi)
        """GET uçlarını yönlendirir."""
        yol = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        try:
            if yol == "/saglik":
                self._json_yanit(200, _saglik_bilgisi())
            elif yol == "/birimler":
                self._json_yanit(200, _birim_katalogu())
            elif yol == "/evrak-turleri":
                self._json_yanit(200, _evrak_turu_katalogu())
            else:
                self._hata_yanit(404, f"Bilinmeyen uç: {yol}")
        except Exception as exc:
            logger.error(f"GET {yol} işlenirken hata: {exc}")
            self._hata_yanit(500, "Sunucu tarafında beklenmeyen bir hata oluştu.")

    def do_POST(self) -> None:  # noqa: N802 (http.server sözleşmesi)
        """POST uçlarını yönlendirir."""
        yol = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"
        if yol not in ("/evrak/isle", "/evrak/anonimlestir"):
            # Bilinmeyen uçta gövde yine sınırlı biçimde tüketilir ki
            # HTTP/1.1 kalıcı bağlantıda akış bozulmasın.
            self._govdeyi_at_basliktan()
            self._hata_yanit(404, f"Bilinmeyen uç: {yol}")
            return

        veri = self._json_govde()
        if veri is None:
            return
        metin = self._metin_al(veri)
        if metin is None:
            return

        try:
            if yol == "/evrak/isle":
                mod = veri.get("mod", "full")
                if mod not in _GECERLI_MODLAR:
                    self._hata_yanit(
                        400,
                        f"Geçersiz 'mod' değeri: {mod!r}. "
                        f"Geçerli değerler: {', '.join(_GECERLI_MODLAR)}.",
                    )
                    return
                self._json_yanit(200, _evrak_isle(metin, mod))
            else:  # /evrak/anonimlestir
                self._json_yanit(200, _evrak_anonimlestir(metin))
        except Exception as exc:
            # İç ayrıntı yanıtta sızdırılmaz; log denetim izinde kalır.
            logger.error(f"POST {yol} işlenirken hata: {exc}")
            self._hata_yanit(500, "Evrak işlenirken sunucu tarafında bir hata oluştu.")

    def _govdeyi_at_basliktan(self) -> None:
        """Content-Length başlığına göre gövdeyi sınırlı biçimde okuyup atar."""
        try:
            uzunluk = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            uzunluk = 0
        if uzunluk > 0:
            self._govdeyi_at(min(uzunluk, _ATIK_OKUMA_SINIRI))


# ----------------------------------------------------------------------
# Sunucu kurulumu / başlatma
# ----------------------------------------------------------------------


def sunucu_olustur(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """
    API sunucusunu oluşturur (başlatmaz).

    Testlerin port=0 (işletim sistemi seçer) ile ayrı thread'de
    çalıştırabilmesi için başlatmadan ayrı tutulmuştur.

    Args:
        host: Bind adresi. GÜVENLİK: varsayılan 127.0.0.1'dir; dışa açmak
            bilinçli bir karar olmalı ve ters proxy arkasında yapılmalıdır.
        port: Dinlenecek port (0 → boş bir port otomatik seçilir).

    Returns:
        Kullanıma hazır ThreadingHTTPServer örneği
    """
    sunucu = ThreadingHTTPServer((host, port), EvrakAPIHandler)
    logger.info(f"API sunucusu oluşturuldu: http://{sunucu.server_address[0]}:{sunucu.server_address[1]}")
    return sunucu


def calistir(host: str = "127.0.0.1", port: int = 8765) -> None:
    """
    API sunucusunu başlatır ve istekleri dinler (bloklar).

    Args:
        host: Bind adresi (varsayılan: yalnızca localhost)
        port: Dinlenecek port (varsayılan: 8765)
    """
    sunucu = sunucu_olustur(host, port)
    gercek_host, gercek_port = sunucu.server_address[0], sunucu.server_address[1]
    logger.info(f"Kamu Evrak Akıllı Ajan API'si dinlemede: http://{gercek_host}:{gercek_port}")
    print(f"Kamu Evrak Akıllı Ajan API'si: http://{gercek_host}:{gercek_port} (durdurmak için Ctrl+C)")
    try:
        sunucu.serve_forever()
    except KeyboardInterrupt:
        print("\nAPI sunucusu kapatılıyor...")
    finally:
        sunucu.shutdown()
        sunucu.server_close()
        logger.info("API sunucusu kapatıldı.")


def _main() -> None:
    """Komut satırı girişi: python3 -m src.api [--host H] [--port P]."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Kamu Evrak Akıllı Ajan REST API (EBYS entegrasyonu)"
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Bind adresi (varsayılan: 127.0.0.1 — yalnızca yerel erişim)",
    )
    parser.add_argument("--port", type=int, default=8765, help="Port (varsayılan: 8765)")
    args = parser.parse_args()
    calistir(host=args.host, port=args.port)


if __name__ == "__main__":
    _main()
