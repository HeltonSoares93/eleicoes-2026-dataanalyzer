"""O app Streamlit abre sem erro no recorte Brasil e numa UF."""

from pathlib import Path

import pytest

APP = str(Path(__file__).resolve().parents[1] / "app" / "streamlit_app.py")


@pytest.mark.lento
def test_app_brasil_e_uf(projeto):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception, at.exception
    assert "Presidente 2026" in at.title[0].value
    at.selectbox[1].select("SE").run()
    assert not at.exception, at.exception
    at.radio[0].set_value(1).run()
    assert not at.exception, at.exception
    at.text_input[0].input("ARACAJU").run()
    assert not at.exception, at.exception
