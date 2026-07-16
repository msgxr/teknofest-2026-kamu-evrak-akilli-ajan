# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""MCP (Model Context Protocol) sunucusu — stdio üzerinden JSON-RPC 2.0.

`docs/mcp_vizyonu.md`'de tanımlı 5 aracı mevcut pipeline/API işlevlerine
VEKÂLET ettirerek çalışır hale getirir; böylece bir kurum LLM asistanı veya
Claude Desktop bu sistemi STANDART bir ajan-araç protokolüyle çağırabilir
(vizyon belgesi → çalışan artefakt). Tümüyle stdlib'dir (harici `mcp` SDK'sı
GEREKMEZ), taşıma tamamen yereldir (stdio; ağ yok). `insan_onayi.gerekli`
bayrağı ve KVKK-anonim varsayılanı yanıtta korunur.

Çalıştırma:
    python3 -m src.mcp_server        # stdin'den JSON-RPC satırları okur

Literatür: Model Context Protocol (Anthropic, 2024); JSON-RPC 2.0 spesifikasyonu.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

from src.api import (
    _birim_katalogu,
    _evrak_anonimlestir,
    _evrak_isle,
    _evrak_turu_katalogu,
    _saglik_bilgisi,
)

PROTOKOL_SURUMU = "2024-11-05"
SUNUCU_BILGISI = {"name": "kamu-evrak-akilli-ajan", "version": "0.4.0"}

ARACLAR = [
    {
        "name": "evrak_isle",
        "description": (
            "Bir kamu evrakını uçtan uca işler: tür sınıflandırma, bilgi çıkarımı, "
            "eksik bilgi, mevzuat önerisi, özet, resmî yazı taslağı ve birim "
            "yönlendirme. Yanıt insan_onayi.gerekli bayrağını taşır."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "metin": {"type": "string", "description": "İşlenecek evrak metni"},
                "mod": {"type": "string", "enum": ["full", "classify", "draft"],
                        "default": "full"},
            },
            "required": ["metin"],
        },
    },
    {
        "name": "evrak_anonimlestir",
        "description": "Evrak metnindeki kişisel verileri (T.C., ad, telefon, "
                       "e-posta, IBAN, adres) maskeleyerek KVKK uyumlu paylaşım "
                       "nüshası üretir.",
        "inputSchema": {
            "type": "object",
            "properties": {"metin": {"type": "string"}},
            "required": ["metin"],
        },
    },
    {
        "name": "birimleri_listele",
        "description": "Yönlendirme hedefi olabilecek kurum birimlerini (kod + ad) "
                       "listeler.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "evrak_turlerini_listele",
        "description": "Sistemin tanıdığı evrak türlerini (kod + ad) listeler.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "sistem_sagligi",
        "description": "Sistemin çalışma durumunu, yüklü ajan sayısını ve LLM "
                       "backend durumunu döndürür.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


_GECERLI_MODLAR = {"full", "classify", "draft"}


def _gecerli_metin(argumanlar: Dict[str, Any]) -> str:
    """'metin' argümanını doğrular (str + boş değil); değilse ValueError."""
    metin = argumanlar.get("metin", "")
    if not isinstance(metin, str) or not metin.strip():
        raise ValueError("'metin' boş olmayan bir metin (string) olmalıdır.")
    return metin


def _arac_calistir(ad: str, argumanlar: Dict[str, Any]) -> dict:
    """Araç adını mevcut API işlevine vekâlet ettirir (giriş doğrulamalı)."""
    if ad == "evrak_isle":
        metin = _gecerli_metin(argumanlar)
        mod = argumanlar.get("mod", "full")
        if mod not in _GECERLI_MODLAR:
            raise ValueError(
                f"Geçersiz mod: {mod!r}. Geçerli değerler: {sorted(_GECERLI_MODLAR)}"
            )
        return _evrak_isle(metin, mod)
    if ad == "evrak_anonimlestir":
        return _evrak_anonimlestir(_gecerli_metin(argumanlar))
    if ad == "birimleri_listele":
        return _birim_katalogu()
    if ad == "evrak_turlerini_listele":
        return _evrak_turu_katalogu()
    if ad == "sistem_sagligi":
        return _saglik_bilgisi()
    raise ValueError(f"Bilinmeyen araç: {ad}")


def istek_isle(istek: Any) -> Optional[Dict[str, Any]]:
    """Tek bir JSON-RPC 2.0 isteğini işler. Bildirim (id yok) ise None döner."""
    # DÜZELTME: üst seviye geçerli JSON nesne (sözlük) DEĞİLSE (5, "x", [], true,
    # null) sonraki .get çağrıları AttributeError atıp sunucuyu çökertirdi;
    # JSON-RPC 2.0'a uygun -32600 (geçersiz istek) döndür.
    if not isinstance(istek, dict):
        return {
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32600, "message": "Geçersiz istek: JSON nesnesi (sözlük) bekleniyor."},
        }
    yontem = istek.get("method")
    istek_id = istek.get("id")

    def sonuc(veri: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": istek_id, "result": veri}

    def hata(kod: int, mesaj: str) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": istek_id, "error": {"code": kod, "message": mesaj}}

    if yontem == "initialize":
        return sonuc({
            "protocolVersion": PROTOKOL_SURUMU,
            "capabilities": {"tools": {}},
            "serverInfo": SUNUCU_BILGISI,
        })
    if yontem == "notifications/initialized":
        return None  # bildirim; yanıt üretilmez
    if yontem == "tools/list":
        return sonuc({"tools": ARACLAR})
    if yontem == "tools/call":
        # DÜZELTME: params/arguments sözlük DEĞİLSE (ör. "x") .get çökerdi;
        # güvenle boş sözlüğe indirge (ad=None → _arac_calistir -32602 döndürür).
        params = istek.get("params")
        if not isinstance(params, dict):
            params = {}
        ad = params.get("name")
        argumanlar = params.get("arguments")
        if not isinstance(argumanlar, dict):
            argumanlar = {}
        try:
            veri = _arac_calistir(ad, argumanlar)
            return sonuc({
                "content": [
                    {"type": "text", "text": json.dumps(veri, ensure_ascii=False)}
                ]
            })
        except ValueError as exc:  # kontrollü giriş doğrulama hatası
            return hata(-32602, str(exc))
        except Exception:  # noqa: BLE001 — iç istisna istemciye HAM sızdırılmaz
            return hata(-32603, "Araç çalıştırılırken bir iç hata oluştu.")

    if istek_id is None:
        return None  # bilinmeyen bildirim → sessiz
    return hata(-32601, f"Bilinmeyen yöntem: {yontem}")


def main() -> None:
    """stdin'den satır-satır JSON-RPC okur, stdout'a yanıt yazar (MCP stdio)."""
    for satir in sys.stdin:
        satir = satir.strip()
        if not satir:
            continue
        try:
            istek = json.loads(satir)
        except json.JSONDecodeError:
            continue
        # DÜZELTME: tek bir bozuk/beklenmedik satır tüm sunucuyu düşürmesin
        # (savunma amaçlı; istek_isle zaten tip kontrolü yapıyor).
        try:
            yanit = istek_isle(istek)
        except Exception:  # noqa: BLE001
            continue
        if yanit is not None:
            sys.stdout.write(json.dumps(yanit, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
