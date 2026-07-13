# Copyright 2026 AGENTRA TECH
# SPDX-License-Identifier: Apache-2.0

"""on_step (canlı akış / streaming) kancasının uçtan uca testleri."""

from src.pipelines.end_to_end_pipeline import EndToEndPipeline

ORNEK = (
    "Genel Müdürlüğe. 3071 sayılı Kanun uyarınca 15.01.2026 tarihli "
    "dilekçemin işleme alınmasını arz ederim. Ali Veli"
)


def test_on_step_her_adimda_cagrilir():
    adimlar = []
    EndToEndPipeline().process_text(
        ORNEK, kayit=False, on_step=lambda adim: adimlar.append(adim)
    )
    # Birçok ajan adımı canlı bildirilmeli
    assert len(adimlar) >= 5
    for a in adimlar:
        assert {"agent", "status", "sure_saniye"} <= set(a)
    ajanlar = [a["agent"] for a in adimlar]
    assert "classification" in ajanlar
    # Adımlar tamamlanma sırasıyla gelir (sınıflandırma bilgi çıkarımından önce)
    assert ajanlar.index("classification") < ajanlar.index("info_extraction")


def test_on_step_yoksa_davranis_degismez():
    r = EndToEndPipeline().process_text(ORNEK, kayit=False)
    assert "siniflandirma" in r


def test_on_step_hatasi_pipeline_bozmaz():
    def bozuk(_adim):
        raise ValueError("kasıtlı test hatası")

    # Callback hata fırlatsa bile pipeline sonuç üretmeli (sunum katmanı izole)
    r = EndToEndPipeline().process_text(ORNEK, kayit=False, on_step=bozuk)
    assert "siniflandirma" in r
