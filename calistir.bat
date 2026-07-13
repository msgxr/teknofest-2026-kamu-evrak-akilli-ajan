@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

echo ============================================================
echo   Kamu Evrak Akilli Ajan - Arayuz Baslatici
echo ============================================================
echo.

REM 1) Python kurulu mu? (Microsoft Store kisayolu gercek Python DEGILDIR)
python --version >nul 2>nul
if errorlevel 1 (
  echo [HATA] Python bulunamadi ^(veya yalnizca Microsoft Store kisayolu var^).
  echo.
  echo Cozum: once Python 3.10+ kurun ^-^>
  echo   https://www.python.org/downloads/windows/
  echo   Kurulum sihirbazinda "Add python.exe to PATH" kutusunu ISARETLEYIN.
  echo.
  echo Python'u kurduktan sonra bu dosyayi tekrar calistirin.
  pause
  exit /b 1
)

REM 2) Sanal ortam (.venv) yoksa olustur
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Sanal ortam olusturuluyor ^(.venv^)...
  python -m venv .venv
  if errorlevel 1 ( echo [HATA] Sanal ortam olusturulamadi. & pause & exit /b 1 )
)

REM 3) Bagimliliklari kur (streamlit, pypdf, ...)
echo [2/3] Bagimliliklar kuruluyor... ^(ilk calistirmada birkac dakika surebilir^)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
pip install -r requirements.txt
if errorlevel 1 ( echo [HATA] Bagimliliklar kurulamadi. & pause & exit /b 1 )

REM 4) Arayuzu baslat
echo.
echo [3/3] Arayuz baslatiliyor...
echo    Adres: http://localhost:8501  ^(tarayicida otomatik acilir^)
echo    Durdurmak icin: bu pencerede Ctrl+C
echo.
streamlit run src\app.py

pause
