---
name: owasp-review
description: Bir diff'i OWASP Top 10'a karşı güvenlik açısından incele. Auth, girdi işleme, sorgu veya harici çağrılara dokunan herhangi bir şeyi merge etmeden önce kullan.
when_to_use: yeni endpoint, auth/oturum değişikliği, kullanıcı girdisi, ham sorgu, dosya yükleme, deserialization
---
# OWASP Review
Diff'i her madde için, tam satırıyla kontrol et:
- **Injection** — string ile inşa edilmiş herhangi bir SQL/shell/HTML. Parameterized query / escaping talep et.
- **Broken access control** — kullanıcının kaynağın SAHİBİ olduğunu mu doğruluyor, yoksa yalnızca giriş yapmış olmasını mı? 
- **Auth** — kod içinde secret'lar mı var? süresiz (expiry'siz) token'lar mı? şifre karşılaştırması constant-time değil mi?
- **SSRF** — kullanıcı kontrolündeki bir URL, allowlist olmadan sunucu tarafında fetch ediliyor.
- **Sensitive data** — PII/secret'lar loglanıyor, hatalarda döndürülüyor veya şifresiz gönderiliyor.
- **Deserialization** — güvenilmeyen girdinin pickle/yaml.load/eval içine geçmesi.
- **Dependency** — bilinen CVE'leri olan veya bakımsız yeni bir paket.
Çıktı: bir {line, risk, fix} listesi. Temizse, bunu açıkça söyle. "Bizim frontend'imizden geliyor" diye girdiyi asla güvenli varsayma.
