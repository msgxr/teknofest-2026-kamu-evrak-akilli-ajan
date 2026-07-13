# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""
Resmî yazışma metin desenleri — paylaşılan tek doğruluk kaynağı.

Belge alanlarını (Sayı/Konu/tarih), sayı biçimini ve gizlilik damgalarını
yakalayan düzenli ifadeler; format denetçisi (draft_writer_agent),
e-Yazışma üstveri üretici/doğrulayıcısı (eyazisma) ve sayı üretici
(sayi_uretici) tarafından ortak kullanılır. Desenler 2646 sayılı
Resmî Yazışmalar Yönetmeliği'nin resmî metnindeki biçimlere dayanır.

Şartname Referansı (Görev 2): resmî yazışma kurallarına uygunluk denetimi.
"""

from __future__ import annotations

import re

# m.11/1-2: sayı = "E"/"Z"/"O" ibaresi + DETSİS'teki Devlet Teşkilatı
# Numarası (8 hane) + standart dosya planı kodu + kayıt numarası,
# aralarına kısa çizgi (örnek biçim m.11/2: E-67915368-903.07.02-4752)
SAYI_BICIM_DESENI = re.compile(r"\b[EZO]-\d{8}-[\d.]+-\d+\b")
SAYI_BICIM_TAM = re.compile(r"^[EZO]-\d{8}-[\d.]+-\d+$")

# Belge alan satırları (değer yakalamalı)
SAYI_SATIRI = re.compile(r"(?mi)^\s*Say[ıi]\s*:\s*(.+)$")
KONU_SATIRI = re.compile(r"(?mi)^\s*Konu\s*:\s*(.+)$")

# m.12/1: tarih GG.AA.YYYY (nokta veya eğik çizgi ayraçlı rakamsal biçim)
TARIH_DESENI = re.compile(r"\b(\d{1,2}[./]\d{1,2}[./]\d{4})\b")

# m.25 (gizlilik dereceli belgeler) + m.26/4 (KİŞİYE ÖZEL): damga tek
# başına satır hâlinde büyük harflerle aranır (gövdedeki sıradan
# "gizlilik" benzeri kelimeler damga sayılmaz)
GIZLILIK_DAMGASI = re.compile(
    r"(?m)^\s*(ÇOK GİZLİ|GİZLİ|HİZMETE ÖZEL|KİŞİYE ÖZEL)\s*$"
)


def belge_sayisi(metin: str) -> str:
    """
    Belge metnindeki Sayı değerini temizleyerek döndürür (yoksa "").

    m.12/1 gereği tarih, sayı ile AYNI satırda yer alır; sayı değeri
    çıkarılırken satır sonundaki tarih ayıklanır.
    """
    eslesme = SAYI_SATIRI.search(metin or "")
    if not eslesme:
        return ""
    deger = eslesme.group(1).strip()
    return TARIH_DESENI.sub("", deger).strip()


def belge_konusu(metin: str) -> str:
    """Belge metnindeki Konu değerini döndürür (yoksa "")."""
    eslesme = KONU_SATIRI.search(metin or "")
    return eslesme.group(1).strip() if eslesme else ""


def belge_tarihi(metin: str) -> str:
    """Belge metnindeki ilk GG.AA.YYYY tarihini döndürür (yoksa "")."""
    eslesme = TARIH_DESENI.search(metin or "")
    return eslesme.group(1) if eslesme else ""


def gizlilik_damgasi(metin: str) -> str:
    """Belge metnindeki gizlilik damgasını döndürür (yoksa "")."""
    eslesme = GIZLILIK_DAMGASI.search(metin or "")
    return eslesme.group(1) if eslesme else ""
