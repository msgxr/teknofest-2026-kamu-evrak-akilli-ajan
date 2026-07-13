# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Arayüz asistanı — güvenli hesap makinesi + genel LLM fallback testleri.

Zeynep'in hibrit niyet motoru bilinen niyetleri eşler; bu iki eklenti kapsam-dışı
kalan yaygın soru tiplerini karşılar:
  * Saf aritmetik ('2+2', '12 çarpı 3 kaç eder') → offline hesap makinesi
    (eval YOK; AST tabanlı, kod enjeksiyonu ve kaynak-tükenmesi/DoS'a kapalı).
  * Genel bilgi/sohbet → yalnızca bir LLM YAPILANDIRILMIŞSA yanıtlanır; aksi
    halde dürüst bilgi-yetersizliği korunur (offline-first + halüsinasyon yasağı,
    Anayasal İlke 2).

app.py kurumsal Streamlit panosuna bağlıdır; Streamlit runtime'ı gerektirmemek
için hafif bir stub ile izole edilir. Testler saf-Python/offline'dır.
"""
import sys
import types

import pytest


def _streamlit_stub() -> types.ModuleType:
    """app.py'nin import edilebilmesi için asgari Streamlit taklidi."""
    st = types.ModuleType("streamlit")
    st.session_state = {}

    def _noop(*a, **k):
        def deco(f=None):
            return f if f else _noop
        return deco

    st.cache_resource = lambda *a, **k: (lambda f: f)
    st.cache_data = lambda *a, **k: (lambda f: f)
    for ad in (
        "set_page_config", "markdown", "write", "caption", "error", "info",
        "warning", "dataframe", "json", "progress", "status", "columns",
        "container", "button", "chat_input", "chat_message", "expander",
        "sidebar", "title", "header", "subheader", "metric", "tabs",
        "altair_chart", "download_button", "text_area", "selectbox", "radio",
        "file_uploader", "rerun", "stop", "divider", "image", "spinner",
        "toast", "success", "form", "form_submit_button", "number_input",
        "checkbox", "slider", "text_input", "empty", "html",
    ):
        setattr(st, ad, _noop)
    return st


@pytest.fixture(scope="module")
def app_modulu():
    """Streamlit stub'ını kurup app.py'yi bir kez import eder."""
    sys.modules["streamlit"] = _streamlit_stub()
    sys.modules.pop("app", None)
    import app  # noqa: E402
    return app


@pytest.fixture(autouse=True)
def _sifir_oturum(app_modulu):
    app_modulu.st.session_state.clear()
    yield


# --------------------------------------------------------------------------
# 1) Hesap makinesi — doğru sonuç (sembol + Türkçe sözel operatörler)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("sorgu,beklenen", [
    ("2+2", "4"),
    ("2 + 2 = ?", "4"),
    ("10-3", "7"),
    ("6*7", "42"),
    ("100/8", "12.5"),
    ("7 % 3", "1"),
    ("(5-3)*4", "8"),
    ("2^10 nedir", "1024"),
    ("2**10", "1024"),
    ("-5 + 8", "3"),
    ("2,5 + 2,5", "5"),               # ondalık virgül
    ("12 çarpı 3 kaç eder", "36"),    # sözel operatör
    ("100 bölü 4", "25"),
    ("5 üzeri 2", "25"),
    ("3 artı 4", "7"),
])
def test_hesap_dogru_sonuc(app_modulu, sorgu, beklenen):
    yanit = app_modulu._matematik_dene(sorgu)
    assert yanit is not None
    assert beklenen in yanit
    assert "🧮" in yanit
    # Tam sayı sonuçlar ondalıksız gösterilir (4, 4.0 değil).
    if beklenen.isdigit():
        assert f"= **{beklenen}**" in yanit


def test_hesap_tam_sayi_ondaliksiz(app_modulu):
    """4.0 değil 4 döner (float tam sayı sadeleştirilir)."""
    assert "**4**" in app_modulu._matematik_dene("2+2")
    assert "4.0" not in app_modulu._matematik_dene("2+2")


# --------------------------------------------------------------------------
# 2) Hesap makinesi — aritmetik OLMAYAN girdiler None döner
#    (mevzuat no, tarih, telefon, domain sorusu yanlışlıkla yakalanmamalı)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("sorgu", [
    "3071",                        # tek sayı (operatör yok) → mevzuat no
    "6698 sayılı kanun",
    "12.06.2020",                  # tarih
    "0532 123 45 67",              # telefon (operatör yok)
    "merhaba",
    "dilekçeye kaç günde cevap verilir",
    "eksik alan nedir",
    "",                            # boş
])
def test_hesap_olmayan_none(app_modulu, sorgu):
    assert app_modulu._matematik_dene(sorgu) is None


# --------------------------------------------------------------------------
# 3) GÜVENLİK — kod enjeksiyonu reddedilir (eval yok, AST beyaz-liste)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("kotu", [
    "__import__('os').system('echo x')",
    "open('/etc/passwd').read()",
    "[i for i in range(9)]",
    "().__class__.__bases__",
    "os.getcwd()",
    "1 if True else 2",
])
def test_guvenlik_enjeksiyon_reddedilir(app_modulu, kotu):
    assert app_modulu._guvenli_aritmetik(kotu) is None


# --------------------------------------------------------------------------
# 4) GÜVENLİK — kaynak-tükenmesi (DoS): devasa üs hızlıca reddedilir
# --------------------------------------------------------------------------

@pytest.mark.parametrize("dos", [
    "9**9**9",
    "2**100000",
    "999**9999999",
    "10 ** 10 ** 10",
])
def test_guvenlik_dos_devasa_us_reddedilir(app_modulu, dos):
    # Koruma çalışmazsa bu ifade süreci astırır; None ve hızlı dönmeli.
    assert app_modulu._guvenli_aritmetik(dos) is None


def test_makul_us_calisir(app_modulu):
    """DoS koruması makul kuvvetleri engellememeli."""
    assert app_modulu._guvenli_aritmetik("2**16") == 65536
    assert app_modulu._guvenli_aritmetik("3**4") == 81


# --------------------------------------------------------------------------
# 5) Entegrasyon — _orkestrator_yanit: hesap yakalanır, domain niyeti korunur
# --------------------------------------------------------------------------

def test_orkestrator_hesap_yakalar(app_modulu):
    """'2+2' hibrit niyet motoruna girmeden hesap makinesine gider."""
    assert "= **4**" in app_modulu._orkestrator_yanit("2+2")
    assert "36" in app_modulu._orkestrator_yanit("12 çarpı 3 kaç eder")


@pytest.mark.parametrize("sorgu,beklenen", [
    ("dilekçeye kaç günde cevap verilir", "Mevzuat"),
    ("kişisel veri riski var mı", "KVKK"),
    ("hangi birime yönlendireyim", "Yönlendirme"),
    ("merhaba", "yardımcı"),
    ("3071 sayılı kanun", "Mevzuat"),   # hesap makinesine değil mevzuata
])
def test_orkestrator_domain_niyeti_bozulmadi(app_modulu, sorgu, beklenen):
    """Hesap kancası Zeynep'in niyet eşlemesini bozmamalı (regresyon)."""
    yanit = app_modulu._orkestrator_yanit(sorgu)
    assert beklenen.lower() in yanit.lower()


# --------------------------------------------------------------------------
# 6) LLM fallback — offline'da None; OOD sorusu dürüst fallback'e düşer
# --------------------------------------------------------------------------

def test_llm_offline_none(app_modulu, monkeypatch):
    """LLM yapılandırılmamışsa genel yanıt üretilmez (offline-first)."""
    class _OfflineLLM:
        backend = "offline"
        model_name = "yok"

        def is_available(self):
            return False

    monkeypatch.setattr(
        "src.models.llm_wrapper.get_default_llm", lambda: _OfflineLLM())
    assert app_modulu._llm_genel_yanit("kuantum fiziği nedir") is None


def test_ood_sorusu_offline_durust_fallback(app_modulu):
    """Alan-dışı genel soru + LLM yok → uydurmaz, dürüstçe bilgi yetersizliği."""
    yanit = app_modulu._orkestrator_yanit("Fransa'nın başkenti neresi")
    assert "yeterli bilgim yok" in yanit.lower() or "🤔" in yanit


def test_llm_baglıysa_yanit_ve_kunye(app_modulu, monkeypatch):
    """LLM yapılandırılmışsa yanıt üretir ve modeli künyeyle işaretler."""
    class _AcikLLM:
        backend = "ollama"
        model_name = "llama3.1"

        def is_available(self):
            return True

        def generate(self, prompt, system_prompt=None, json_mode=False):
            return "Paris."

    monkeypatch.setattr(
        "src.models.llm_wrapper.get_default_llm", lambda: _AcikLLM())
    yanit = app_modulu._llm_genel_yanit("Fransa'nın başkenti neresi")
    assert yanit is not None
    assert "Paris" in yanit
    assert "llama3.1" in yanit   # şeffaflık: yanıtın LLM'den geldiği açık
