"""scripts/plots.py: série de códigos IBGE → SVG do matplotlib, com o tempo no título (sem banco, sem rede)."""

import importlib.util
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pytest  # noqa: E402
from matplotlib.collections import PathCollection  # noqa: E402
from matplotlib.patches import PathPatch  # noqa: E402

_spec = importlib.util.spec_from_file_location("plots", Path(__file__).parents[1] / "scripts" / "plots.py")
pl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pl)


def test_agrupar_resolve_6_digitos_tira_repetidos_e_separa_por_uf():
    assert pl.agrupar(["3550308", "355030", "5300108", "3518800"]) == {"35": ["3550308", "3518800"],
                                                                      "53": ["5300108"]}


def test_agrupar_rejeita_codigo_invalido():
    with pytest.raises(ValueError, match="município"):
        pl.agrupar(["9999999"])


def test_path_orienta_exterior_e_buraco_para_a_regra_nonzero():
    exterior_horario = [[0, 0], [0, 10], [10, 10], [10, 0], [0, 0]]
    buraco_horario = [[2, 2], [2, 4], [4, 4], [4, 2], [2, 2]]  # mesmo sentido: sem orientar, o buraco enche
    path = pl._path({"type": "Polygon", "coordinates": [exterior_horario, buraco_horario]}, 0.5)
    v = path.vertices.tolist()
    assert pl._area(v[:5]) > 0 and pl._area(v[5:]) < 0
    assert v[0] == [0.0, 0.0] and max(x for x, _ in v) == 5.0  # lon × cosseno
    fig, ax = plt.subplots(figsize=(2, 4))
    ax.add_patch(PathPatch(path, facecolor="red", edgecolor="none"))
    ax.set_xlim(-1, 6), ax.set_ylim(-1, 11)
    fig.canvas.draw()
    pixels = np.asarray(fig.canvas.buffer_rgba())

    def cor(x, y):
        px, py = ax.transData.transform((x, y))
        return pixels[int(pixels.shape[0] - py), int(px)][:3].tolist()

    assert cor(4, 5) == [255, 0, 0] and cor(1.5, 3) == [255, 255, 255]  # o buraco fica vazio
    plt.close(fig)


def test_plotar_pinta_a_serie_e_poe_o_tempo_no_titulo():
    fig, ms = pl.plotar(["5300108"])
    ax = fig.axes[0]
    assert ms > 0
    assert re.fullmatch(r"1 município · 1 UF · \d+(\.\d)? ms", ax.get_title())
    cores = [c.get_facecolor()[0][:3].round(3).tolist() for c in ax.collections if len(c.get_facecolor())]
    assert [round(int(pl.desenho.CORES["destaque"][i:i + 2], 16) / 255, 3) for i in (1, 3, 5)] in cores


def test_plotar_com_varias_ufs_e_titulo_proprio():
    fig, _ = pl.plotar(["2605459", "5300108"], titulo="Noronha e DF")
    ax = fig.axes[0]
    assert ax.get_title().startswith("Noronha e DF · 2 UFs · ")
    circulos = [c for c in ax.collections if type(c) is PathCollection]  # só o scatter
    assert len(circulos) == 1 and len(circulos[0].get_offsets()) == 1  # Noronha, pequeno: ganha círculo; Brasília não


def test_plotar_serie_vazia():
    with pytest.raises(ValueError, match="vazia"):
        pl.plotar([])


def test_main_grava_o_svg_com_o_tempo(tmp_path):
    saida = tmp_path / "a" / "df.svg"
    assert pl.main(["530010", "-o", str(saida), "-t", "DF"]) == 0
    texto = saida.read_text()
    assert texto.startswith("<?xml") and "<svg" in texto
    assert re.search(r"<!-- DF · 1 UF · [\d.]+ ms -->", texto)
    assert "<dc:date>" not in texto  # sem data: diff estável


def test_main_codigo_invalido_sai_com_2(tmp_path):
    assert pl.main(["123", "-o", str(tmp_path / "x.svg")]) == 2
    assert not (tmp_path / "x.svg").exists()


def test_galeria_so_tem_codigos_validos():
    for titulo, codigos in pl.GALERIA.values():
        assert sum(map(len, pl.agrupar(codigos).values())) == len(codigos), titulo


def test_plotar_mede_a_frio(monkeypatch):
    pl.agrupar(["5300108"])  # aquece o cache
    limpos = []
    for nome in ("_uf", "_indice"):
        cache = getattr(pl.desenho, nome)
        monkeypatch.setattr(cache, "cache_clear", lambda c=cache, n=nome: (limpos.append(n), type(c).cache_clear(c)))
    pl.plotar(["5300108"])
    assert sorted(limpos) == ["_indice", "_uf"]


def test_svg_repetivel_salvo_o_tempo(tmp_path):
    textos = []
    for i in range(2):
        pl.salvar(pl.plotar(["5300108"], titulo="DF")[0], tmp_path / f"{i}.svg")
        textos.append(re.sub(r"[\d.]+ ms", "", (tmp_path / f"{i}.svg").read_text()))
    ids = re.findall(r'clip-path="url\(#(\w+)\)"', textos[0])
    assert ids and ids == re.findall(r'clip-path="url\(#(\w+)\)"', textos[1])


def test_main_recusa_saida_sem_codigos(tmp_path, capsys):
    with pytest.raises(SystemExit) as saida:
        pl.main(["-o", str(tmp_path / "x.svg")])
    assert saida.value.code == 2 and "pedem códigos" in capsys.readouterr().err


def test_trecho_python_do_readme_roda_e_pinta_a_serie(tmp_path, monkeypatch):
    readme = (Path(__file__).parents[1] / "README.md").read_text()
    trecho = re.search(r"Sem o script, direto da lib.*?```python\n(.*?)```", readme, re.S).group(1)
    monkeypatch.chdir(tmp_path)
    exec(compile(trecho, "README.md", "exec"), {})
    plt.close("all")
    svg = (tmp_path / "meus.svg").read_text()
    assert svg.startswith("<?xml") and "#d62728" in svg  # série pintada na cor de destaque
