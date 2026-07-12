"""MCP sunucusunun (src/mcp_server.py) JSON-RPC dispatch testleri.

stdio döngüsü olmadan istek_isle() işlev düzeyinde test edilir.
"""

import json

from src.mcp_server import ARACLAR, istek_isle


def _istek(yontem, params=None, id_=1):
    r = {"jsonrpc": "2.0", "id": id_, "method": yontem}
    if params is not None:
        r["params"] = params
    return r


class TestInitialize:
    def test_protokol_ve_sunucu(self):
        y = istek_isle(_istek("initialize"))
        assert y["result"]["protocolVersion"]
        assert y["result"]["serverInfo"]["name"] == "kamu-evrak-akilli-ajan"


class TestToolsList:
    def test_bes_arac(self):
        y = istek_isle(_istek("tools/list"))
        adlar = {a["name"] for a in y["result"]["tools"]}
        assert adlar == {
            "evrak_isle", "evrak_anonimlestir", "birimleri_listele",
            "evrak_turlerini_listele", "sistem_sagligi",
        }

    def test_semada_arac_sayisi(self):
        assert len(ARACLAR) == 5


class TestToolsCall:
    def test_sistem_sagligi(self):
        y = istek_isle(_istek("tools/call", {"name": "sistem_sagligi", "arguments": {}}))
        icerik = y["result"]["content"][0]["text"]
        assert isinstance(json.loads(icerik), dict)

    def test_birimleri_listele(self):
        y = istek_isle(_istek("tools/call", {"name": "birimleri_listele"}))
        assert "content" in y["result"]

    def test_evrak_isle(self):
        y = istek_isle(_istek("tools/call", {
            "name": "evrak_isle",
            "arguments": {"metin": "3071 sayılı dilekçemin işleme alınmasını arz ederim."},
        }))
        veri = json.loads(y["result"]["content"][0]["text"])
        assert "siniflandirma" in veri

    def test_bilinmeyen_arac_hata(self):
        y = istek_isle(_istek("tools/call", {"name": "olmayan_arac"}))
        assert "error" in y


class TestProtokol:
    def test_bildirim_yanit_uretmez(self):
        assert istek_isle(_istek("notifications/initialized", id_=None)) is None

    def test_bilinmeyen_yontem_hata(self):
        y = istek_isle(_istek("olmayan/yontem"))
        assert y["error"]["code"] == -32601
