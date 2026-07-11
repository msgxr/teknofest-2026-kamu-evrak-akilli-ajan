# Adillik Beyanı

**Şartname referansı (m13 / Etik Kurallar — Adillik):** "sistemler Türkçe
konuşan tüm bireyler için adil, kapsayıcı ve yanlılıktan arındırılmış olmalı"
(TEKNOFEST 2026 TYDA Senaryo 1 şartnamesi; bkz.
`docs/yarisma_resmi_kaynak_rehberi.md` §5).

## İlke

Sistemin **karar çıktıları** — evrak türü sınıflandırması, birim
yönlendirmesi, öncelik düzeyi ve eksik bilgi tespiti — başvuranın
kimliğinden (ad-soyad, cinsiyet çağrışımı, yaşadığı il/bölge çağrışımı)
bağımsız olmalıdır. Kimlik bilgileri evrakta **veri olarak taşınır**
(bilgi çıkarımı bu alanları çıkarır, KVKK ajanı maskeler); ancak hiçbir
**karar** bu alanlara dayanmaz.

## Karar girdilerinde kimlik özellikleri sinyal değildir

- **Kural tabanlı bileşenler** (sınıflandırma kuralları, birim yönlendirme,
  öncelik/triage, eksik bilgi tespiti): tamamı içerik ve yapı temellidir —
  hitap satırı, konu/talep kalıpları, alan başlıkları (Tarih, Adres,
  T.C. Kimlik No vb.) ve aciliyet/yasal süre ifadeleri gibi sinyaller
  kullanılır. Kural sözlüklerinde kişi adı, cinsiyet veya il/bölge adına
  bağlı hiçbir kural yoktur (bkz. `src/agents/classification_agent.py`,
  `src/agents/routing_agent.py`, `src/agents/triage_agent.py`,
  `src/agents/missing_info_agent.py`).
- **İstatistiksel model** (`src/models/istatistiksel_siniflandirici.py`):
  öznitelikleri kelime token'ları ve karakter 3-gram'larıdır ve metnin
  tamamı üzerinden hesaplanır. **Şeffaflık notu:** bu tasarımda kişi/yer
  adları teknik olarak öznitelik uzayına girer; ancak model kurgu evrak
  derlemindeki tür-ayırt-edici kalıpları öğrenir, tekil adlar TF-IDF benzeri
  ağırlıklandırmada ihmal edilebilir katkı üretir ve ensemble'da kural
  skoru baskındır (%60). Bu nedenle "adlar girdide hiç yok" İDDİA EDİLMEZ;
  bunun yerine kararların adlardan etkilenmediği aşağıdaki karşı-olgusal
  testle **deneysel olarak** doğrulanır.

## Adillik testi ne kontrol eder?

`tests/test_adillik.py`, karşı-olgusal (counterfactual) değişmezlik testi
uygular: aynı evrak metni, yalnızca kimlik çağrışımlı alanları — kurgu
ad-soyad (kadın/erkek çağrışımlı) ve kurgu il/ilçe adları — değiştirilmiş
**4 evrak şablonu × 5 varyant** halinde uçtan uca pipeline'dan geçirilir ve
şu karar çıktılarının varyantlar arasında **birebir aynı** olduğu doğrulanır:

1. Sınıflandırma türü (`siniflandirma.tur`)
2. Yönlendirilen birim (`yonlendirme.birim`)
3. Öncelik düzeyi (`onceliklendirme.oncelik`)
4. Eksik bilgi alan kümesi (`eksik_bilgiler[].alan`)

Testin vakumda geçmemesi için senaryolar bilinçli çeşitlendirilmiştir:
İVEDİ sinyalli şablonda önceliğin (her kimlikte aynı biçimde) normal dışına
çıktığı, eksik alanlı şablonda eksik kümesinin (her kimlikte aynı içerikle)
boş olmadığı ayrıca doğrulanır. Tüm adlar ve yer adları kurgudur; gerçek
kişi verisi kullanılmaz (şartnamenin "gerçek kamu verisi kullanılmayacak"
kuralıyla uyumlu).

## Sınırlar (dürüst kapsam beyanı)

- Bu test **sentetik ve sınırlı** bir kontroldür: seçilmiş şablonlar ve
  sınırlı sayıda kurgu kimlik varyantı üzerinde çalışır. Kapsamlı bir
  toplumsal yanlılık denetimi (ör. lehçe/ağız çeşitliliği, farklı
  sosyoekonomik dil kullanımı, engellilik bağlamı, gerçek demografik
  dağılımlar üzerinde ölçüm) **değildir** ve öyleymiş gibi sunulmaz.
- Test, karar çıktılarının değişmezliğini ölçer; özet ve yazı taslağı gibi
  serbest metin çıktıları adı/ili doğal olarak içerir — bu, karar yanlılığı
  değil içerik yansımasıdır ve test kapsamı dışındadır.
- Yazım hataları, farklı üslup düzeyleri veya OCR gürültüsü gibi dolaylı
  kimlik göstergelerinin karara etkisi bu testte ölçülmemektedir; ileri
  çalışma olarak not edilir.
- Opsiyonel LLM katmanı devredeyken üretilen serbest metinler bu beyanın
  garantisi dışındadır; sistemde düşük güvenli/serbest metin çıktılar
  zaten insan onayına sunulur (kapı mekanizması).

*Bu belge kurgu verilerle geliştirilen bir yarışma prototipi için
hazırlanmıştır; gerçek kamu hizmetine alım öncesinde bağımsız ve kapsamlı
bir adillik denetimi gerekir.*
