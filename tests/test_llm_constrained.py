"""Şema-kısıtlı LLM çözümleme (constrained decoding) testleri.

Canlı LLM olmadan, HTTP çağrısı mock'lanarak payload'a doğru kısıtın
(response_format / format) eklendiği doğrulanır.
"""

import src.models.llm_wrapper as lw


def _sahte_wrapper(monkeypatch, backend, yanit_metni):
    yakalanan = {}

    def sahte_post(url, payload, headers, timeout=90):
        yakalanan["payload"] = payload
        if backend == "openai":
            return {"choices": [{"message": {"content": yanit_metni}}]}
        return {"message": {"content": yanit_metni}}

    monkeypatch.setattr(lw, "_http_post_json", sahte_post)
    w = lw.LLMWrapper()
    w.backend = backend
    w.model_name = "test-model"
    return w, yakalanan


def test_openai_json_mode_response_format_ekler(monkeypatch):
    w, yakalanan = _sahte_wrapper(monkeypatch, "openai", '{"tur": "dilekce"}')
    sonuc = w.generate_json("Türü belirle", '{"tur": "..."}')
    assert sonuc == {"tur": "dilekce"}
    assert yakalanan["payload"]["response_format"] == {"type": "json_object"}


def test_ollama_json_mode_format_ekler(monkeypatch):
    w, yakalanan = _sahte_wrapper(monkeypatch, "ollama", '{"tur": "rapor"}')
    sonuc = w.generate_json("Türü belirle", '{"tur": "..."}')
    assert sonuc == {"tur": "rapor"}
    assert yakalanan["payload"]["format"] == "json"


def test_metin_modu_kisit_eklemez(monkeypatch):
    # Normal generate (json_mode=False) response_format EKLEMEZ
    w, yakalanan = _sahte_wrapper(monkeypatch, "openai", "düz metin yanıtı")
    w.generate("Merhaba")
    assert "response_format" not in yakalanan["payload"]
