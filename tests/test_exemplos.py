"""scripts/exemplos.py: SVG pela receita do mapas.json e pelo banco, e a medição (sem banco, sem rede)."""

import importlib.util
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from geoibge import desenho

SVG = "{http://www.w3.org/2000/svg}"
_spec = importlib.util.spec_from_file_location("exemplos", Path(__file__).parents[1] / "scripts" / "exemplos.py")
ex = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ex)

UF = {"sigla": "XX", "largura": 100.0, "altura": 50.0, "contorno": "M0 0 100 0 100 50Z",
      "municipios": {"1100001": {"nome": "Grande & Cia", "nivel": "municipio", "caixa": [0, 0, 80, 50], "d": "M0 0 80 0 80 50Z"},
                     "1100002": {"nome": "Pequeno", "nivel": "municipio", "caixa": [90, 10, 92, 12], "d": "M90 10 92 10 92 12Z"},
                     "1100003": {"nome": "Lagoa", "nivel": "area_operacional", "caixa": [80, 0, 90, 5], "d": "M80 0 90 0 90 5Z"}}}


def _paths(svg):
    return ET.fromstring(svg).findall(f"{SVG}path")


def test_montar_segue_a_receita():
    raiz = ET.fromstring(ex.montar("1100001", UF, largura=200))
    assert raiz.find(f"{SVG}title").text == "Grande & Cia (XX)"
    m = desenho.RAIO_MARCADOR + 4
    assert raiz.get("viewBox") == f"{-m} {-m} {100 + 2 * m:.1f} {50 + 2 * m:.1f}"
    fundo, agua, destaque, contorno = raiz.findall(f"{SVG}path")
    assert fundo.get("d") == "M0 0 80 0 80 50ZM90 10 92 10 92 12Z" and agua.get("d") == "M80 0 90 0 90 5Z"
    assert destaque.get("d") == "M0 0 80 0 80 50Z" and destaque.get("fill") == desenho.CORES["destaque"]
    assert contorno.get("d") == UF["contorno"] and raiz.find(f"{SVG}circle") is None


def test_municipio_pequeno_ganha_circulo():
    circulo = ET.fromstring(ex.montar("1100002", UF)).find(f"{SVG}circle")
    assert (circulo.get("cx"), circulo.get("cy"), circulo.get("r")) == ("91.0", "11.0", str(desenho.RAIO_MARCADOR))


def test_montar_reproduz_o_desenho_do_catalogo():
    cat = json.loads(desenho.JSON_PUBLICO.read_bytes())
    uf = cat["ufs"]["35"]
    paths = _paths(ex.montar("3550308", uf))
    assert paths[2].get("d") == desenho._desenho("35")["paths"]["3550308"]
    assert paths[3].get("d") == desenho._desenho("35")["contorno"]


def test_uf_do_banco_tem_o_formato_do_catalogo():
    linhas = [{"cd_mun": None, "nome": None, "is_municipio": True, "sg_uf": "XX", "largura": 100.0, "altura": 50.0,
               "d": "M 0 0 L 1 1 Z"},
              {"cd_mun": "1100001", "nome": "A", "is_municipio": True, "sg_uf": "XX", "largura": 100.0,
               "altura": 50.0, "d": "M 0 0 L 1 0 Z"},
              {"cd_mun": "1100003", "nome": "L", "is_municipio": False, "sg_uf": "XX", "largura": 100.0,
               "altura": 50.0, "d": "M 2 2 L 3 2 Z"}]
    uf = ex.uf_do_banco(linhas)
    assert (uf["sigla"], uf["largura"], uf["altura"], uf["contorno"]) == ("XX", 100.0, 50.0, "M 0 0 L 1 1 Z")
    assert uf["municipios"]["1100003"]["nivel"] == "area_operacional"
    assert len(_paths(ex.montar("1100001", uf))) == 4  # sem caixa: nunca desenha o círculo


def test_sql_svg_le_o_gold_da_uf():
    assert "marts.geo_municipio" in ex.SQL_SVG and "marts.geo_uf" in ex.SQL_SVG and "st_assvg" in ex.SQL_SVG
    assert all(p in ex.SQL_SVG for p in ("%(edicao)s", "%(cd_uf)s", "%(lado)s"))


def test_mediana_ms_roda_antes_fora_do_cronometro():
    chamadas = []
    ms = ex.mediana_ms(lambda: chamadas.append("f"), 3, antes=lambda: chamadas.append("antes"))
    assert chamadas == ["antes", "f"] * 3 and ms >= 0
    assert ex.fmt(0.123) == "0.12 ms" and ex.fmt(42.4) == "42 ms"
