"""Reflexion / Self-Refine yardımcıları — taslak öz-düzeltme döngüsü.

Format denetiminin YAPISAL çıktısını (başarısız kurallar) bir "sözlü eleştiri"ye
çevirir; bu eleştiri LLM'e geri verilerek taslak hedefli biçimde yeniden
yazdırılır (aktör → eleştirmen → yeniden üretim döngüsü). Aday havuzundan format
skoru en yüksek taslak seçilir (keep-best) — döngü taslak kalitesini ASLA
düşürmez; yalnızca iyileştirir veya aynı bırakır.

Şu an offline çekirdek için de güvenlidir: LLM yoksa döngü yalnızca kural
tabanlı adayı seçer (mevcut davranış birebir korunur).

Literatür: Reflexion (Shinn vd. 2023, NeurIPS, arXiv:2303.11366); Self-Refine
(Madaan vd. 2023, arXiv:2303.17651); CRITIC (Gou vd. 2023). Saf Python.
"""

from __future__ import annotations

from typing import Any, Dict


def yapisal_geri_bildirim(validation: Dict[str, Any], azami: int = 6) -> str:
    """Başarısız format kurallarını hedefli bir düzeltme notuna çevirir.

    Args:
        validation: `_validate_format` çıktısı — {"kontroller": [{kural_id,
            kural, durum, detay, ...}]}. durum=False olan kurallar düzeltme
            gerektirir.
        azami: En fazla kaç kuralın nota alınacağı.

    Returns:
        Düzeltme notu (LLM'e verilecek); düzeltilecek bir şey yoksa boş string.
    """
    basarisiz = [
        k for k in validation.get("kontroller", []) if not k.get("durum", True)
    ]
    if not basarisiz:
        return ""
    satirlar = []
    for k in basarisiz[:azami]:
        detay = (k.get("detay") or "").strip()
        parca = f"- {k.get('kural', k.get('kural_id', ''))}"
        if detay:
            parca += f" — {detay}"
        satirlar.append(parca)
    return (
        "Bir önceki taslakta aşağıdaki resmî yazışma kuralları eksik/hatalıydı; "
        "yeni taslakta bunları MUTLAKA düzelt:\n" + "\n".join(satirlar)
    )
