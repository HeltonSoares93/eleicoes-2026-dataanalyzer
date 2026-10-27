"""Executa os notebooks de ponta a ponta sobre o projeto de teste."""

from pathlib import Path

import nbformat
import pytest
from nbclient import NotebookClient

NOTEBOOKS = sorted((Path(__file__).resolve().parents[1] / "notebooks").glob("*.ipynb"))


@pytest.mark.lento
@pytest.mark.parametrize("caminho", NOTEBOOKS, ids=lambda p: p.name)
def test_notebook_executa_sem_erro(projeto, caminho, tmp_path):
    nb = nbformat.read(caminho, as_version=4)
    NotebookClient(
        nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(tmp_path)}}
    ).execute()
    nbformat.write(nb, tmp_path / caminho.name)
    erros = [
        o
        for c in nb.cells
        if c.cell_type == "code"
        for o in c.get("outputs", [])
        if o.get("output_type") == "error"
    ]
    assert not erros
