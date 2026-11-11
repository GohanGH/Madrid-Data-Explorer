import pandas as pd
import pytest
from catalog import compatible_resources, describe_table, download_table


def test_resource_filter():
    dataset = {"resources": [
        {"format": "CSV", "url": "https://datos.comunidad.madrid/file.csv"},
        {"format": "PDF", "url": "https://datos.comunidad.madrid/file.pdf"},
    ]}
    assert len(compatible_resources(dataset)) == 1


def test_reject_external_host():
    with pytest.raises(ValueError):
        download_table({"format": "CSV", "url": "https://example.org/data.csv"})


def test_describe():
    result = describe_table(pd.DataFrame({"a": [1, None], "b": ["x", "y"]}))
    assert result["filas"] == 2
    assert result["variables"][0]["faltantes"] == 1
