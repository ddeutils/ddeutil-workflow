from ddeutil.pipe.__regex import RegexConf


def test_regex_caller():
    for tc, respec in (
        ("test data ${{ utils.params.data('test') }}", "utils.params.data('test')"),
        ("${{ matrix.python-version }}", "matrix.python-version"),
        ("${{matrix.os }}", "matrix.os"),
        ("${{ hashFiles('pyproject.toml') }}-test", "hashFiles('pyproject.toml')"),
        ("${{toJson(github)}}", "toJson(github)"),
        ('echo "event type is:" ${{ github.event.action}}', "github.event.action"),
        ("${{ value.split('{').split('}') }}", "value.split('{').split('}')"),
    ):
        rs = RegexConf.RE_CALLER.search(tc)
        assert respec == rs.group('caller')
