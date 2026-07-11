# Güvenlik Politikası

## Kapsam

Bu depo, TEKNOFEST 2026 Yapay Zeka Dil Ajanları Yarışması (Senaryo 1 — Kamu Evrak)
için geliştirilen **demo amaçlı** bir akıllı ajan destek sistemini içerir. Sistem
gerçek kamu verisi işlemek için tasarlanmamıştır ve depoda yalnızca sentetik/kurgu
veri bulunur (bkz. `data/README.md`).

## Desteklenen Sürümler

| Sürüm | Destek |
|---|---|
| `main` dalı (en güncel) | ✅ |
| Diğer dallar/etiketler | ❌ |

## Zafiyet Bildirimi

Bir güvenlik açığı bulduğunuzu düşünüyorsanız lütfen **herkese açık issue açmadan
önce** aşağıdaki kanallardan birini kullanın:

1. **GitHub Private Vulnerability Reporting** (tercih edilen): deponun
   *Security → Report a vulnerability* sekmesi üzerinden özel bildirim yapın.
2. Özel bildirim kullanılamıyorsa, depo yöneticilerine GitHub profillerindeki
   iletişim bilgisi üzerinden ulaşın.

Bildirimde şunları eklemeniz çözümü hızlandırır: etkilenen dosya/sürüm, yeniden
üretme adımları, olası etki ve (varsa) öneriniz.

- Bildiriminiz **7 gün** içinde yanıtlanır; doğrulanan bulgular önem derecesine
  göre önceliklendirilir ve düzeltme bu depoda şeffaf biçimde yayımlanır.
- İyi niyetli güvenlik araştırması memnuniyetle karşılanır; sorumlu bildirim
  yapan araştırmacılara karşı hukuki yol izlenmez.

## Veri Koruması (KVKK) Bildirimi

Depodaki tüm evrak örnekleri kurgudur. Kurgu T.C. kimlik numaraları yalnızca
checksum algoritması testleri için üretilmiştir ve gerçek kişilere ait değildir.
**Herhangi bir değerin gerçek bir kişi/kurum kaydıyla çakıştığını fark ederseniz**
(tesadüfi çakışma), lütfen yukarıdaki kanaldan bildirin; ilgili değer derhal
değiştirilir.

## Güvenli Kullanım Notları

- Sistem varsayılan olarak **çevrimdışı/kural tabanlı** modda çalışır; hiçbir
  veri dışarı gönderilmez.
- Opsiyonel LLM entegrasyonu kullanılacaksa API anahtarını yalnızca `.env`
  dosyasında tutun (`.env` git tarafından izlenmez; şablon: `.env.example`).
  Anahtarınızı asla koda veya commit'e yazmayın.
- Streamlit demo arayüzü yerel demo içindir; varsayılan yapılandırma
  (`.streamlit/config.toml`) sunucuyu yalnızca `localhost`'a bağlar. Arayüzü
  ağa açmanız gerekiyorsa bunu bilinçli yapın ve güvenilmeyen ağlarda
  çalıştırmayın.
- Yerel LLM (Ollama vb.) kullanıyorsanız endpoint'i `localhost` ile sınırlı
  tutun; `0.0.0.0`'a kimlik doğrulamasız açmayın.
