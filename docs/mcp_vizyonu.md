# MCP Entegrasyon Vizyonu — EBYS'ler Sistemimizi "Araç" Olarak Çağırır

> **Dürüst kapsam beyanı:** Bu belge bir VİZYON ve İSKELET tanımıdır.
> Çalışan bir MCP sunucusu bu depoda İDDİA EDİLMEZ; aşağıdaki şemalar,
> mevcut sıfır-bağımlılıklı REST API'nin (`python -m src.api`) Model
> Context Protocol araçlarına nasıl birebir eşleneceğini gösterir.
> Amaç, ürünleşme yolunun mimari olarak hazır olduğunu kanıtlamaktır.

## Neden MCP?

**Model Context Protocol (MCP)** — Anthropic'in 2024'te açık standart
olarak yayımladığı, 2025'te fiilî sektör standardına dönüşen ajan-araç
birlikte çalışabilirlik protokolü. Google'ın A2A (Agent-to-Agent, 2025;
Linux Foundation) protokolüyle birlikte, ajan sistemlerinin birbirine
özel entegrasyon yazmadan konuşabildiği bir ekosistem kuruyor.

Kamu bağlamındaki karşılığı: **EBYS'ler ve kurum içi yapay zekâ
asistanları, bu sistemi özel entegrasyon geliştirmeden, standart
protokolle bir "araç" gibi çağırabilir.** Kurumun mevcut LLM asistanı
("kuruma gelen şu dilekçeyi işle ve taslak öner" komutuyla) arka planda
bizim analiz hattımızı MCP aracı olarak kullanır; sistemimiz karar
vermez, ÖNERİ döndürür (insan-döngüde ilke korunur).

## Mimari

```
┌──────────────────────────────┐        ┌──────────────────────────────────┐
│  Kurum Asistanı / EBYS       │  MCP   │  MCP Sunucu Katmanı (iskelet)    │
│  (MCP istemcisi: Claude,     │◄──────►│  - araç kayıtları (aşağıda)      │
│   kurum içi LLM, otomasyon)  │ stdio/ │  - kimlik doğrulama / KVKK filtre│
└──────────────────────────────┘  SSE   └───────────────┬──────────────────┘
                                                        │ HTTP (yerel ağ)
                                                        ▼
                                        ┌──────────────────────────────────┐
                                        │  Mevcut REST API (python -m      │
                                        │  src.api — sıfır bağımlılık)     │
                                        │  GET  /saglik /birimler          │
                                        │       /evrak-turleri             │
                                        │  POST /evrak/isle                │
                                        │       /evrak/anonimlestir        │
                                        └───────────────┬──────────────────┘
                                                        ▼
                                          11 uzman ajan + orkestratör
                                          (tamamen çevrimdışı çekirdek)
```

Tasarım ilkeleri:

1. **REST katmanı değişmez** — MCP sunucusu ince bir sarmalayıcıdır;
   çekirdek offline-first mimari hiçbir MCP bağımlılığı almaz.
2. **KVKK varsayılanı** — MCP üzerinden dışarı dönen metinler için
   varsayılan, anonimleştirilmiş nüshadır (`evrak_anonimlestir` aracı
   zincirin başında önerilir); ham metin ancak açık parametreyle döner.
3. **Öneri dili** — araç çıktıları "karar" değil "öneri/taslak"tır;
   `insan_onayi.gerekli` bayrağı MCP yanıtında aynen taşınır.

## Araç (Tool) Şeması Taslakları

MCP araç tanımı biçiminde (JSON Schema), REST uçlarıyla birebir eşleşme:

```json
{
  "name": "evrak_isle",
  "description": "Türkçe resmî evrakı uçtan uca işler: tür sınıflandırma, bilgi çıkarımı, eksik bilgi tespiti, madde-referanslı mevzuat önerisi, özet, resmî yazı taslağı, birim yönlendirme önerisi, öncelik/yasal süre ve taslak kalite puanı döndürür. Çıktılar ÖNERİDİR; insan_onayi.gerekli=true dönen sonuçlar insan kontrolü gerektirir.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "metin": {"type": "string", "description": "Evrakın düz metni (UTF-8)"},
      "mod": {"type": "string", "enum": ["full", "classify", "draft"], "default": "full"}
    },
    "required": ["metin"]
  }
}
```

```json
{
  "name": "evrak_anonimlestir",
  "description": "Evrak metnindeki kişisel verileri (T.C. kimlik no, ad-soyad, telefon, IBAN, adres) maskeleyerek KVKK paylaşım nüshası üretir. Kurum dışına/LLM'e gönderilecek metin için zincirin İLK aracı olarak kullanılması önerilir.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "metin": {"type": "string", "description": "Ham evrak metni"}
    },
    "required": ["metin"]
  }
}
```

```json
{
  "name": "birimleri_listele",
  "description": "Yönlendirme hedefi olabilecek kurum birimlerini (kod + ad) listeler. evrak_isle çıktısındaki birim_kodu değerlerinin sözlüğüdür.",
  "inputSchema": {"type": "object", "properties": {}}
}
```

```json
{
  "name": "evrak_turlerini_listele",
  "description": "Sistemin tanıdığı evrak türlerini (kod + ad) listeler (dilekçe, üst yazı, cevap yazısı, bilgilendirme, tutanak, rapor, genelge, onaylı belge).",
  "inputSchema": {"type": "object", "properties": {}}
}
```

```json
{
  "name": "sistem_sagligi",
  "description": "Sistem durumu: ajan sayısı, LLM backend'i (offline/ollama/openai-uyumlu), sürüm. İzleme ve devreye alma denetimleri için.",
  "inputSchema": {"type": "object", "properties": {}}
}
```

## Ürünleşme Yol Haritası

| Aşama | İş | Durum |
|---|---|---|
| 1 | Sıfır-bağımlılıklı REST API | ✅ depoda (`python -m src.api`) |
| 2 | MCP araç şemaları | ✅ bu belge |
| 3 | MCP sunucu sarmalayıcısı (resmî Python SDK ile ~200 satır; araçlar REST'e vekâlet eder) | Ürünleşme aşaması |
| 4 | Kurum kimlik doğrulaması + denetim izi eşlemesi (mevcut SQLite kayıt defteri MCP çağrılarını da loglar) | Ürünleşme aşaması |
| 5 | A2A değerlendirmesi (kurumlar arası ajan-ajan senaryoları) | Araştırma |

## Kaynaklar

- Model Context Protocol: https://modelcontextprotocol.io (Anthropic, 2024)
- A2A Protocol: https://github.com/a2aproject/A2A (Google → Linux Foundation, 2025)
- Bu depodaki REST API: `src/api.py` (uçlar: `/saglik`, `/birimler`,
  `/evrak-turleri`, `/evrak/isle`, `/evrak/anonimlestir`)
