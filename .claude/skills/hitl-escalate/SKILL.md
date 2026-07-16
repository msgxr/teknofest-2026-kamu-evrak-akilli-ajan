---
name: hitl-escalate
description: Bloklanmış çalışmaları, yapılandırılmış kanal üzerinden bir insana yükselt (escalate) veya BLOCKED.md'ye geri düş ve döngüden çık. Döngü belirsiz bir spec'e, eksik bir kimlik bilgisine (credential), onay gerektiren yıkıcı bir eyleme ya da aynı görevde 3+ ardışık verify başarısızlığına takıldığında kullan.
when_to_use: döngü belirsiz bir spec'e, eksik bir kimlik bilgisine, onay gerektiren yıkıcı bir eyleme ya da aynı görevde 3+ ardışık verify başarısızlığına takıldı
---

# İnsan-Döngüde (Human-in-the-Loop) Yükseltme

Uzun-ömürlü ajan döngüleri, cevaplayamadıkları bir soruyla karşılaştıklarında belirli bir biçimde başarısız olur: tahmin ederler. Tahmin gönderilir, sonraki oturum onun üzerine inşa eder ve bir insan baktığında sapma üç commit derinliğindedir. Bu skill, tahliye vanasıdır — ajan takıldığında durur ve insanın üzerine eyleme geçebileceği bir biçimde, temizce sorar.

## Tetik — bunlardan herhangi biri doğruysa yükselt

- **Belirsiz spec.** `PROMPT.md` iki uygulamaya (implementation) izin veriyor ve seçim kullanıcıya-görünür davranışı değiştiriyor.
- **Eksik kimlik bilgisi (credential).** Gerekli bir env var, API key veya config dosyası yok ve ajanın birini oluşturması için onaylı bir yol bulunmuyor.
- **Onay gerektiren yıkıcı eylem.** Bir tabloyu düşürmek (drop), force-push yapmak, kullanıcı verisini silmek, para harcamak, gerçek alıcılara e-posta göndermek.
- **Aynı görevde 3+ ardışık `/verify` başarısızlığı.** Döngü debeleniyor (thrashing). Dördüncü denemeden önce dur ve bir insan gözü al.
- **Harici bağımlılık çökük.** Özelliğin ihtiyaç duyduğu üçüncü-taraf bir servise erişilemiyor ve çevrimdışı (offline) bir yol yok.

Yukarıdakilerin hiçbiri geçerli değilse, yükseltme. Tahmin etmek kötüdür; çözülebilir bir problemde yükseltmek de kötüdür (insanları kanalı görmezden gelmeye alıştırır).

## Birincil eylem — yapılandırılmış kanal üzerinden insanı çağır

`LOOPKIT_HITL_CHANNEL`'ı oku. Desteklenen değerler:

| Değer | Biçim |
|---|---|
| `telegram` | `chat_id=$LOOPKIT_HITL_TELEGRAM_CHAT`, `text=<soru + repo + kısa bağlam>` ile `https://api.telegram.org/bot$LOOPKIT_HITL_TELEGRAM_TOKEN/sendMessage` adresine POST. |
| `slack` | `$LOOPKIT_HITL_SLACK_WEBHOOK` (incoming-webhook URL) adresine JSON `{"text": "..."}` POST'la. |
| `dial` | Mesaj stdin'de olacak şekilde `$LOOPKIT_HITL_DIAL_CMD`'yi çalıştır. Operatör ne bağladıysa — SMS gateway, ntfy, telefon araması, çağrı cihazı (pager). |
| `none` (veya ayarlanmamış) | Birincil eylemi atla. Doğrudan geri-düşüşe (fallback) geç. |

Mesaj gövdesi — her zaman bu beş satır, bu sırayla:

```
[loopkit] blocked in <repo-name> on <ISO timestamp>
Q: <one-line question>
Context: <one-line what you were doing>
Attempted: <one-line what you tried>
Choices: <A | B | C>
```

Kanaldan gelen 2xx-olmayan yanıt yumuşak bir başarısızlıktır. Logla, ardından döngünün yine de temizce çıkması için geri-düşüşe (fallback) devam et.

## Geri-düşüş (Fallback) — BLOCKED.md yaz ve çık

Birincil eylem başarılı olsun ya da olmasın, repo kökünde her zaman tam olarak dört bölümle `./BLOCKED.md` yaz:

```markdown
# Blocked

## Question:
<one sentence, answerable with a short reply>

## Context:
<what feature, which file, which commit, why now — 3-6 lines>

## Attempted:
<bulleted list of what you tried and why each fell short>

## Choices:
- A) <option> — <consequence>
- B) <option> — <consequence>
- C) <option> — <consequence>
```

Sonra `exit 2`. Döngü çalıştırıcı (`run.sh`), her yinelemenin başında `BLOCKED.md`'yi kontrol eder ve varsa kod 2 ile çıkar — bu, bir insan temizleyene kadar döngüyü durdurur.

## İnsan blokajı kaldırır

İnsan `BLOCKED.md`'yi okur, `PROMPT.md`'yi düzenler / kimlik bilgisini yerleştirir / yıkıcı adımı onaylar, ardından `rm BLOCKED.md` yapıp `run.sh`'yi yeniden başlatır. Silinmiş `BLOCKED.md`, blokaj-kaldırma sinyalidir.

## Anti-desenler — bunları yapma

- **Bir cevap uydurma.** "Kullanıcının X'i kastettiğini varsayacağım" sapmanın başladığı yoldur. Belirsizlik altında hiçbir şey varsayma — yükselt.
- **Sonsuza kadar döngüye girme.** Aynı görevde üçüncü ardışık `/verify` başarısızlığından sonra yükselt. Dördüncü deneme, üç kez başarısız olan aynı muhakemeyle başarılı olmayacak.
- **Eksik kimlik bilgisini sessizce yutma.** Yer tutucu (placeholder) commit'leme, özelliği devre dışı bırakma, auth'u "TODO"ya bırakma. Sor.
- **Repo'nun zaten cevapladığı sorular için yükseltme.** Önce `AGENTS.md`, `PROMPT.md` ve son üç commit'i oku. Yükseltme, pahalı insan dikkatidir — onu gerçek belirsizliğe harca.
- **Birincil kanal başarılı oldu diye `BLOCKED.md` yazmayı atlama.** Dosya, döngünün çıkış sözleşmesidir. O olmadan `run.sh` dönmeye devam eder.

## Şunlarla eşleşir

- `adversarial-verify` — 3-verify-başarısızlığı tetiğinin kaynağı.
- `shift-notes` — yükselttikten sonra, sonraki oturumun (blokaj-kaldırma sonrası) tam bağlama sahip olması için blokajı `IMPLEMENTATION_PLAN.md`'ye not düş.
- `spec-first` — belirsiz bir `PROMPT.md`, bir spec-first başarısızlığıdır; insanın blokaj-kaldırması yalnızca tek seferlik soruyu cevaplamakla kalmayıp spec'i sıkılaştırmalıdır.
