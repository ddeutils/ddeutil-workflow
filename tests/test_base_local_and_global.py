from textwrap import dedent

import pytest

a: str = "main global"


@pytest.fixture(scope="function")
def g():
    """Return globals() that filter-out unnecessary keys."""
    global a
    _g = globals()
    return {
        k: _g[k]
        for k in _g
        if k
        not in (
            "__doc__",
            "__cached__",
            "__loader__",
        )
    }


def test_exec():
    statement: str = dedent(
        """
    import dotenv
    import ddeutil.workflow as wf

    # NOTE: this assert will pass because `a` exists on `g`
    assert a == 'main global'

    a: str = 'exec global'
    """
    )

    exec(statement)

    assert "exec global" == locals()["a"]
    assert "main global" == a


def test_exec_global(g):
    statement: str = dedent(
        """
    import dotenv
    import ddeutil.workflow as wf

    # NOTE: this assert will pass because `a` exists on `g`
    assert a == 'main global'

    a: str = 'exec global'

    x: int = 1

    def foo():
        return 'bar'
    """
    )

    exec(statement, g)

    assert "main global" == a
    assert "exec global" == g["a"]

    # NOTE:
    #   `x` and `foo` will keep in globals `g` that does not impact to
    #   `globals()`.
    assert 1 == g["x"]
    assert globals().get("x") is None
    assert "bar" == g["foo"]()
    assert globals().get("foo") is None

    assert locals().get("foo") is None


def test_exec_global_and_locals(g):
    lc = locals()
    statement: str = dedent(
        """
    import dotenv
    import ddeutil.workflow as wf

    assert a == 'main global'

    a: str = 'exec global'

    x: int = 1

    def foo():
        return 'bar'
    """
    )

    exec(statement, g, lc)

    # NOTE:
    #   `x` will keep in locals `lc` instead `g`
    assert 1 == lc["x"]
    assert "bar" == lc["foo"]()
    assert {"a": str, "x": int} == lc["__annotations__"]
    assert ("g", "__annotations__", "dotenv", "wf", "a", "x", "foo") == tuple(
        lc.keys()
    )

    assert 1 == locals()["x"]
    assert "bar" == locals()["foo"]()

    # NOTE: `x` does not exists on globals `g` nor `globals()`
    assert g.get("x") is None
    assert globals().get("x") is None


def test_local_and_global():
    print()

    def func():
        a = "local"
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        exec("print('(0)', a)", globals())  # (0) main global
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        exec("a='exec global'\nprint('(1)', a)", globals())  # (1) exec global
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        exec(
            "a='exec locals'\nprint('(2)', a)", globals(), locals()
        )  # (2) exec locals
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        exec("print('(3)', a)", globals(), locals())  # (3) local
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        exec("print('(4)', a)", globals())  # (4) exec global
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        exec(
            "global a\na='exec global change'\nprint('(5)', a)",
            globals(),
            locals(),
        )  # (5) exec global change
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        exec("print('(6)', a)", locals())  # (6) local
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        exec("print('(7)', a)", globals())  # (7) exec global change
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

        print("(8)", a)  # (8) local
        print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")

    a = "global"
    assert ("main global", "global") == (globals().get("a"), locals().get("a"))
    func()
    print("(9)", a)  # (9) global
