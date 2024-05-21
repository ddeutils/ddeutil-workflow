import ddeutil.workflow.dataset as ds


def test_polars_csv(params_simple):

    dataset = ds.PolarsCSV.from_loader(
        "ds_csv_local_file",
        params=params_simple,
        externals={},
    )
    df = dataset.load()
    print(df.count().to_dict(as_series=False))


def test_polars_csv_conn(params_simple):
    dataset = ds.PolarsCSV.from_loader(
        "ds_csv_local_file",
        params=params_simple,
        externals={},
    )
    print(dataset)
    # connection = ds.get_simple_conn(dataset.conn, params_simple, {})
    # print(connection)
