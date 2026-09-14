from ki_knowledge.widgetkit_core import DataSourceSpec, TableDataSourceAdapter
from ki_knowledge.widgetkit_registry import resolve_data_source_adapter


def test_table_data_source_adapter_normalizes_flat_rows():
    source = DataSourceSpec(
        source_id="demo.sources",
        source_type="table",
        label="Sources",
        description="Flat table source",
        rows=(
            {"id": "alpha", "label": "Alpha", "value": "active", "url": "/sources/alpha/"},
            {"id": "beta", "label": "Beta", "value": "idle"},
        ),
        stats=(("Rows", "2"),),
        links=(("Open catalog", "/sources/"),),
        detail_url_template="/sources/{id}/",
    )

    payload = TableDataSourceAdapter().adapt(source)

    assert payload["widget_id"] == "demo.sources"
    assert payload["label"] == "Sources"
    assert payload["description"] == "Flat table source"
    assert payload["stats"] == [{"label": "Rows", "value": "2"}]
    assert payload["rows"][0]["url"] == "/sources/alpha/"
    assert payload["rows"][1]["url"] == "/sources/beta/"
    assert payload["links"] == [{"label": "Open catalog", "url": "/sources/"}]


def test_data_source_registry_keeps_table_adapter_registered():
    adapter = resolve_data_source_adapter("table", lambda source: {"widget_id": "fallback"})

    assert isinstance(adapter, TableDataSourceAdapter)
