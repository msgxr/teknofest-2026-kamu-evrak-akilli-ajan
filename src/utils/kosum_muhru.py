# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""Tekrarlanabilirlik mührü — her rapora makine-okunur köken (provenance) damgası.

Her değerlendirme/benchmark raporuna: git commit SHA + kirli-çalışma bayrağı,
Python/platform sürümü, `requirements.txt` sha256 özeti ve DEĞERLENDİRİLEN SETİN
içerik hash'i (sıralı .txt + etiketler.json sha256) gömer. Böylece "her sayı
hangi kod + hangi veri durumundan üretildi KANITLANABİLİR" olur — NeurIPS
tekrarlanabilirlik standardı; jürinin sonuç-manipülasyonu endişesini kapatır.

Yalnızca stdlib (hashlib, subprocess, platform, sys). git yoksa (ör. tarball)
"bilinmiyor"a zarifçe düşer. Mutlak yol SIZMAZ (yalnızca ad + kısa hash).
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _git_durumu(proje_koku: Path) -> Tuple[Optional[str], Optional[bool]]:
    """(commit_sha, calisma_agaci_kirli). git yoksa (None, None)."""
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(proje_koku),
            capture_output=True, text=True, timeout=5,
        )
        if sha.returncode != 0:
            return None, None
        kirli = subprocess.run(
            ["git", "status", "--porcelain"], cwd=str(proje_koku),
            capture_output=True, text=True, timeout=5,
        )
        return sha.stdout.strip(), bool(kirli.stdout.strip())
    except Exception:
        return None, None


def _dosya_hash(yol: Path) -> str:
    return hashlib.sha256(yol.read_bytes()).hexdigest()[:16]


def set_icerik_hash(veri_dizini: Path) -> str:
    """Değerlendirme setinin içerik hash'i: sıralı .txt adları+içerikleri +
    etiketler.json. Set değişirse hash değişir (veri provenansı)."""
    d = Path(veri_dizini)
    h = hashlib.sha256()
    for yol in sorted(d.glob("*.txt")):
        h.update(yol.name.encode("utf-8"))
        h.update(yol.read_bytes())
    etiket = d / "etiketler.json"
    if etiket.exists():
        h.update(etiket.read_bytes())
    return h.hexdigest()[:16]


def kosum_muhru(
    proje_koku: Path, veri_dizini: Optional[Path] = None
) -> Dict[str, Any]:
    """Bir rapora gömülecek tekrarlanabilirlik mührünü üretir."""
    sha, kirli = _git_durumu(Path(proje_koku))
    req = Path(proje_koku) / "requirements.txt"
    muhur: Dict[str, Any] = {
        "git_commit": sha or "bilinmiyor",
        "calisma_agaci_kirli": kirli if sha is not None else None,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "requirements_sha256": _dosya_hash(req) if req.exists() else None,
    }
    if veri_dizini is not None:
        muhur["set_icerik_hash"] = set_icerik_hash(Path(veri_dizini))
    return muhur
