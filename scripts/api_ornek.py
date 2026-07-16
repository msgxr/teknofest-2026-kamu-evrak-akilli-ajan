# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
API örnek istemcisi — EBYS entegrasyon demo betiği.

Çalışan API sunucusuna (varsayılan: http://127.0.0.1:8765) yalnızca
stdlib (urllib) ile bağlanır; bir EBYS'nin yapacağı gibi önce sağlık
kontrolü yapar, sonra örnek bir evrakı işletip özet/tür/birim bilgisini
Türkçe olarak ekrana basar. Ek olarak KVKK anonimleştirme ucunu dener.

Kullanım:
    # 1. terminal: sunucuyu başlat
    python3 -m src.api

    # 2. terminal: örnek istemciyi çalıştır
    python3 scripts/api_ornek.py
    python3 scripts/api_ornek.py --port 9000
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

# Demo için kurgu (tamamen sentetik) örnek evrak metni.
ORNEK_EVRAK = """T.C.
ÖRNEKKENT BELEDİYE BAŞKANLIĞI

Sayı: E-12345678-622.03-4567
Konu: Park aydınlatması hakkında

ÖRNEKKENT BELEDİYE BAŞKANLIĞINA

Mahallemizde bulunan Cumhuriyet Parkı'nın aydınlatma lambalarının
uzun süredir arızalı olduğunu, akşam saatlerinde parkın karanlık
kaldığını ve güvenlik sorunu oluşturduğunu bildirmek isterim.

Söz konusu aydınlatma sisteminin onarılması hususunda gereğini
arz ederim. 05.03.2026

Ayşe YILMAZ
Cumhuriyet Mah. Zambak Sok. No: 12
Örnekkent
Tel: 0532 111 22 33
"""


def _get(taban: str, yol: str) -> dict:
    """GET isteği atar ve JSON yanıtı döndürür."""
    with urllib.request.urlopen(taban + yol, timeout=30) as yanit:
        return json.loads(yanit.read().decode("utf-8"))


def _post(taban: str, yol: str, veri: dict) -> dict:
    """JSON gövdeli POST isteği atar ve JSON yanıtı döndürür."""
    govde = json.dumps(veri, ensure_ascii=False).encode("utf-8")
    istek = urllib.request.Request(
        taban + yol,
        data=govde,
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(istek, timeout=120) as yanit:
        return json.loads(yanit.read().decode("utf-8"))


def _http_hata_mesaji(exc: urllib.error.HTTPError) -> str:
    """Sunucunun HTTP hata yanıtındaki JSON 'hata' alanını okur; yoksa exc metni."""
    try:
        return str(json.loads(exc.read().decode("utf-8")).get("hata", exc))
    except Exception:
        return str(exc)


def _guvenli_post(taban: str, yol: str, veri: dict, baslik: str) -> dict | None:
    """POST çağrısını EBYS-dostu Türkçe hata mesajlarıyla korur.

    DÜZELTME: Eski akışta POST çağrıları try/except DIŞINDAYDI; sunucu 4xx/5xx
    dönerse urllib.error.HTTPError yakalanmayıp betik ham Python traceback ile
    çökerek entegrasyon demosunu bozuyordu. Artık HTTPError (önce; URLError alt
    sınıfıdır) ve URLError/OSError yakalanır, başarısızlıkta None döner.
    """
    try:
        return _post(taban, yol, veri)
    except urllib.error.HTTPError as exc:
        print(f"HATA: {baslik} başarısız (HTTP {exc.code}): {_http_hata_mesaji(exc)}")
    except (urllib.error.URLError, OSError) as exc:
        print(f"HATA: {baslik} — API sunucusuna ulaşılamadı ({exc}).")
    return None


def main() -> int:
    """Demo akışını çalıştırır: sağlık → evrak işleme → anonimleştirme."""
    parser = argparse.ArgumentParser(description="Kamu Evrak Ajan API örnek istemcisi")
    parser.add_argument("--host", default="127.0.0.1", help="API sunucu adresi")
    parser.add_argument("--port", type=int, default=8765, help="API sunucu portu")
    args = parser.parse_args()
    taban = f"http://{args.host}:{args.port}"

    print(f"API sunucusu: {taban}\n")

    # 1) Sağlık kontrolü — EBYS tarafında servis izleme adımına karşılık gelir
    try:
        saglik = _get(taban, "/saglik")
    except (urllib.error.URLError, OSError) as exc:
        print(f"HATA: API sunucusuna ulaşılamadı ({exc}).")
        print("Önce sunucuyu başlatın: python3 -m src.api")
        return 1

    print("[1] Sağlık kontrolü")
    print(f"    Durum       : {saglik.get('durum')}")
    print(f"    Sürüm       : {saglik.get('surum')}")
    print(f"    LLM backend : {saglik.get('llm_backend')}")
    print(f"    Ajan sayısı : {saglik.get('ajan_sayisi')}\n")

    # 2) Örnek evrakı uçtan uca işle — EBYS'nin gelen evrak kaydı senaryosu
    print("[2] Örnek evrak işleniyor (POST /evrak/isle)...")
    sonuc = _guvenli_post(taban, "/evrak/isle", {"metin": ORNEK_EVRAK, "mod": "full"}, "Evrak işleme")
    if sonuc is None:
        return 1

    siniflandirma = sonuc.get("siniflandirma", {})
    yonlendirme = sonuc.get("yonlendirme", {})
    print(f"    Evrak türü  : {siniflandirma.get('tur_adi')} "
          f"(güven: {siniflandirma.get('guven')})")
    print(f"    Önerilen birim: {yonlendirme.get('birim')} "
          f"(güven: {yonlendirme.get('guven')})")
    print(f"    Özet        : {sonuc.get('ozet', '')[:200]}")
    print(f"    İşlem süresi: {sonuc.get('islem_suresi_saniye')} sn\n")

    # 3) KVKK anonimleştirme — paylaşım/arşiv nüshası senaryosu
    print("[3] KVKK anonimleştirme (POST /evrak/anonimlestir)...")
    anonim = _guvenli_post(taban, "/evrak/anonimlestir", {"metin": ORNEK_EVRAK}, "Anonimleştirme")
    if anonim is None:
        return 1
    rapor = anonim.get("rapor", {})
    print(f"    Maskelenen unsur sayısı: {rapor.get('toplam')}")
    print(f"    Kategori dağılımı      : {rapor.get('maskelenen')}\n")

    print("Demo tamamlandı: API uçları EBYS tarafından aynı sözleşmeyle çağrılabilir.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
