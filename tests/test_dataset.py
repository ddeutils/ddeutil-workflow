import os
from pathlib import Path

import ddeutil.workflow.dataset as ds
import polars as pl


def test_polars_csv(params_simple):
    dataset = ds.PolarsCSV.from_loader(
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
    df = dataset.load()
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
    Path(
        f"{os.getenv('ROOT_PATH')}/tests/data/examples/demo_customer_writer.csv"
    ).unlink(missing_ok=True)
