import os

import ddeutil.workflow.dataset as ds


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
    print(dataset.extras)
    df = dataset.load()
    print(df)
    print(df.count().to_dict(as_series=False))
