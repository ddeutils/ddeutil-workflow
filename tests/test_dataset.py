import os
from pathlib import Path

import ddeutil.workflow.dataset as ds
import polars as pl


def test_polars_csv():
    dataset = ds.PolarsCsv.from_loader(
        "ds_csv_local_file",
        externals={},
    )
    assert f"{os.getenv('ROOT_PATH')}/tests/data/examples" == dataset.endpoint
    assert (
        f"{os.getenv('ROOT_PATH')}/tests/data/examples" == dataset.conn.endpoint
    )
    assert "demo_customer.csv" == dataset.object
    assert (
        f"local:///{os.getenv('ROOT_PATH')}/tests/data/examples"
        == dataset.conn.get_spec()
    )
    assert dataset.exists()
    df: pl.DataFrame = dataset.load()
    assert [
        "CustomerID",
        "CustomerName",
        "CustomerOrgs",
        "CustomerRevenue",
        "CustomerAge",
        "CreateDate",
    ] == df.columns
    assert 2 == df.select(pl.len()).item()
    dataset.save(df, _object="demo_customer_writer.csv")

    # NOTE: Teardown and remove file that create from ``save`` method.
    Path(
        f"{os.getenv('ROOT_PATH')}/tests/data/examples/demo_customer_writer.csv"
    ).unlink(missing_ok=True)

    df: pl.LazyFrame = dataset.scan()
    assert [
        "CustomerID",
        "CustomerName",
        "CustomerOrgs",
        "CustomerRevenue",
        "CustomerAge",
        "CreateDate",
    ] == df.columns
    dataset.sink(df, _object="demo_customer_sink.csv")
    # NOTE: Teardown and remove file that create from ``sink`` method.
    Path(
        f"{os.getenv('ROOT_PATH')}/tests/data/examples/demo_customer_sink.csv"
    ).unlink(missing_ok=True)


def test_polars_json_nested():
    dataset = ds.PolarsJson.from_loader(
        "ds_json_local_file",
        externals={},
    )
    assert f"{os.getenv('ROOT_PATH')}/tests/data/examples" == dataset.endpoint
    assert "demo_iot.json" == dataset.object
    df = dataset.load(options={})
    print(df)
    df = df.unnest("data")
    print(df)
    df = df.explode("sensor")
    print(df.schema)
