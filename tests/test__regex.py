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
    for f in Re.RE_CALLER.findall(
        "${{ matrix.table }}-${{ matrix.partition }}"
    ):
        print(type(f))
        print(f)


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
