# -------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# --------------------------------------------------------------------------

import json
from typing import (
    Any,
    Optional,
)

import pandas as pd
import polars as pl
from ddeutil.core.base.merge import merge_dict
from ddeutil.io.__base.pathutils import join_path
from ddeutil.node.base.converter import Schemas
from ddeutil.node.exceptions import CatalogArgumentError


class BaseCatalog:
    """Base Catalog object. This object will design necessary properties and
    methods for any kind of subclass catalog types.
    """

    conn_ptt: str = "::"

    option_key: set = {
        "endpoint",
        "connection",
        "alias",
    }

    @classmethod
    def from_data(cls, data: dict):
        """Return Base Catalog object from parsing by configuration data."""
        if not (_endpoint := data.pop("endpoint", None)):
            raise CatalogArgumentError(
                "endpoint",
                f"does not set in data for parsing to {cls.__name__}.",
            )
        elif not (_conn := data.pop("connection", None)):
            if cls.conn_ptt not in _endpoint:
                raise CatalogArgumentError(
                    "connection",
                    f"does not set in data for parsing tot {cls.__name__}.",
                )
            _conn, _endpoint = _endpoint.split("::", maxsplit=1)
        _schemas: Optional[dict] = data.pop("schemas", None)
        return cls(
            endpoint=_endpoint,
            connection=_conn,
            schemas=_schemas,
            properties=data,
        )

    def __init__(
        self,
        endpoint: str,
        connection: Optional = None,
        schemas: Optional[dict] = None,
        properties: Optional[dict] = None,
    ):
        """Main initialize of the base catalog object that create necessary properties
        from `cls.option_key`.
        """
        # TODO: formatter if endpoint have datetime format
        self._endpoint: str = endpoint
        self._connection = connection
        self._props: dict = properties or {}

        # Push the schema input value to Schemas converter object.
        _schemas: dict = schemas or {}
        self._schemas = Schemas(_schemas)

        # Pop the alias properties for represent name of this catalog instance.
        self._alias: str = self._props.pop("alias", self._endpoint)
        self._props_load: dict = self._props.pop("load", {})
        self._props_save: dict = self._props.pop("save", {})

    def __str__(self):
        return self._alias

    @property
    def alias(self) -> str:
        """Return the alias name of the catalog."""
        return self._alias

    @property
    def properties(self) -> dict:
        """Return main properties that set in the same level of any catalog
        keys.
        """
        return self._props

    def props_load(self, addition: Optional[dict] = None) -> dict:
        """Return loading properties."""
        return merge_dict(self._props_load, (addition or {}))

    def props_save(self, addition: Optional[dict] = None) -> dict:
        """Return saving properties."""
        return merge_dict(self._props_save, (addition or {}))

    def option(self, key, value):
        """Set attribute of the catalog object."""
        if key not in self.option_key or not hasattr(self, key):
            raise CatalogArgumentError(
                f"option:{key!r}",
                f"the option method of {self.__class__.__name__!r} object does not support",
            )
        super().__setattr__(f"_{key}", value)
        return self

    def load(self, conn: Optional = None, limit: Optional[int] = None) -> Any:
        raise NotImplementedError(
            f"subclass of `{self.__class__.__name__}` must implement `load()` method."
        )

    def save(self, df: Any, conn: Optional = None) -> None:
        raise NotImplementedError(
            f"subclass of `{self.__class__.__name__}` must implement `save()` method."
        )


class PandasCSVFile(BaseCatalog):
    """Pandas DataFrame with CSV File catalog object."""

    converters: dict = {
        "converter_time": lambda x: pd.to_datetime(x).time(),
        "converter_date": lambda x: pd.to_datetime(x, format="%Y:%m:%d"),
    }

    @property
    def properties(self) -> dict:
        """Return main properties that set in the same level of any catalog keys.

        - encoding  : A string representing the encoding to use in the output file, defaults
            to 'utf-8'. encoding is not supported if path_or_buf is a non-binary file
            object.
            ref on https://docs.python.org/3/library/codecs.html#standard-encodings

        - compression   : If 'infer' and 'path_or_buf' is path-like, then detect compression
            from the following extensions: '.gz', '.bz2', '.zip', '.xz', '.zst',
            '.tar', '.tar.gz', '.tar.xz' or '.tar.bz2' (otherwise no compression).
            Set to None for no compression. Can also be a dict with key 'method'
            set to one of {'zip', 'gzip', 'bz2', 'zstd', 'tar'}.

            As an example,
                -   The following could be passed for faster compression and
                    to create a reproducible gzip archive:

                    compression={'method': 'gzip', 'compresslevel': 1, 'mtime': 1}
        """
        return merge_dict(
            {
                "encoding": "utf-8",
                "compression": "infer",
            },
            self._props,
        )

    def props_load(self, addition: Optional[dict] = None) -> dict:
        """Properties for CSV file reading function from the pandas library,

            - engine    : The C and pyarrow engines are faster, while the python engine
                          is currently more feature-complete. Multithreading is currently
                          only supported by the pyarrow engine.

            - na_filter : Detect missing value markers (empty strings and the value of na_values).
                          In data without any NAs, passing na_filter=False can improve the
                          performance of reading a large file.

            - verbose   : Indicate number of NA values placed in non-numeric columns which default
                          to False.

            - doublequote : When `quotechar` is specified and quoting is not QUOTE_NONE, indicate
                            whether or not to interpret two consecutive `quotechar` elements INSIDE
                            a field as a single `quotechar` element.

            - converters  : Dict of functions for converting values in certain columns. Keys can
                            either be integers or column labels.

                            Note: The value should exist in `self.converters`

            - on_bad_lines : Specifies what to do upon encountering a bad line (a line with too many fields).
                             Allowed values are :

                             - `error`, raise an Exception when a bad line is encountered.

                             - `warn`, raise a warning when a bad line is encountered and skip that line.

                             - `skip`, skip bad lines without raising or warning when they are encountered.

        Note:
            - The `quoting` use before parse `skiprows`. If first row will be comment string value like 'Start',
              and quoting is 2, it will raise error for this sting value. So convert string value from 'Start' to
              '"Start"'.

        :ref:
            - https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html
        """
        _schemas: dict = {}
        if self._schemas.features:
            _schemas: dict = {
                # TODO: default if schemas does not set.
                "names": list(self._schemas.data_type(style="new")),
                "dtype": self._schemas.data_type(style="new"),
            }
        _props: dict = merge_dict(
            self.properties, self._props_load, (addition or {}), _schemas
        )

        # Change value from main properties to save properties.
        _delimiter = _props.pop("delimiter", ",")

        return merge_dict(
            {
                "engine": "python",
                "header": None,
                "sep": _delimiter,
                "na_filter": True,
                "verbose": False,
            },
            _props,
        )

    def props_save(self, addition: Optional[dict] = None) -> dict:
        """Properties for CSV file saving function from pandas library,

            - columns   : Columns to write.

            - header    : Write out the column names. If a list of strings is given it is
                          assumed to be aliases for the column names.

            - na_rep    : Missing data representation which default to ''

            - quoting   : Control field quoting behavior per csv.QUOTE_* constants.
                          Use one of QUOTE_MINIMAL (0), QUOTE_ALL (1), QUOTE_NONNUMERIC (2)
                          or QUOTE_NONE (3).

                          Example:
                              0 :   1,"00""A",2,300.0,280.0
                                    2,00B,2,250.0,150.0

                              1 :   "1","00""A","2","300.0","280.0"
                                    "2","00B","2","250.0","150.0"

                              2 :   1,"00""A",2,300.0,280.0
                                    2,"00B",2,250.0,150.0

                              3 :   1,00"A,2,300.0,280.0
                                    2,00B,2,250.0,150.0

                              Note: This example use default of `doublequote` which be True

            - doublequote : Control quoting of quotechar inside a field.

            - quotechar : String of length 1 that default with '"'. Character used to quote
                          fields.

            - escapechar  : String of length 1. Character used to escape `sep` and `quotechar`
                            when appropriate. When `doublequote` set be True this property will
                            ignore.

        :example:

                    in:     1,00",A,2,300.0,280.0
                            2,00B,2,250.0,150.0

            (i)     properties:
                        'sep': ',', 'quoting': 3, 'doublequote': False, 'escapechar': '\\'
                        'sep': ',', 'quoting': 3, 'doublequote': True, 'escapechar': '\\'

                    out:    1,00"\\,A,2,300.0,280.0
                            2,00B,2,250.0,150.0

            (ii)    properties:
                        'sep': ',', 'quoting': 1, 'doublequote': False, 'escapechar': '\\'

                    out:    "1","00\",A","2","300.0","280.0"
                            "2","00B","2","250.0","150.0"

            (iii)   properties:
                        'sep': ',', 'quoting': 1, 'doublequote': True, 'escapechar': '\\'

                    out:    "1","00"",A","2","300.0","280.0"
                            "2","00B","2","250.0","150.0"

        :ref:
            - https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html
        """
        _props: dict = merge_dict(
            self.properties, self._props_save, (addition or {})
        )

        # Change value from main properties to save properties.
        _header: bool = (_props.pop("header", True)) is not None
        _delimiter: str = _props.pop("delimiter", ",")
        _mode: str = (
            "w"
            if (_m := _props.pop("mode", "overwrite")) == "overwrite"
            else _m[0]
        )

        return merge_dict(
            {
                "index": False,
                "mode": _mode,
                "header": _header,
                "sep": _delimiter,
                "doublequote": True,
            },
            _props,
        )

    def load(
        self,
        conn: Optional = None,
        *,
        limit: Optional[int] = None,
        option: Optional = None,
    ) -> pd.DataFrame:
        """Return DataFrame that loading data from CSV file with `load_csv` method."""
        return pd.read_csv(
            conn.join(conn.path, self._endpoint),
            nrows=limit,
            storage_options=conn.properties,
            **self.props_load(addition=option),
        )

    def save(
        self,
        df: pd.DataFrame,
        conn: Optional = None,
        *,
        option: Optional = None,
    ) -> None:
        """Save DataFrame to CSV file with `to_csv` method."""
        return df.to_csv(
            conn.join(conn.path, self._endpoint),
            storage_options=conn.properties,
            **self.props_save(addition=option),
        )


class PandasJsonFile(BaseCatalog):
    @property
    def properties(self) -> dict:
        """Return main properties that set in the same level of any catalog keys.

        - compression   : If 'infer' and 'path_or_buf' is path-like, then detect compression
                          from the following extensions: '.gz', '.bz2', '.zip', '.xz', '.zst',
                          '.tar', '.tar.gz', '.tar.xz' or '.tar.bz2' (otherwise no compression).
                          Set to None for no compression. Can also be a dict with key 'method'
                          set to one of {'zip', 'gzip', 'bz2', 'zstd', 'tar'}.

                          As an example,
                                -   The following could be passed for faster compression and
                                    to create a reproducible gzip archive:

                                    compression={'method': 'gzip', 'compresslevel': 1, 'mtime': 1}
        """
        return merge_dict(
            {
                "compression": "infer",
            },
            self._props,
        )

    def props_load(self, addition: Optional[dict] = None) -> dict:
        """Properties for Json file reading function from the pandas library,

            - orient    : Indication of expected JSON string format. Compatible JSON strings can
                          be produced by to_json() with a corresponding orient value. The set of
                          possible orients is:

                          - `split` : dict like {index -> [index], columns -> [columns], data -> [values]}

                          - `records` : list like [{column -> value}, ... , {column -> value}]

                          - `index` : dict like {index -> {column -> value}}

                          - `columns` : dict like {column -> {index -> value}}

                          - `values` : just the values array

                          The allowed and default values depend on the value of the typ parameter.

                          - when typ == 'series', default is 'index',

                            - allowed orients are {'split','records','index'}

                            - The Series index must be unique for orient 'index'.

                          - when typ == 'frame', default is 'columns',

                            - allowed orients are {'split','records','index', 'columns','values', 'table'}

                            Note:

                                - The DataFrame index must be unique for orients 'index' and 'columns'.

                                - The DataFrame columns must be unique for orients 'index', 'columns', and 'records'.

            - typ       : The type of object to recover, `frame`, nor `series`, default `frame`.

        :ref:
            - https://pandas.pydata.org/docs/reference/api/pandas.read_json.html

            - https://pandas.pydata.org/docs/reference/api/pandas.json_normalize.html

            - https://towardsdatascience.com/how-to-convert-json-into-a-pandas-dataframe-100b2ae1e0d8
        """
        _schemas: dict = {}
        # if self._schemas.features:
        #     _schemas: dict = {
        #         # TODO: default if schemas does not set.
        #         'dtype': self._schemas.data_type(style='new'),
        #     }
        _props: dict = merge_dict(
            self.properties, self._props_load, (addition or {}), _schemas
        )

        return merge_dict(
            {
                "encoding": "utf-8",
                "typ": "frame",
                "lines": False,
            },
            _props,
        )

    def props_save(self, addition: Optional[dict] = None) -> dict:
        """Properties for Json file saving function from pandas library,

        - orient    : Indication of expected JSON string format,

                      - Series:

                        - default is 'index'

                        - allowed values are: {'split', 'records', 'index', 'table'}.

                      - DataFrame:

                        - default is 'columns'

                        - allowed values are: {'split', 'records', 'index', 'columns', 'values', 'table'}.

                      - The format of the JSON string:

                        - 'split' : dict like {'index' -> [index], 'columns' -> [columns], 'data' -> [values]}

                        - 'records' : list like [{column -> value}, … , {column -> value}]

                        - 'index' : dict like {index -> {column -> value}}

                        - 'columns' : dict like {column -> {index -> value}}

                        - 'values' : just the values array

                        - 'table' : dict like {'schema': {schema}, 'data': {data}}

                        - Describing the data, where data component is like orient='records'.

        - force_ascii   : Force encoded string to be ASCII, default True.

        - lines     : If ‘orient’ is ‘records’ write out line-delimited json format. Will throw ValueError
                      if incorrect ‘orient’ since others are not list-like, default False.

        - indent    : Length of whitespace used to indent each record.
        """
        _props: dict = merge_dict(
            self.properties, self._props_save, (addition or {})
        )

        # Change value from main properties to save properties.
        _mode: str = (
            "w"
            if (_m := _props.pop("mode", "overwrite")) == "overwrite"
            else _m[0]
        )

        return merge_dict(
            {
                "index": False,
                "mode": _mode,
                "indent": None,
                "lines": False,
            },
            _props,
        )

    def load(
        self,
        conn: Optional = None,
        *,
        limit: Optional[int] = None,
        option: Optional = None,
    ) -> pd.DataFrame:
        """Return DataFrame that loading data from Json file with `load_csv` method."""
        _props: dict = self.props_load(addition=option)

        if _props.get("typ") == "series":
            series: pd.Series = pd.read_json(
                join_path(conn.path, self._endpoint),
                nrows=limit,
                storage_options=conn.properties,
                **_props,
            )
            print(series.to_json(orient="columns"))
            if _props.get("orient") == "records":
                _df: pd.DataFrame = pd.json_normalize(
                    json.loads(series.to_json(orient="records"))
                )
            else:
                # Convert `Series` to `DataFrame` with key and value base columns
                _df: pd.DataFrame = series.to_frame(name="value").reset_index(
                    names="key"
                )
            _df.rename(columns=self._schemas.rename_cols(), inplace=True)
            return _df
        elif _props.get("orient") == "values":
            _df: pd.DataFrame = pd.read_json(
                join_path(conn.path, self._endpoint),
                nrows=limit,
                storage_options=conn.properties,
                **_props,
            )
            # TODO: change columns name from schemas.
            _df_normalize = pd.json_normalize(
                json.loads(_df.to_json(orient="records")),
                sep=".",
                max_level=None,
            )
            # _df.rename(columns=self._schemas.rename_cols(), inplace=True)
            return _df_normalize
        return self._load_type_records(
            path=join_path(conn.path, self._endpoint),
            conn=conn,
            limit=limit,
            properties=_props,
        )

    def _load_type_records(
        self,
        path: str,
        conn: Optional = None,
        limit: Optional[int] = None,
        properties: Optional[dict] = None,
    ) -> pd.DataFrame:
        """Return DataFrame that loading data with `records` orient."""
        json_struct = json.loads(
            pd.read_json(
                path, nrows=limit, storage_options=conn.properties, **properties
            ).to_json(orient="records")
        )
        _df: pd.DataFrame = pd.json_normalize(
            json_struct, sep=".", max_level=None
        ).astype(self._schemas.data_type(style="old"))
        _df.rename(columns=self._schemas.rename_cols(), inplace=True)
        # print(_df.to_dict(orient='split'))
        return _df[list(self._schemas.features)]

    def save(
        self,
        df: pd.DataFrame,
        conn: Optional = None,
        *,
        option: Optional = None,
    ) -> None:
        """Save DataFrame to Json file with `to_json` method."""
        return df.to_json(
            conn.join(conn.path, self._endpoint),
            storage_options=conn.properties,
            **self.props_save(addition=option),
        )


class PandasExcelFile(BaseCatalog):
    """Pandas DataFrame with Excel File catalog object."""

    def props_load(self, addition: Optional[dict] = None) -> dict:
        """Properties for Excel file reading function from the pandas library,

            - engine    : Supported engines: “xlrd”, “openpyxl”, “odf”, “pyxlsb”.

                          Engine compatibility :

                          - `xlrd` supports old-style Excel files (.xls).

                          - `openpyxl` supports newer Excel file formats.

                          - `odf` supports OpenDocument file formats (.odf, .ods, .odt).

                          - `pyxlsb` supports Binary Excel files.

            - sheet_name : Strings are used for sheet names. Integers are used in
                           zero-indexed sheet positions (chart sheets do not count as a
                           sheet position). Lists of strings/integers are used to request
                           multiple sheets. Specify None to get all worksheets.

                           Example:
                                - Defaults to 0: 1st sheet as a DataFrame

                                - 1: 2nd sheet as a DataFrame

                                - "Sheet1": Load sheet with name “Sheet1”

                                - [0, 1, "Sheet5"]: Load first, second and sheet named
                                                    “Sheet5” as a dict of DataFrame

                                - None: All worksheets.

        :ref:
            - https://pandas.pydata.org/docs/reference/api/pandas.read_excel.html
        """
        _schemas: dict = {}
        if self._schemas.features:
            _schemas: dict = {
                # TODO: default if schemas does not set.
                "names": list(self._schemas.data_type(style="new")),
                "dtype": self._schemas.data_type(style="new"),
            }
        _props: dict = merge_dict(
            self.properties, self._props_load, (addition or {}), _schemas
        )

        return merge_dict(
            {"engine": "openpyxl", "header": 0, "skipfooter": 0}, _props
        )

    def props_save(self, addition: Optional[dict] = None) -> dict:
        """Properties for CSV file saving function from pandas library,

            - engine    : Write engine to use, 'openpyxl' or 'xlsxwriter'. You can also set
                          this via the options `io.excel.xlsx.writer`, `io.excel.xls.writer`,
                          and `io.excel.xlsm.writer`.

        :ref:
            - https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_excel.html

        """
        _props: dict = merge_dict(
            self.properties, self._props_save, (addition or {})
        )

        return merge_dict(
            {
                "index": False,
                "sheet_name": "Sheet1",
                "header": True,
                "na_rep": "",
            },
            _props,
        )

    def load(
        self,
        conn: Optional = None,
        *,
        limit: Optional[int] = None,
        option: Optional = None,
    ) -> pd.DataFrame:
        return pd.read_excel(
            join_path(conn.path, self._endpoint),
            nrows=limit,
            storage_options=conn.properties,
            **self.props_load(addition=option),
        )

    def save(
        self,
        df: pd.DataFrame,
        conn: Optional = None,
        *,
        option: Optional = None,
    ) -> None:
        df.to_excel(
            join_path(conn.path, self._endpoint),
            storage_options=conn.properties,
            **self.props_save(addition=option),
        )


class PandasParquetFile(BaseCatalog):
    @property
    def properties(self) -> dict:
        """Properties for Parquet file reading function from the pandas library,

                - engine    : The default io.parquet.engine behavior is to try 'pyarrow',
                              falling back to 'fastparquet' if 'pyarrow' is unavailable.

        :ref:
            - https://pandas.pydata.org/docs/reference/api/pandas.read_parquet.html
        """
        return merge_dict(
            {
                "engine": "auto",
            },
            self._props,
        )

    def props_load(self, addition: Optional[dict] = None) -> dict:
        """Properties for Excel file reading function from the pandas library,

        - columns   : If not None, only these columns will be read from the file, default is None.

        - use_nullable_dtypes : If True, use dtypes that use pd.NA as missing value indicator for
                                the resulting DataFrame. (only applicable for the pyarrow engine)
                                As new dtypes are added that support pd.NA in the future, the output
                                with this option will change to use those dtypes. Note:
                                this is an experimental option, and behaviour (e.g. additional
                                support dtypes) may change without notice. Default is False
        """
        _schemas: dict = {}
        _props: dict = merge_dict(
            self.properties, self._props_load, (addition or {}), _schemas
        )
        return merge_dict(
            {"columns": None, "use_nullable_dtypes": False}, _props
        )

    def props_save(self, addition: Optional[dict] = None) -> dict:
        """Properties for Parquet file saving function from pandas library,

        - partition_cols : Column names by which to partition the dataset. Columns are partitioned
                           in the order they are given. Must be None if path is not a string.

        - compression   : Name of the compression to use. Use None for no compression.
                          List of compression, {'snappy', 'gzip', 'brotli', None}, default 'snappy'

        """
        _props: dict = merge_dict(
            self.properties, self._props_save, (addition or {})
        )
        return merge_dict(
            {
                "index": False,
                "partition_cols": None,
                "compression": None,
            },
            _props,
        )

    def load(
        self,
        conn: Optional = None,
        *,
        limit: Optional[int] = None,
        option: Optional = None,
    ) -> pd.DataFrame:
        return pd.read_parquet(
            join_path(conn.path, self._endpoint),
            storage_options=conn.properties,
            **self.props_load(addition=option),
        )

    def save(
        self,
        df: pd.DataFrame,
        conn: Optional = None,
        *,
        option: Optional = None,
    ) -> None:
        df.to_excel(
            join_path(conn.path, self._endpoint),
            storage_options=conn.properties,
            **self.props_save(addition=option),
        )


class PandasPickle(BaseCatalog):
    def load(
        self, conn: Optional = None, limit: Optional[int] = None
    ) -> Any: ...

    def save(self, df: Any, conn: Optional = None) -> None: ...


class PandasSQLite(BaseCatalog):
    @property
    def properties(self) -> dict:
        return merge_dict(
            {"columns": list(self._schemas.data_type(style="new"))}, self._props
        )

    def load(
        self,
        conn: Optional = None,
        *,
        limit: Optional[int] = None,
        option: Optional = None,
    ) -> pd.DataFrame:
        _stm: str = (
            f"select * from {self._endpoint} limit {limit}"
            if limit
            else self._endpoint
        )
        return pd.read_sql(_stm, con=conn.connection, **self.properties)

    def save(
        self, df: Any, conn: Optional = None, *, option: Optional = None
    ) -> None: ...


class PandasPostgres(BaseCatalog):
    @property
    def properties(self) -> dict:
        return merge_dict(
            {"columns": list(self._schemas.data_type(style="new"))}, self._props
        )

    def load(
        self,
        conn: Optional = None,
        *,
        limit: Optional[int] = None,
        option: Optional = None,
    ) -> pd.DataFrame:
        _stm: str = (
            f"select * from {self._endpoint} limit {limit}"
            if limit
            else self._endpoint
        )
        return pd.read_sql(_stm, con=conn.connection, **self.properties)

    def save(
        self, df: Any, conn: Optional = None, *, option: Optional = None
    ) -> None: ...


class PandasGoogleBigQuery(BaseCatalog):
    def load(
        self, conn: Optional = None, limit: Optional[int] = None
    ) -> Any: ...

    def save(self, df: Any, conn: Optional = None) -> None: ...


class PandasAzureSynapse(BaseCatalog):
    def load(
        self, conn: Optional = None, limit: Optional[int] = None
    ) -> Any: ...

    def save(self, df: Any, conn: Optional = None) -> None: ...


class PandasAWSRedShift(BaseCatalog):
    def load(
        self, conn: Optional = None, limit: Optional[int] = None
    ) -> Any: ...

    def save(self, df: Any, conn: Optional = None) -> None: ...


class PolarCSVFile(BaseCatalog):
    def props_load(self, addition: Optional[dict] = None) -> dict:
        """Properties for CSV file reading function from the polars library,

            - low_memory    : Reduce memory usage at expense of performance, default False.

            - use_pyarrow   : Try to use pyarrow’s native CSV parser. This will always parse dates,
                              even if parse_dates=False. This is not always possible. The set of
                              arguments given to this function determines if it is possible to use
                              pyarrow’s native parser. Note that pyarrow and polars may have a
                              different strategy regarding type inference.

        :ref:
            - https://pola-rs.github.io/polars/py-polars/html/reference/api/polars.read_csv.html
        """
        _schemas: dict = {}
        if self._schemas.features:
            _schemas: dict = {
                # TODO: default if schemas does not set.
                "new_columns": list(self._schemas.data_type(style="new")),
                "dtype": self._schemas.data_type(style="new"),
            }
        _props: dict = merge_dict(
            self.properties, self._props_load, (addition or {}), _schemas
        )
        # Change value from main properties to save properties.
        _delimiter = _props.pop("delimiter", ",")

        return merge_dict(
            {
                "encoding": "utf-8",
                "has_header": True,
                "sep": _delimiter,
                "low_memory": False,
                "use_pyarrow": False,
            },
            _props,
        )

    def load(
        self,
        conn: Optional = None,
        limit: Optional[int] = None,
        option: Optional = None,
    ) -> pl.DataFrame:
        """Return DataFrame that loading data from CSV file with `load_csv` method."""
        return pl.read_csv(
            conn.join(conn.path, self._endpoint),
            n_rows=limit,
            storage_options=conn.properties,
            **self.props_load(addition=option),
        )

    def save(self, df: pl.DataFrame, conn: Optional = None) -> None: ...


class DaskCSVFile(BaseCatalog):
    def load(
        self, conn: Optional = None, limit: Optional[int] = None
    ) -> Any: ...

    def save(self, df: Any, conn: Optional = None) -> None: ...


class SparkCSVFile(BaseCatalog):
    def load(
        self, conn: Optional = None, limit: Optional[int] = None
    ) -> Any: ...

    def save(self, df: Any, conn: Optional = None) -> None: ...


__all__ = {
    # File Catalog type
    "PandasCSVFile",
    "PandasJsonFile",
    "PandasExcelFile",
    "PandasParquetFile",
    "PandasPickle",
    # 'PolarCSVFile',
    # 'DaskCSVFile',
    # RDBMS Catalog type
    "PandasSQLite",
    "PandasPostgres",
    # DBMS Catalog type
    # 'PandasMangoDB',
    # 'PandasRedis',
    # Analytic Service Catalog type
    # 'PandasGoogleBigQuery',
    # 'PandasAzureSynapse',
    # 'PandasAWSRedShift',
}


def test_pandas_local():
    from src.core.loader import Connection

    with Connection("demo:conn_local_data_landing").connect() as conn:
        df = PandasCSVFile("customer_csv.type01.csv").load(conn)
        print(df)


def test_polars_local():
    from src.core.loader import Connection

    pl.Config.set_tbl_column_data_type_inline(True)
    pl.Config.set_tbl_hide_column_data_types(True)
    pl.Config.set_tbl_hide_dataframe_shape(True)
    pl.Config.set_tbl_hide_dtype_separator(True)

    with Connection("demo:conn_local_data_landing").connect() as conn:
        df = PolarCSVFile(
            "customer_csv.type01.csv",
            properties={
                "sep": "|",
                "encoding": "utf-8",
            },
        ).load(conn)
        print(df)


def test_pandas_s3():
    from src.core.loader import Connection

    with Connection("demo:conn_s3_data_eng").connect() as conn:
        df = PandasCSVFile("temp/customer.csv").load(conn)
        print(df)


def test_pandas_abfs():
    from src.core.loader import Connection

    with Connection("demo:conn_azure_blob_de_test").connect() as conn:
        df = PandasJsonFile(
            "scg_cbm_do_dev_rg_bf435d1a3dc9-718bf.json",
            properties={
                "orient": "columns",
                "typ": "series",
            },
        ).load(conn)
        print(df)
        print(df.dtypes)


def test_pandas_sqlite():
    from src.core.loader import Connection

    with Connection("demo:conn_local_metadata").connect() as conn:
        df = PandasSQLite("tbl_metadata").load(conn)
        print(df)


if __name__ == "__main__":
    # test_pandas_local()
    test_polars_local()
    # test_pandas_s3()
    # test_pandas_abfs()
    # test_pandas_sqlite()
