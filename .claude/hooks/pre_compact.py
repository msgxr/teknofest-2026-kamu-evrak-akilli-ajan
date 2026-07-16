#!/usr/bin/env python
"""loopkit PreCompact hook — bağlam sıkıştırılmadan önce yüksek-sinyal kararları çıkarır.

Sıkıştırma (compaction) düz metin muhakemeyi yok eder. Kararlar (X seçildi, Y reddedildi,
denendi ve başarısız, A'dan B'ye geçildi), yeni bir taze-bağlam oturumunun "neden"i yeniden
türetmeden yeniden yükleyebilmesi için yapılandırılmış biçimde saklanmaya değer parçadır.

loopkit'in bash+jq sürümünün Python portu (bu makinede jq yok). Karar örüntüleri Türkçe +
İngilizce olarak eşleştirilir. Çıktı: proje kökünde ./claude-decisions.json.

Bu betik settings.json'a elle bağlanmadıkça çalışmaz — bkz. docs/loopkit_kurulum.md.
Girdi: stdin'den JSON (transcript_path + cwd). Asla sıkıştırmayı bloklamaz.
"""
import json
import os
import re
import sys

# Karar örüntüleri (TR + EN).
PATTERN = re.compile(
    r"(karar\w*|seçildi|seçtim|reddedildi|denendi ve başarısız|"
    r"vazgeçildi|geçildi|yerine|decided|chose|rejected|tried and failed|"
    r"switched from .* to|going with|not going to)",
    re.IGNORECASE,
)


def extract_from_transcript(path: str) -> list[str]:
    """JSONL transcript'ten asistan metinlerini okuyup karar cümlelerini süz."""
    hits: list[str] = []
    seen: set[str] = set()
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if rec.get("type") != "assistant":
                    continue
                content = (rec.get("message") or {}).get("content") or []
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "text":
                        continue
                    for sentence in re.split(r"(?<=[.!?])\s+", block.get("text", "")):
                        s = sentence.strip()
                        if 20 < len(s) < 400 and PATTERN.search(s) and s not in seen:
                            seen.add(s)
                            hits.append(s)
                            if len(hits) >= 20:
                                return hits
    except Exception:
        pass
    return hits


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}

    transcript = payload.get("transcript_path", "")
    cwd = payload.get("cwd") or os.getcwd()
    if not transcript or not os.path.isfile(transcript):
        return 0

    hits = extract_from_transcript(transcript)
    if not hits:
        return 0

    out = os.path.join(cwd, "claude-decisions.json")
    existing: list = []
    if os.path.isfile(out):
        try:
            with open(out, encoding="utf-8") as fh:
                existing = json.load(fh)
                if not isinstance(existing, list):
                    existing = []
        except Exception:
            existing = []

    # Zaman damgası ScheduleWakeup/harici değil; PreCompact yükünde yoksa alan atlanır.
    ts = payload.get("timestamp", "")
    existing.extend({"ts": ts, "decision": h} for h in hits)

    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(existing, fh, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
