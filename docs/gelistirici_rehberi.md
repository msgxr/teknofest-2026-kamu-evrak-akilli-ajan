# Geliştirici Rehberi — Mimarinin Genişletilmesi

Bu rehber, sisteme **yeni bir ajan**, **yeni bir evrak türü**, **yeni bir
birim**, **yeni bir mevzuat belgesi** veya **yeni bir API ucu** eklemek
isteyen geliştiriciler içindir. Tüm referanslar gerçek dosya ve satır
numaralarına işaret eder (satır numaraları bu rehberin yazıldığı andaki
duruma göredir; küçük kaymalar olabilir — sembol adları kalıcı çapadır).

Genel üslup/katkı kuralları için [../CONTRIBUTING.md](../CONTRIBUTING.md),
mimarinin kuş bakışı anlatımı için [teknik_rapor.md](teknik_rapor.md)
dosyalarına bakınız.

---

## 0. Mimarinin 60 Saniyelik Özeti

- **Orkestratör** (`src/agents/orchestrator.py`) 11 uzman ajanı, paylaşılan
  bir `AgentState` veri sınıfı (satır 55) üzerinde sırayla çalıştırır;
  akış üç koşullu kapıya sahiptir (okunabilirlik / dil / düşük güven).
- Her ajan tek bir sözleşmeye uyar: `run(self, state: "AgentState") ->
  "AgentState"` — girdiyi `state`'ten okur, sonucunu `state`'e yazar.
- `_run_step()` (orchestrator.py satır 484) her adımın süresini ölçer ve
  hatayı yutup `state.errors`'a kaydeder: **bir ajanın çökmesi boru hattını
  durdurmaz**.
- `_compile_results()` (orchestrator.py satır 522) `state`'i, dış dünyaya
  verilen Türkçe anahtarlı sonuç sözlüğüne çevirir.
- Girişler: CLI (`src/main.py`), Streamlit (`src/app.py`), REST API
  (`src/api.py`) ve `EndToEndPipeline` (`src/pipelines/end_to_end_pipeline.py`).

---

## 1. Yeni Bir Ajan Nasıl Eklenir (adım adım)

Örnek: evrak metninden yazım/imla puanı üreten kurgusal bir
`ImlaDenetimAgent`.

### Adım 1 — Ajan sınıfı iskeleti

Yeni dosya: `src/agents/imla_denetim_agent.py`. Mevcut ajanlarla aynı kalıbı
kullanın (kısa bir örnek için `src/agents/summarization_agent.py`, zengin
docstring geleneği için `src/agents/triage_agent.py` iyi şablonlardır):

```python
"""
İmla Denetim Agent — evrak metninde yazım denetimi. (Ne yaptığını,
hangi İLKESEL kurala dayandığını ve şartnamenin hangi maddesini
karşıladığını Türkçe açıklayın.)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.orchestrator import AgentState

logger = logging.getLogger("kamu_evrak_ajan.imla_denetim")


class ImlaDenetimAgent:
    """Evrak metninde imla denetimi yapan ajan."""

    def __init__(self) -> None:
        logger.info("İmla Denetim Agent başlatıldı.")

    def run(self, state: "AgentState") -> "AgentState":
        """Metni denetler ve sonucu state.imla_denetimi alanına yazar."""
        metin = state.raw_text
        # ... kural tabanlı analiz ...
        state.imla_denetimi = {"skor": 1.0, "bulgular": []}
        return state
```

Kurallar: Türkçe docstring/yorum, `from __future__ import annotations`
(py39 uyumu), `logging.getLogger("kamu_evrak_ajan.<ad>")` logger deseni,
yalnızca stdlib (+ mevcut çekirdek bağımlılıklar). Ajan **exception
fırlatabilir**; orkestratör bunu adım kaydına işler.

### Adım 2 — `AgentState` alanı

`src/agents/orchestrator.py` satır 55–105'teki `AgentState` dataclass'ına,
ilgili görev bloğunun altına varsayılanlı bir alan ekleyin (mutable
varsayılanlar için `field(default_factory=...)` zorunludur):

```python
imla_denetimi: dict = field(default_factory=dict)
```

### Adım 3 — Orkestratöre kayıt

Aynı dosyada üç nokta:

1. `_load_agents()` (satır 125): import + `self.agents` sözlüğüne
   (satır 139–151) `"imla_denetim": ImlaDenetimAgent(),` girdisi.
2. `_run_workflow()` (satır 217): akışta doğru yere
   `self._run_step("imla_denetim", "İmla denetimi")` çağrısı. Koşullu
   kapılara saygı gösterin — içerik analizi ajanları yalnızca
   `metin_okunabilir` iken çalışmalıdır (Görev 1 bloğu, satır 230–241
   civarı, bunun örneğidir).
3. `_compile_results()` (satır 522): sonuç sözlüğüne Türkçe anahtar:
   `"imla_denetimi": self.state.imla_denetimi,`. Sonuç sözlüğü dış API'nin
   parçasıdır; anahtar eklemek geriye uyumludur, anahtar adı değiştirmek
   kırıcıdır.

### Adım 4 — Test

Yeni dosya: `tests/test_imla_denetim.py`. Mevcut gelenek: sınıf bazlı
gruplama + Türkçe test adları (örnek: `tests/test_triage.py`). En az üç
düzeyde test yazın:

```python
class TestImlaDenetimAgent:
    def test_temiz_metin_tam_puan(self): ...     # birim: ajan tek başına
    def test_bos_metin_cokmez(self): ...         # sınır durumu

class TestOrkestratorEntegrasyonu:
    def test_sonuc_sozlugunde_alan_var(self):    # uçtan uca
        sonuc = OrchestratorAgent().process_text("...")
        assert "imla_denetimi" in sonuc
```

Çalıştırma: `pytest tests/test_imla_denetim.py -q`, sonra tüm paket:
`pytest tests/ -q`.

### Adım 5 — Uyum matrisi ve dokümantasyon

- `docs/sartname_uyum_matrisi.md`: ajanın karşıladığı şartname
  gereksinimine kanıt satırı ekleyin (tablo biçimi: gereksinim | kanıt
  dosyası | durum).
- README'deki özellik tablosuna ve ajan sayısına dokunuyorsanız sayıyı
  güncelleyin (11 → 12); `docs/teknik_rapor.md` mimari bölümünü hizalayın.
- Sonuç alanını kullanıcıya göstermek için `src/app.py` içinde ilgili
  sekmeye (sekmeler satır 1376–1378'de kurulur) bir gösterim bloğu
  ekleyebilirsiniz — zorunlu değildir, sonuç sözlüğünde alan zaten döner.

---

## 2. Yeni Bir Evrak Türü Ekleme

Örnek: "davet yazısı" türü.

1. **Sınıflandırma**: `src/agents/classification_agent.py` satır 46'daki
   `EVRAK_TURLERI` sözlüğüne yeni anahtar ekleyin (`ad`, anahtar kelime /
   yapısal sinyal tanımları mevcut girdilerle aynı şemada). Tür anahtarı
   (ör. `davet_yazisi`) sistem genelinde kimliktir.
2. **Zorunlu alanlar**: `src/agents/missing_info_agent.py` satır 61'deki
   `ZORUNLU_ALANLAR` sözlüğüne türe özgü alan listesi ekleyin; tür
   tanımsızsa `diger` varsayılanı kullanılır (satır 199).
3. **Usul mevzuatı (opsiyonel)**: tür belirli bir usul mevzuatına tabiyse
   `src/agents/legislation_agent.py` satır 41'deki `TUR_USUL_MEVZUATI`
   ve satır 70'teki `TUR_MEVZUAT_AGIRLIKLARI` tablolarına doc_id ekleyin.
4. **Taslak şablonu (opsiyonel)**: türe özel resmî yazı taslağı
   gerekiyorsa `src/templates/` altına şablon ekleyip
   `src/agents/draft_writer_agent.py` içindeki tür → şablon seçimini
   genişletin.
5. **Veri + etiket**: `data/raw/kurgu_evraklar/` altına 2–3 **kurgu**
   örnek ekleyin ve `etiketler.json`'a
   `{"tur", "birim_kodu", "eksik_alanlar", "aciklama"}` şemasıyla
   etiketleyin (gerçek kişisel veri ASLA kullanılmaz). Held-out setlere
   dokunmayın (bkz. CONTRIBUTING §5).
6. **Test + ölçüm**: sınıflandırma testi ekleyin
   (`tests/test_classification.py` geleneğinde) ve geliştirme seti
   ölçümünü yenileyin: `python scripts/evaluate.py`.
7. **ML ensemble notu**: istatistiksel sınıflandırıcı
   (`src/models/istatistiksel_siniflandirici.py`) etiketli veriden
   `scripts/ml_egit.py` ile eğitilir; yeni tür örnekleri eklendiyse modeli
   yeniden eğitip `data/processed/ml_model.json`'u güncelleyin.

## 3. Yeni Bir Birim Ekleme

1. `src/agents/routing_agent.py` satır 42'deki `BIRIMLER` sözlüğüne yeni
   birim anahtarı ekleyin (mevcut girdilerle aynı şema: `ad` + sinyal
   listeleri). Anahtar (ör. `cevre_koruma`), etiketlerdeki `birim_kodu`
   değeriyle birebir aynıdır.
2. Yönlendirme sinyallerini İLKESEL yazın: birimin gerçek görev alanının
   söz dağarcığı — belirli bir test dosyasına özel ezber değil.
3. REST API'deki `GET /birimler` kataloğu (`src/api.py` satır 147,
   `_birim_katalogu`) `BIRIMLER`'den otomatik beslenir; ek iş gerekmez.
4. Test: `tests/` altında ilgili yönlendirme testine yeni birim için
   olumlu/olumsuz örnek ekleyin; `python scripts/evaluate.py` ile
   yönlendirme doğruluğunun gerilemediğini doğrulayın.

## 4. Yeni Bir Mevzuat Belgesi Ekleme

Korpus `data/raw/mevzuat_metinleri/*.txt` dosyalarından oluşur ve
`LegislationAgent._ensure_index()` (`src/agents/legislation_agent.py`
satır 214) tarafından otomatik yüklenir — **dosyayı doğru formatta koymak
yeterlidir**, kod değişikliği gerekmez:

1. Dosya adı = doc_id: `ornek_kanun_1234.txt` (küçük harf, alt çizgi).
2. Dosya formatı (`_parse_corpus_file`, satır 251):

   ```
   # Başlık: <resmî ad>
   # Kaynak: <kaynak, ör. mevzuat.gov.tr bağlantısı>
   # Anahtar-Kelimeler: <virgülle ayrılmış liste>

   ## <bölüm başlığı, ör. Madde 7 — Cevap süresi>
   <2–5 cümlelik bölüm metni>

   ## <sonraki bölüm>
   ...
   ```

3. Yalnızca **kamuya açık** mevzuat metni/özeti kullanın; kaynak satırı
   zorunlu şeffaflık kanıtıdır (`data/README.md` geleneği).
4. (Opsiyonel) Belge belirli türler için usul mevzuatıysa veya bir alan
   temasına aitse `TUR_MEVZUAT_AGIRLIKLARI` (satır 70) / `MEVZUAT_TEMALARI`
   (satır 94) tablolarına doc_id ekleyin — modül yorumunda belirtildiği
   gibi yeni dosya için yalnızca bu tablo kayıtları yeterlidir.
5. Dikkat: korpus **sınıf düzeyinde önbelleğe** alınır (satır 200–202,
   `_chunks`/`_bm25`); değişikliğin görünmesi için süreci (Streamlit/API)
   yeniden başlatın.
6. Test: `pytest tests/test_end_to_end.py -q` yeşil kalmalı; belgeyi
   hedefleyen bir sorguyla `LegislationAgent`'ın önerisini doğrulayan
   küçük bir test eklemek iyi pratiktir.

## 5. Yeni Bir API Ucu Ekleme

REST API (`src/api.py`) stdlib `http.server` üzerine kuruludur; framework
yoktur:

1. **GET ucu**: `do_GET()` (satır 288) içindeki `if/elif` zincirine yeni
   yol ekleyin; yanıtı `self._json_yanit(200, sozluk)` (satır 192) ile
   döndürün. Veri üreten mantığı, üstteki modül düzeyi yardımcılar gibi
   (`_saglik_bilgisi` satır 91, `_birim_katalogu` satır 147) ayrı bir
   fonksiyona koyun — import'ları tembel (fonksiyon içinde) yapın ki
   sunucu açılışı hafif kalsın.
2. **POST ucu**: `do_POST()` (satır 304) başındaki izinli yol demetine
   (`("/evrak/isle", "/evrak/anonimlestir")`) yolu ekleyin; gövde okuma
   için mevcut `_json_govde()` / `_metin_al()` yardımcılarını kullanın
   (boyut sınırı ve hata yanıtları oradan hazır gelir).
3. **Güvenlik gelenekleri**: iç hata ayrıntısı yanıta sızdırılmaz
   (`_hata_yanit(500, ...)` + log), bilinmeyen uçta gövde sınırlı tüketilir,
   girdi uzunluk sınırları korunur.
4. **Test**: `tests/test_api.py` sunucuyu `sunucu_olustur(port=0)`
   (satır 354) ile ayrı thread'de kaldırır; yeni uç için aynı desenle
   olumlu + olumsuz (404/400) test ekleyin.
5. **Dokümantasyon**: `docs/api_rehberi.md`'ye ucun istek/yanıt örneğini
   ekleyin.

---

## 6. Teslim Öncesi Kalite Kapıları (her genişletme için)

```bash
python -m compileall -q src scripts   # sözdizimi / py39 uyumu
pytest tests/ -q                      # tüm testler yeşil
python scripts/evaluate.py            # geliştirme seti metrikleri gerilemedi
```

Aynı denetimler CI'da (`.github/workflows/ci.yml`) Python 3.9 ve 3.12
üzerinde otomatik koşar. Held-out setler nihai ölçüm içindir; onlara
bakarak geliştirme yapmayın (bkz. `CONTRIBUTING.md` §5).
