"""
Yerli LLM Mini-Karşılaştırma Protokolü (P2-10).

Aynı tutulmuş set üzerinde iki (veya daha çok) yerel Ollama modelinin
eskalasyon kalitesini karşılaştırır. Bu betik bir ÖLÇÜM PROTOKOLÜDÜR:
GPU'lu/uygun bir makinede koşulur; rapora ve sunuma yalnızca bu betiğin
ürettiği sayılar (komut + tarihle) yazılabilir — koşulmadan hiçbir
karşılaştırma sayısı yazılamaz (dürüstlük kuralı).

Kurulum (ölçüm makinesinde):
    1) Ollama: https://ollama.com/download  (Windows: winget install Ollama.Ollama)
    2) Modeller:
       ollama pull qwen2.5:7b
       ollama pull hf.co/ytu-ce-cosmos/Turkish-Llama-8b-Instruct-v0.1-GGUF:Q4_K_M
       # (isteğe bağlı üçüncü aday) ollama pull hf.co/ytu-ce-cosmos/Turkish-Gemma-9b-T1-GGUF:Q4_K_M

Koşum:
    python scripts/llm_karsilastirma.py \
        --modeller "qwen2.5:7b,hf.co/ytu-ce-cosmos/Turkish-Llama-8b-Instruct-v0.1-GGUF:Q4_K_M" \
        --veri-dizini data/raw/kurgu_evraklar_heldout \
        --rapor-dosyasi data/processed/llm_karsilastirma.json

Ölçülenler (model başına, aynı evraklar):
    - llm_tur_dogrulugu: LLM'in TEK BAŞINA (kural katmanı olmadan)
      yapılandırılmış çıktıyla tür sınıflandırma doğruluğu — eskalasyon
      kalitesinin en doğrudan vekili
    - json_uyum_orani: yapılandırılmış (JSON) çıktı disiplinine uyum
    - ort/medyan gecikme (sn/evrak) — demo gerçek-zamanlılık etkisi

Not: Kural tabanlı çekirdeğin başarımı bu betikten bağımsızdır ve
scripts/evaluate.py ile ölçülür; buradaki karşılaştırma yalnızca
OPSİYONEL eskalasyon katmanı için model seçimini bilgilendirir.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJE_KOKU = Path(__file__).resolve().parent.parent
if str(PROJE_KOKU) not in sys.path:
    sys.path.insert(0, str(PROJE_KOKU))

GECERLI_TURLER = [
    "dilekce", "ust_yazi", "cevap_yazisi", "bilgilendirme",
    "tutanak", "rapor", "genelge", "onayli_belge", "diger",
]

SINIFLANDIRMA_PROMPTU = (
    "Aşağıdaki Türkçe resmî evrakın türünü belirle. Geçerli türler: "
    + ", ".join(GECERLI_TURLER)
    + ". Yalnızca JSON döndür.\n\nEVRAK:\n{metin}"
)
SEMA_IPUCU = '{"tur": "<geçerli türlerden biri>"}'


def hesapla_medyan(degerler: List[float]) -> float:
    """Saf Python medyan (boş listede 0.0)."""
    if not degerler:
        return 0.0
    s = sorted(degerler)
    n = len(s)
    return float(s[n // 2]) if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def model_olc(model: str, evraklar: List[dict]) -> Dict[str, Any]:
    """Tek modeli tüm evraklarda ölçer; sonuç sözlüğü döndürür."""
    from src.config import settings
    from src.models.llm_wrapper import LLMWrapper

    # Model seçimi: sarmalayıcı Ollama yolunda settings.llm.ollama_model
    # okur; betik süreci ölçüm sahibi olduğundan ayarı doğrudan ezer
    settings.llm.backend = "ollama"
    settings.llm.ollama_model = model
    llm = LLMWrapper()
    if llm.backend != "ollama" or not llm.is_available():
        return {
            "model": model,
            "durum": "ERISILEMEDI",
            "aciklama": (
                "Ollama erişilemiyor veya model yüklü değil; kurulum için "
                "betik docstring'ine bakın."
            ),
        }

    dogru = 0
    json_hata = 0
    gecikmeler: List[float] = []
    yanlislar: List[Dict[str, str]] = []

    for evrak in evraklar:
        baslangic = time.perf_counter()
        try:
            yanit = llm.generate_json(
                SINIFLANDIRMA_PROMPTU.format(metin=evrak["metin"][:1500]),
                schema_hint=SEMA_IPUCU,
                system_prompt=(
                    "Sen kamu evrak türlerine hâkim bir sınıflandırıcısın; "
                    "yalnızca istenen JSON'u üretirsin."
                ),
            )
            tahmin = str(yanit.get("tur", "")).strip()
        except Exception:
            json_hata += 1
            tahmin = ""
        gecikmeler.append(time.perf_counter() - baslangic)

        if tahmin == evrak["tur"]:
            dogru += 1
        else:
            yanlislar.append(
                {"dosya": evrak["dosya"], "beklenen": evrak["tur"], "tahmin": tahmin}
            )

    n = len(evraklar)
    return {
        "model": model,
        "durum": "OLCULDU",
        "evrak_sayisi": n,
        "llm_tur_dogrulugu": round(dogru / n, 4) if n else 0.0,
        "json_uyum_orani": round((n - json_hata) / n, 4) if n else 0.0,
        "ort_gecikme_sn": round(sum(gecikmeler) / n, 2) if n else 0.0,
        "medyan_gecikme_sn": round(hesapla_medyan(gecikmeler), 2),
        "yanlislar": yanlislar,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Yerli LLM eskalasyon kalitesi mini-karşılaştırması (P2-10)"
    )
    parser.add_argument(
        "--modeller", required=True,
        help="Virgülle ayrılmış Ollama model adları",
    )
    parser.add_argument(
        "--veri-dizini", default="data/raw/kurgu_evraklar_heldout",
        help="etiketler.json + .txt evrakları içeren dizin",
    )
    parser.add_argument(
        "--rapor-dosyasi", default="data/processed/llm_karsilastirma.json",
    )
    args = parser.parse_args(argv)

    veri_dizini = PROJE_KOKU / args.veri_dizini
    etiketler = json.loads(
        (veri_dizini / "etiketler.json").read_text(encoding="utf-8")
    )
    evraklar = [
        {
            "dosya": dosya,
            "tur": etiket.get("tur", "diger"),
            "metin": (veri_dizini / dosya).read_text(encoding="utf-8"),
        }
        for dosya, etiket in sorted(etiketler.items())
        if (veri_dizini / dosya).exists()
    ]

    sonuclar = []
    for model in [m.strip() for m in args.modeller.split(",") if m.strip()]:
        print(f"[{datetime.now():%H:%M:%S}] Ölçülüyor: {model} "
              f"({len(evraklar)} evrak)...")
        sonuclar.append(model_olc(model, evraklar))

    rapor = {
        "zaman_damgasi": datetime.now().isoformat(timespec="seconds"),
        "veri_dizini": args.veri_dizini,
        "protokol": "llm_karsilastirma.py — LLM-only tür sınıflandırma + "
                    "JSON uyumu + gecikme (eskalasyon kalitesi vekilleri)",
        "sonuclar": sonuclar,
    }
    rapor_yolu = PROJE_KOKU / args.rapor_dosyasi
    rapor_yolu.parent.mkdir(parents=True, exist_ok=True)
    rapor_yolu.write_text(
        json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(rapor, ensure_ascii=False, indent=2))
    print(f"\nRapor: {rapor_yolu}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
