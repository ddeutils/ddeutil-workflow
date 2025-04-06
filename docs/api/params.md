# Params

The `Param` type constructs by:

```text
Param = Annotated[
    Union[
        MapParam,
        ArrayParam,
        ChoiceParam,
        DatetimeParam,
        DateParam,
        IntParam,
        StrParam,
    ],
    Field(discriminator="type"),
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

## DateParam

## ChoiceParam

## MapParam

## ArrayParam
