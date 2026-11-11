import pandas as pd
import pytest
from joins import join_preview


def test_composite_keys_dont_multiply_years():
    a = pd.DataFrame({"municipio": ["Madrid", "Madrid"], "anio": [2023, 2024], "pob": [1, 2]})
    b = pd.DataFrame({"municipio": ["madrid", "MADRID"], "anio": [2023, 2024], "centros": [8, 9]})
    result, info = join_preview(a, b, ["municipio", "anio"], ["municipio", "anio"], "inner")
    assert len(result) == 2
    assert info["filas_coincidentes"] == 2


def test_null_keys_never_match():
    a = pd.DataFrame({"municipio": [None, "A"]})
    b = pd.DataFrame({"municipio": [None, "A"]})
    result, _ = join_preview(a, b, ["municipio"], ["municipio"], "inner")
    assert len(result) == 1


def test_refuse_explosive_join():
    a = pd.DataFrame({"id": ["X"] * 100})
    b = pd.DataFrame({"id": ["X"] * 100})
    with pytest.raises(ValueError):
        join_preview(a, b, ["id"], ["id"], "inner", max_rows=1000)
