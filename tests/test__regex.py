import pytest
from ddeutil.workflow.__types import Re


@pytest.mark.parametrize(
    "value,expected",
    (
        (
            "test data ${{ utils.params.data('test') }}",
            "utils.params.data('test')",
        ),
        ("${{ matrix.python-version }}", "matrix.python-version"),
        ("${{matrix.os }}", "matrix.os"),
        (
            "${{ hashFiles('pyproject.toml') }}-test",
            "hashFiles('pyproject.toml')",
        ),
        ("${{toJson(github)}}", "toJson(github)"),
        (
            'echo "event type is:" ${{ github.event.action}}',
            "github.event.action",
        ),
        ("${{ value.split('{').split('}') }}", "value.split('{').split('}')"),
    ),
)
def test_regex_caller(value, expected):
    rs = Re.RE_CALLER.search(value)
    assert expected == rs.group("caller")


def test_regex_caller_multiple():
    assert [
        ("matrix.table", "matrix.", "table", ""),
        ("matrix.partition", "matrix.", "partition", ""),
    ] == Re.RE_CALLER.findall("${{ matrix.table }}-${{ matrix.partition }}")


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            'test-${{ article.pub_date|datetimeformat("%B %Y") }}',
            {
                "caller": "article.pub_date",
                "caller_prefix": "article.",
                "caller_last": "pub_date",
                "post_filters": '|datetimeformat("%B %Y") ',
            },
        ),
        (
            "${{ listx|join(', ') }}",
            {
                "caller": "listx",
                "caller_prefix": "",
                "caller_last": "listx",
                "post_filters": "|join(', ') ",
            },
        ),
        (
            "${{listx | abs | test}}",
            {
                "caller": "listx",
                "caller_prefix": "",
                "caller_last": "listx",
                "post_filters": "| abs | test",
            },
        ),
        (
            "${{ listx.data }}",
            {
                "caller": "listx.data",
                "caller_prefix": "listx.",
                "caller_last": "data",
                "post_filters": "",
            },
        ),
        (
            "${{ params.data.get('name') }}",
            {
                "caller": "params.data.get('name')",
                "caller_prefix": "params.data.",
                "caller_last": "get('name')",
                "post_filters": "",
            },
        ),
    ],
)
def test_regex_caller_filter(value, expected):
    rs = Re.RE_CALLER.search(value)
    assert expected == rs.groupdict()


def test_regex_caller_filter_with_args():
    rs = Re.RE_CALLER.search("${{ params.asat-dt | fmt('%Y%m%d') }}")
    assert {
        "caller": "params.asat-dt",
        "caller_prefix": "params.",
        "caller_last": "asat-dt",
        "post_filters": "| fmt('%Y%m%d') ",
    } == rs.groupdict()


@pytest.mark.parametrize(
    "value,expected",
    [
        (
            "tasks/el-csv-to-parquet@polars",
            ("tasks", "el-csv-to-parquet", "polars"),
        ),
        (
            "tasks.el/csv-to-parquet@pandas",
            ("tasks.el", "csv-to-parquet", "pandas"),
        ),
    ],
)
def test_regex_task_format(value, expected):
    rs = Re.RE_TASK_FMT.search(value)
    assert expected == tuple(rs.groupdict().values())
