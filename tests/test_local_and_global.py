a = "main global"


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
    print(f"Debug: g -> {globals().get('a')}, l -> {locals().get('a')}")
    func()
    print("(9)", a)  # (9) global
