# ============================================================
# Kamu Evrak Akıllı Ajan Sistemi — Container imaj tanımı
#
# NOT (dürüstlük): Hazır bir container imajı YAYINLANMAZ; bu
# Dockerfile sağlanır ve imaj kullanıcı tarafından derlenir.
#
# Derleme:   docker build -t kamu-evrak-ajan .
# Web (UI):  docker run --rm -p 8501:8501 kamu-evrak-ajan
# REST API:  docker run --rm -p 8765:8765 kamu-evrak-ajan \
#              python -m src.api --host 0.0.0.0 --port 8765
#
# Sistem offline-first'tür: imaj içinde LLM/İnternet olmadan tam
# işlevli çalışır (yalnızca çekirdek bağımlılıklar kurulur).
# ============================================================

FROM python:3.12-slim

# Derleme artığı .pyc üretme, çıktıyı tamponlama, pip önbelleği tutma
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Önce yalnızca bağımlılık dosyası: kod değişikliklerinde bu katman
# önbellekten gelir (hızlı yeniden derleme)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Uygulama kaynakları (.dockerignore gereksiz dosyaları dışarıda tutar)
COPY . .

# GÜVENLİK: root olmayan kullanıcıyla çalıştır; kayıt defteri (SQLite)
# data/processed/ altına yazabildiğinden dizin sahipliği devredilir
RUN useradd --create-home --uid 1000 ajan \
    && chown -R ajan:ajan /app
USER ajan

# 8501: Streamlit web arayüzü, 8765: REST API (python -m src.api)
EXPOSE 8501 8765

# Sağlık denetimi: Streamlit'in kendi sağlık ucu (stdlib ile, curl gerekmez)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)" || exit 1

# Varsayılan: Streamlit web arayüzü (container dışından erişim için 0.0.0.0)
CMD ["streamlit", "run", "src/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0", \
     "--server.headless=true", "--browser.gatherUsageStats=false"]
