# REST API Rehberi — EBYS Entegrasyonu

Kamu Evrak Akıllı Ajan sistemi, kurumların Elektronik Belge Yönetim
Sistemlerinden (EBYS) çağrılabilmesi için hafif bir REST API sunar.
API tamamen **Python standart kütüphanesiyle** (`http.server`) yazılmıştır;
hiçbir ek bağımlılık gerektirmez ve çevrimdışı (LLM'siz) ortamda da tam
çalışır.

## Başlatma

```bash
# Varsayılan: yalnızca yerel erişim, port 8765
python3 -m src.api

# Farklı port
python3 -m src.api --port 9000
```

Programatik kullanım:

```python
from src.api import calistir
calistir(host="127.0.0.1", port=8765)
```

Örnek istemci (sağlık kontrolü + evrak işleme + anonimleştirme demosu):

```bash
python3 scripts/api_ornek.py
```

## Genel Sözleşme

- Tüm istek ve yanıt gövdeleri **UTF-8 JSON**'dur.
- Hata yanıtları `{"hata": "<Türkçe açıklama>"}` biçimindedir ve sunucu içi
  ayrıntı (stack trace vb.) sızdırmaz.
- Durum kodları: `200` başarı, `400` geçersiz istek/JSON, `404` bilinmeyen
  uç, `411` Content-Length eksik, `413` gövde sınırı aşımı (1 MB),
  `500` sunucu hatası.

## Uçlar

### GET /saglik

Servis izleme/ayakta-mı kontrolü.

```bash
curl http://127.0.0.1:8765/saglik
```

```json
{
  "durum": "calisiyor",
  "surum": "0.1.0",
  "llm_backend": "offline",
  "ajan_sayisi": 11
}
```

`llm_backend` değeri `offline` ise sistem tamamen kural tabanlı çalışıyor
demektir; `openai`/`ollama` ise LLM destekli eskalasyon aktiftir. Her iki
durumda da uçlar aynı sözleşmeyle yanıt verir.

### POST /evrak/isle

Evrak metnini uçtan uca işler: sınıflandırma, bilgi çıkarımı, eksik bilgi
tespiti, mevzuat eşleştirme, önceliklendirme, özet, KVKK nüshası, resmî
yazı taslağı ve birim yönlendirme.

| Alan    | Tür    | Zorunlu | Açıklama                                        |
|---------|--------|---------|-------------------------------------------------|
| `metin` | string | evet    | Evrak düz metni (boş olamaz)                    |
| `mod`   | string | hayır   | `full` (varsayılan), `classify` veya `draft`    |

```bash
curl -X POST http://127.0.0.1:8765/evrak/isle \
  -H "Content-Type: application/json" \
  -d '{"metin": "ÖRNEKKENT KAYMAKAMLIĞINA\n\nMahallemizdeki sokak lambalarının arızalı olduğunu bilgilerinize sunar, gereğini arz ederim.", "mod": "full"}'
```

Yanıt, pipeline sonuç sözlüğünün tamamıdır (kısaltılmış örnek):

```json
{
  "siniflandirma": {"tur": "dilekce", "tur_adi": "Dilekçe", "guven": 0.92},
  "ozet": "…",
  "yonlendirme": {"birim": "Fen İşleri Müdürlüğü", "guven": 0.81},
  "yazi_taslagi": "…",
  "onceliklendirme": {"aciliyet": "normal"},
  "anonimlestirme": {"metin": "…", "rapor": {"toplam": 3}},
  "insan_onayi": {"gerekli": false, "gerekceler": []},
  "islem_suresi_saniye": 0.05
}
```

Python istemci örneği:

```python
import json, urllib.request

govde = json.dumps({"metin": evrak_metni, "mod": "full"},
                   ensure_ascii=False).encode("utf-8")
istek = urllib.request.Request(
    "http://127.0.0.1:8765/evrak/isle", data=govde, method="POST",
    headers={"Content-Type": "application/json; charset=utf-8"},
)
with urllib.request.urlopen(istek, timeout=120) as yanit:
    sonuc = json.loads(yanit.read().decode("utf-8"))
print(sonuc["siniflandirma"]["tur_adi"], "→", sonuc["yonlendirme"]["birim"])
```

### POST /evrak/anonimlestir

Yalnızca KVKK anonimleştirme çalıştırır: T.C. kimlik, telefon, e-posta,
IBAN, adres ve kişi adlarını format koruyarak maskeler. Evrakın kurum
dışıyla paylaşılacak/arşivlenecek nüshası için kullanılır.

```bash
curl -X POST http://127.0.0.1:8765/evrak/anonimlestir \
  -H "Content-Type: application/json" \
  -d '{"metin": "Başvuru sahibi: Ayşe YILMAZ, Tel: 0532 111 22 33"}'
```

```json
{
  "anonim_metin": "Başvuru sahibi: A*** Y***, Tel: 05** *** ** 33",
  "rapor": {
    "maskelenen": {"tc_kimlik": 0, "telefon": 1, "eposta": 0,
                    "iban": 0, "kisi_adi": 1, "adres": 0},
    "toplam": 2,
    "yontem": "kural_tabanli"
  }
}
```

### GET /birimler

Yönlendirme ajanının tanıdığı birim kataloğu (EBYS tarafında havale
listesi eşlemesi için).

```bash
curl http://127.0.0.1:8765/birimler
```

```json
{"birimler": [{"kod": "yazi_isleri", "ad": "Yazı İşleri Müdürlüğü",
               "aciklama": "Genel yazışma ve evrak yönetimi"}, "…"],
 "adet": 9}
```

### GET /evrak-turleri

Sınıflandırma ajanının tanıdığı evrak türü kataloğu.

```bash
curl http://127.0.0.1:8765/evrak-turleri
```

```json
{"evrak_turleri": [{"kod": "dilekce", "ad": "Dilekçe",
                     "aciklama": "Vatandaş veya kurumlardan gelen talep/şikayet belgesi"}, "…"],
 "adet": 9}
```

## EBYS Entegrasyon Senaryosu

Tipik bir kurum EBYS'sinde gelen evrak şu akışla sisteme bağlanır:

1. **Kayıt anında zenginleştirme:** EBYS, taranmış/aktarılmış evrak metnini
   `POST /evrak/isle` (mod: `classify`) ile gönderir; dönen tür, güven
   skoru ve özet, evrak kayıt formuna otomatik doldurulur. `insan_onayi.gerekli`
   alanı `true` ise kayıt memuru sonucu onaylamadan havale yapılmaz —
   düşük güvenli kararlar insan kontrolüne düşer.
2. **Havale önerisi:** `yonlendirme.birim` ve `yonlendirme.alternatifler`
   alanları EBYS'nin havale ekranında öneri olarak gösterilir; `GET /birimler`
   kataloğu, kurumun kendi birim kodlarıyla bir kez eşlenir.
3. **Cevap taslağı:** Memur onayladığında `mod: "draft"` (veya `full`)
   çağrısından dönen `yazi_taslagi`, EBYS'nin yazı editörüne başlangıç
   içeriği olarak aktarılır; imza/onay süreci EBYS'de kalır.
4. **Paylaşım nüshası:** Bilgi edinme/paylaşım taleplerinde
   `POST /evrak/anonimlestir` çıktısı kullanılarak KVKK'ya uygun nüsha
   üretilir.
5. **İzleme:** EBYS zamanlayıcısı `GET /saglik` ile servisi izler.

Servis durum tutmaz (stateless yanıt sözleşmesi): her istek kendi başına
tam sonucu döndürür, bu yüzden EBYS tarafında yeniden deneme (retry)
güvenlidir.

## Güvenlik Notları

- **Varsayılan bind adresi `127.0.0.1`'dir.** Servis ancak bilinçli bir
  kararla (`--host` parametresi) dışa açılmalıdır. Önerilen kurulum,
  EBYS sunucusuyla aynı makinede veya bir **ters proxy** (nginx/IIS ARR)
  arkasında çalıştırmaktır; TLS sonlandırma, kimlik doğrulama (ör. kurum
  içi API anahtarı/mTLS) ve hız sınırlama ters proxy katmanında yapılmalıdır.
- **Gövde sınırı 1 MB'dir:** aşan istekler belleğe alınmadan `413` ile
  reddedilir (kaynak tüketimi saldırılarına karşı, CWE-400).
- Evrak metni **200.000 karakterde** kırpılır (pipeline'ın merkezî girdi
  sınırı); aşırı uzun girdi analiz adımlarını süresiz meşgul edemez.
- Hata yanıtları iç ayrıntı sızdırmaz; ayrıntılar yalnızca sunucu
  loglarında (denetim izi) tutulur. Her istek kaynak IP ile loglanır.
- Evrak içerikleri kişisel veri taşıyabilir: sunucu loglarında evrak
  metni **yazılmaz**, yalnızca istek satırı ve durum kodu loglanır.
- İstemci soketleri 60 saniyelik zaman aşımıyla korunur (yavaş istemci /
  slowloris türü durumlar işleyiciyi süresiz kilitleyemez).
