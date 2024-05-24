import pytest
from ddeutil.workflow.__regex import RegexConf


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
    rs = RegexConf.RE_CALLER.search(value)
    assert expected == rs.group("caller")


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
    rs = RegexConf.RE_TASK_FMT.search(value)
    assert expected == tuple(rs.groupdict().values())
