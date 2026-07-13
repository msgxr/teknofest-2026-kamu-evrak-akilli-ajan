# Yayın Öncesi Kontrol Listesi (Public'e Çıkış)

Depo **herkese açık yapılmadan hemen önce** bu liste baştan sona işaretlenir.
Her komut repo kökünde çalıştırılır; ✅ olmayan tek madde varsa yayın ertelenir.

> Son tam denetim: 2026-07-11 — `docs/GUVENLIK_DENETIM_RAPORU.md`

## 1. Sır Taraması — Çalışma Kopyası

- [ ] Desen taraması temiz (eşleşmeler yalnızca değişken adı/örnek olmalı):

```bash
grep -rInE "(api[_-]?key|apikey|secret|token|passwd|password|Bearer |AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{30,}|AIza[0-9A-Za-z_\-]{30,}|xox[bap]-)" . \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules --exclude-dir=__pycache__
```

- [ ] Hassas dosya yok: `find . -name ".env" -o -name "*.pem" -o -name "*.key" -o -name "*.crt" -o -name "credentials*" -o -name "secrets.toml" | grep -v ".git/"` boş dönmeli (`.env.example` hariç).
- [ ] `detect-secrets scan --all-files` (kuruluysa) yeni bulgu vermiyor.

## 2. Sır Taraması — Git Geçmişi

- [ ] `gitleaks detect --source . -v` temiz (veya elle: `git log -p --all | grep -inE "api[_-]?key|secret|token|passw|BEGIN (RSA|OPENSSH)"` yalnızca kod tanımlayıcıları döndürüyor).
- [ ] Silinmiş şüpheli dosya yok: `git log --all --diff-filter=D --name-only | grep -iE "env|key|secret|credential"` boş.
- [ ] Yayınlanmayacak dal/tag/stash yok: `git branch -a && git tag && git stash list`.
- [ ] Yazar e-postaları bilinçli: `git log --all --format="%ae" | sort -u` — kişisel adres görünmesin isteniyorsa public ÖNCESİ `git filter-repo` ile noreply adresine çevrilir (geçmiş yeniden yazımı; takım kararı gerektirir).

## 3. Gerçek Veri / PII Taraması

- [ ] TCKN adayları yalnızca bilinen kurgu numaralar: `grep -rInE "\b[1-9][0-9]{10}\b" data/ docs/ presentations/` — her eşleşme `data/README.md` sentetiklik beyanı kapsamında olmalı.
- [ ] IBAN yok: `grep -rInE "TR[0-9]{2}[0-9 ]{20,30}" .` boş.
- [ ] Kişisel e-posta yok: `grep -rIn "@gmail\|@icloud\|@hotmail\|@outlook" --exclude-dir=.git .` boş.
- [ ] Mutlak yol/kullanıcı adı sızıntısı yok: `grep -rIn "C:\\\\Users\|/Users/\|/home/" data/processed/ docs/ presentations/` boş.
- [ ] `data/processed/eval_report*.json` içindeki `veri_dizini` alanları göreli yol.
- [ ] Depoya görsel/PDF evrak (ıslak imza/kaşe/antet görseli) eklenmemiş: `git ls-files | grep -E "\.(png|jpg|jpeg|tiff|pdf)$"` boş.
- [ ] Yeni eklenen ikili dosyalar (pptx/docx) metadata temiz (creator/lastModifiedBy alanlarında gerçek ad yok).

## 4. Bağımlılık ve Statik Analiz

- [ ] `pip-audit -r requirements.txt` kritik CVE göstermiyor (gösteriyorsa sürüm yükselt + testleri koş).
- [ ] `bandit -r src scripts -x tests` yüksek önemli bulgu vermiyor.

## 5. Yapılandırma

- [ ] `.gitignore` şunları kapsıyor: `.env*`, `logs/`, `*.log`, `data/chroma_db/`, `output/`, model dosyaları, `.streamlit/secrets.toml`.
- [ ] `.streamlit/config.toml` mevcut: `address="localhost"`, `maxUploadSize`, `showErrorDetails="none"`, `gatherUsageStats=false`.
- [ ] `.env` yerel dosyası commit'lenmemiş: `git ls-files | grep -x ".env"` boş.
- [ ] Ollama/yerel model endpoint'i localhost'ta; `0.0.0.0`'a açılmamış.

## 6. İşlevsellik (yarışma kuralı: demo zinciri bozulmamalı)

- [ ] `python -m pytest tests/ -q` → tümü geçiyor.
- [ ] `python scripts/evaluate.py --veri-dizini data/raw/kurgu_evraklar --rapor-dosyasi data/processed/eval_report.json` → metrikler önceki raporla tutarlı.
- [ ] `python demo/demo_scenario.py` uçtan uca hatasız.
- [ ] `streamlit run src/app.py` açılıyor; dosya yükle → sınıflandır → taslakla → yönlendir akışı çalışıyor.

## 7. Dokümantasyon

- [ ] `LICENSE` (Apache 2.0) kökte; `README.md` lisans beyanıyla tutarlı.
- [ ] `SECURITY.md` kökte ve bildirim kanalı güncel.
- [ ] `data/README.md` sentetiklik beyanları (TCKN, telefon, EBYS kodu, yer adları) güncel.
- [ ] `docs/model_bilgileri.md` üçüncü taraf modelleri bağlantı+sürüm+lisans ile listeliyor; depoya model ağırlığı eklenmemiş: `git ls-files | grep -E "\.(bin|pt|onnx|safetensors|gguf|h5)$"` boş.

## 8. Fikri Mülkiyet / Atıf

- [x] `LICENSE` telif satırı doğru özneyi taşıyor: **AGENTRA TECH — Şeyma Nur Çebi, Muhammed Sina Gün, Emine Elik, Zeynep Akel** (Apache-2.0 gövdesi değişmedi).
- [x] `NOTICE` kökte mevcut; 4 eser sahibini ve Apache-2.0 §4(d) atıf-koruma notunu içeriyor.
- [x] `AUTHORS` kökte mevcut; 4 eser sahibini (FSEK m.10) listeliyor.
- [x] `CITATION.cff` kökte mevcut; geçerli YAML, 4 yazar (GitHub "Cite this repository").
- [x] `README.md` ekip bölümü placeholder içermiyor; **AGENTRA TECH** + 4 isim yazılı.
- [x] `README.md` "Fikri Mülkiyet ve Katkı" bölümü eklendi (izin verici lisans, abartısız; §4/§5 atıfları).
- [x] `CONTRIBUTING.md` inbound = outbound (Apache-2.0 §5, DCO benzeri) notu var.
- [x] Tüm `src`, `tests`, `scripts`, `demo` altındaki `*.py` dosyaları SPDX başlığı taşıyor: `grep -rL "SPDX-License-Identifier" $(git ls-files '*.py')` boş.
- [x] Eski/tutarsız telif özneleri (`... Kamu Evrak Akıllı Ajan Takımı` [LICENSE], `Agentra Tech` [datasheet], `Teknofest 2026 Takımı` [pyproject.toml authors]) telif bağlamında kalmadı; hepsi AGENTRA TECH + 4 eser sahibine birleştirildi.
- [x] `pyproject.toml` `authors` alanı 4 gerçek eser sahibini listeliyor (paketleme metadatası atıfla tutarlı).
- [x] `CITATION.cff` sürüm/tarih depodaki gerçek değerle güncel (`0.4.0` / `2026-07-11`, CHANGELOG son yayın).
