#!/usr/bin/env bash
# ============================================================
# Kamu Evrak Akıllı Ajan Sistemi — tek komut başlatma
#
# Kullanım:
#   ./baslat.sh          # Streamlit web arayüzünü başlatır (port 8501)
#   ./baslat.sh --api    # REST API'yi başlatır (port 8765)
#   ./baslat.sh --help   # yardım
#
# Sistem offline-first'tür: LLM/İnternet olmadan da tam çalışır.
# ============================================================
set -euo pipefail

# Depo köküne geç (betik nereden çağrılırsa çağrılsın çalışsın)
cd "$(dirname "$0")"

MOD="web"
case "${1:-}" in
    --api)  MOD="api" ;;
    --help|-h)
        sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'
        exit 0
        ;;
    "") ;;
    *)
        echo "HATA: bilinmeyen seçenek: $1 (geçerli: --api, --help)" >&2
        exit 2
        ;;
esac

# --- Python kontrolü -------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "HATA: python3 bulunamadı. Python 3.9+ kurulu olmalıdır." >&2
    exit 1
fi

# --- Sanal ortam kontrolü (uyarı; zorlamaz) --------------------------
if [ -z "${VIRTUAL_ENV:-}" ]; then
    if [ -f "venv/bin/activate" ]; then
        echo "Bilgi: depodaki 'venv/' sanal ortamı etkinleştiriliyor..."
        # shellcheck disable=SC1091
        . venv/bin/activate
    elif [ -f ".venv/bin/activate" ]; then
        echo "Bilgi: depodaki '.venv/' sanal ortamı etkinleştiriliyor..."
        # shellcheck disable=SC1091
        . .venv/bin/activate
    else
        echo "UYARI: Etkin bir sanal ortam yok ve depoda venv/ bulunamadı."
        echo "       Sistem paketlerine kurulum yapmamak için önerilen:"
        echo "         python3 -m venv venv && source venv/bin/activate"
        echo "         pip install -r requirements.txt"
        echo "       Devam ediliyor (mevcut Python ortamı kullanılacak)..."
    fi
fi

# --- Bağımlılık kontrolü ---------------------------------------------
# Çekirdek bağımlılıklar eksikse kullanıcıya tek komutluk çözüm gösterilir.
if ! python3 -c "import pydantic, rich" >/dev/null 2>&1; then
    echo "HATA: çekirdek bağımlılıklar eksik görünüyor." >&2
    echo "      Kurulum: pip install -r requirements.txt" >&2
    exit 1
fi
if [ "$MOD" = "web" ] && ! python3 -c "import streamlit" >/dev/null 2>&1; then
    echo "HATA: streamlit kurulu değil (web arayüzü için gerekli)." >&2
    echo "      Kurulum: pip install -r requirements.txt" >&2
    echo "      Alternatif: './baslat.sh --api' (API streamlit gerektirmez)" >&2
    exit 1
fi

# --- Başlat -----------------------------------------------------------
if [ "$MOD" = "api" ]; then
    echo "REST API başlatılıyor: http://127.0.0.1:8765 (durdurmak için Ctrl+C)"
    exec python3 -m src.api
else
    echo "Streamlit web arayüzü başlatılıyor: http://localhost:8501 (durdurmak için Ctrl+C)"
    exec python3 -m streamlit run src/app.py
fi
