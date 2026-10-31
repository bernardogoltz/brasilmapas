import hashlib

import pytest

from ibge import download


@pytest.fixture
def origem(tmp_path):
    f = tmp_path / "origem.zip"
    f.write_bytes(b"x" * 3_000_000)
    return f


def test_baixar_grava_e_calcula_sha(tmp_path, origem):
    destino = tmp_path / "raw" / "2025" / "a.zip"
    res = download.baixar(origem.as_uri(), destino, tamanho=origem.stat().st_size)
    assert res["baixado"] and destino.read_bytes() == origem.read_bytes()
    assert res["sha256"] == hashlib.sha256(origem.read_bytes()).hexdigest()
    assert not destino.with_name("a.zip.part").exists()


def test_baixar_pula_se_tamanho_bate(tmp_path, origem):
    destino = tmp_path / "a.zip"
    download.baixar(origem.as_uri(), destino, tamanho=origem.stat().st_size)
    origem.unlink()  # se tentasse baixar de novo, falharia
    assert download.baixar("file:///inexistente", destino, tamanho=destino.stat().st_size)["baixado"] is False


def test_baixar_incompleto_falha_e_limpa(tmp_path, origem):
    destino = tmp_path / "a.zip"
    with pytest.raises(IOError):
        download.baixar(origem.as_uri(), destino, tamanho=origem.stat().st_size + 1)
    assert not destino.exists() and not destino.with_name("a.zip.part").exists()
