#!/usr/bin/env python
"""loopkit PostToolUse hook — düzenlenen Python dosyasını `ruff format` ile biçimlendirir.

loopkit'in prettier hook'unun Python karşılığı ("okunabilir diff'ler" ilkesi). Yalnızca
DÜZENLENEN tek `.py` dosyasına dokunur; projenin ruff yapılandırması (pyproject.toml,
line-length=100) kullanılır. Asla düzenlemeyi başarısız kılmaz (her hata sessizce yutulur).

Bu betik settings.json'a elle bağlanmadıkça çalışmaz — bkz. docs/loopkit_kurulum.md.
Girdi: stdin'den JSON (Claude Code PostToolUse yükü).
"""
import json
import shutil
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # Yük okunamadı — sessiz geç.

    path = (payload.get("tool_input") or {}).get("file_path", "")
    if not path or not path.endswith(".py"):
        return 0  # Yalnız Python dosyaları.

    ruff = shutil.which("ruff")
    if not ruff:
        return 0  # ruff yoksa no-op (offline-first: zorunlu bağımlılık değil).

    try:
        subprocess.run([ruff, "format", "--quiet", path], timeout=30, check=False)
    except Exception:
        pass  # Biçimlendirme asla düzenlemeyi bloklamaz.
    return 0


if __name__ == "__main__":
    sys.exit(main())
