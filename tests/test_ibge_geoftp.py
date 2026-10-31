from pathlib import Path

import pytest

from ibge import geoftp

FIX = Path(__file__).parent / "fixtures"


def html(nome):
    return (FIX / nome).read_text(encoding="latin-1")


def test_edicoes_lista_anos_do_diretorio():
    eds = geoftp.edicoes(html("geoftp_malhas_municipais.html"))
    assert eds[0] == 2000 and eds[-1] == 2025
    assert 2019 in eds and len(eds) == len(set(eds))


def test_links_ignora_pai_e_externos():
    ls = geoftp.links(html("geoftp_2025_brasil.html"))
    assert all(not l.startswith(("/", "http")) for l in ls)
    assert "BR_UF_2025.zip" in ls


@pytest.mark.parametrize("arquivo,esperado", [
    ("geoftp_2025_brasil.html", "BR_Municipios_2025.zip"),
    ("geoftp_2019_brasil_br.html", "br_municipios_20200807.zip"),
])
def test_zip_municipios(arquivo, esperado):
    assert geoftp.zip_municipios(html(arquivo)) == esperado


def test_descobrir_url_tenta_brasil_e_depois_brasil_br():
    paginas = {
        f"{geoftp.MALHAS}/municipio_2019/Brasil/": '<a href="BR/">BR/</a>',
        f"{geoftp.MALHAS}/municipio_2019/Brasil/BR/": html("geoftp_2019_brasil_br.html"),
    }
    url = geoftp.descobrir_url(2019, ler=paginas.__getitem__)
    assert url == f"{geoftp.MALHAS}/municipio_2019/Brasil/BR/br_municipios_20200807.zip"


def test_descobrir_url_usa_manifesto_se_listagem_falha():
    def falha(url):
        raise OSError("sem rede")
    assert geoftp.descobrir_url(2015, ler=falha).endswith("municipio_2015/Brasil/BR/br_municipios.zip")


def test_descobrir_url_sem_zip_nacional():
    with pytest.raises(LookupError):
        geoftp.descobrir_url(2010, ler=lambda url: '<a href="ac/">ac/</a>')
