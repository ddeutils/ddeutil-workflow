import os
from pathlib import Path

import ddeutil.workflow.dataset as ds
import polars as pl


def test_polars_csv(params_simple):
    dataset = ds.PolarsCsv.from_loader(
        "ds_csv_local_file",
        params=params_simple,
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


def test_polars_json(params_simple):
    dataset = ds.PolarsJson.from_loader(
        "ds_json_local_file",
        params=params_simple,
        externals={},
    )
    assert f"{os.getenv('ROOT_PATH')}/tests/data/examples" == dataset.endpoint
    assert "demo_iot.json" == dataset.object
    df = dataset.load(options={})
    print(df)
    # df = (
    #     df.select(
    #         pl.all().exclude(["data"]),
    #         pl.col("data").list.explode())
    # )
    # print(df)
    df = df.explode("data")
    print(df)
    # print(df.unnest('data'))
