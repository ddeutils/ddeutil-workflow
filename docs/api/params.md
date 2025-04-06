# Params

The `Param` type constructs by:

```text
Param = Union[
    ChoiceParam,
    DatetimeParam,
    IntParam,
    StrParam,
]
```

## StrParam

!!! example

    === "Str"

        ```yaml
        params:
            value: str
        ```

    === "Str Default"

        ```yaml
        params:
            value: str
            default: foo
        ```

## IntParam

## DatetimeParam

## ChoiceParam
