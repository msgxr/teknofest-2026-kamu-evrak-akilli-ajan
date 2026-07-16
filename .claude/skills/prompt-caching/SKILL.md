---
name: prompt-caching
description: Prompt'un değişmeyen kısımlarını cache'le, böylece uzun-ömürlü bir döngü her turda tam fiyat ödemeyi bırakır. system prompt, tool tanımları (tool defs) veya referans dokümanlar birçok tur boyunca sabit olduğunda kullan.
when_to_use: uzun oturum, tekrarlanan büyük bağlam, tırmanan maliyet, 1024 token üstü system prompt, turlar boyunca değişmeyen tool tanımları
---

# Prompt Caching

Bir Planla→Uygula→Doğrula döngüsünün her turu aynı system prompt'u, aynı tool tanımlarını ve (genellikle) aynı referans dokümanları yeniden gönderir. cache breakpoint'leri olmadan bunların hepsine, her turda tam input fiyatı ödersin. Onlarla birlikte, cache'lenmiş okumalar yazmanın ~%10'una mal olur.

## Breakpoint'ler nereye konulmalı

Prompt'un tepesinden aşağıya doğru cache'le. cache, önek-eşleşmelidir (prefix-matched) — ortadaki bir kesme, kendisinden sonraki her şeyi geçersiz kılar.

1. **System prompt** — 1024 token'dan (Sonnet/Opus) veya 2048'den (Haiku) büyükse, sonunu bir breakpoint olarak işaretle.
2. **Tool tanımları** — tool seti döngü boyunca sabitse, hemen ardından cache'le.
3. **Büyük sabit dokümanlar** — repo haritası, stil kılavuzu, spec — tura-özgü herhangi bir kullanıcı metninden önce.
4. **Kullanıcı mesajı kökü (stem)** — yalnızca aynı önsöz (preamble) her turda tekrarlanıyorsa.

Son breakpoint'ten sonraki her şey her turda yeniden faturalanır. Bu sorun değil — değişen içeriğin gittiği yer orasıdır.

## TTL seçimi

- **5-dakikalık cache** (varsayılan) — turların saniyeler arayla olduğu sıkı döngüler için. Yazması ücretsiz.
- **1-saatlik cache** — yavaş döngüler için (insan döngüde, arka plan işleri). Yazma maliyeti daha yüksek; başabaş (break-even) ~2 isabet.

Turların dakikalar arayla olduğunu bilmiyorsan 5dk seç.

## Bayatlama kuralları — cache geçersizleştirme sessizdir

- Breakpoint'in üstündeki **herhangi bir bayt değişikliği**, cache'i o noktadan itibaren geçersiz kılar.
- Tool'ları veya mesajları **yeniden sıralamak** değişiklik sayılır.
- **Sondaki boşluk (trailing whitespace)** değişiklik sayılır.
- **Farklı bir model sürümü** değişiklik sayılır.

Maliyet düşmüyorsa, cache-hit metriğini logla. Varsayma.

## Ne zaman cache'lenMEMELİ

- Prompt <1024 token — minimum blok boyutunun altında, tasarruf yok.
- Tek-seferlik (one-shot) çağrılar — yeniden kullanım yok, cache yazması boşa gider.
- Yüksek düzeyde dinamik system prompt (kullanıcı-başına şablonlama) — cache ıskalamaları isabetleri aşar.

## Kırmızı bayraklar

- **Breakpoint ekledikten sonra maliyet grafiği düz** — her turda geçersizleştiriyorsun. Breakpoint'in üstündeki iki ardışık isteği bayt-bayt diff'le.
- **Kullanıcı mesajından sonra breakpoint** — anlamsız; kullanıcı mesajı her turda değişir.
- **Dört+ breakpoint** — en fazla dört; fazlalıklar sessizce yok sayılır.
- **Oturum ortasında düzenlenen bir prompt'u cache'lemek** — kesme noktasının üstündeki tek bir düzenleme, aşağı akıştaki tüm tasarrufları siler.

## Matematik

Cache yazma ≈ 1.25× normal input. Cache okuma ≈ 0.1× normal input. Yani N kez isabet alan, sabit 20K-token'lık bir önek: N=1 cache'siz durumdan daha pahalıdır; N=2 başabaş gelir; N=10 cache'siz durumun ~%15'ine mal olur. Uzun döngüler büyük kazanır; kısa sohbetler kaybeder.

Cache, uzun-ömürlü bir ajandaki tek en büyük maliyet kaldıracıdır. Döngünün başında bir kez ayarla, isabetleri doğrula, unut.
