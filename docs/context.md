# Context

## Workflow Execute

```mermaid
stateDiagram-v2
    [*] --> Workflow : execute

    state Workflow {
        [*] --> Job

        state Job {
            [*] --> generate
            generate --> Strategy

            state Strategy {
                [*] --> strategy01
                strategy01 --> [*]
                --

                [*] --> strategy02
                strategy02 --> [*]
                --

                [*] --> strategy03
                strategy03 --> [*]

            }

            Strategy --> [*]
        }
    }
```

## Job Execute

```mermaid
stateDiagram-v2
    [*] --> Strategy : execute

    state Strategy {
        [*] --> Stage01

        state Stage01 {
            [*] --> stage0101 : handler<br>execute
            stage0101 --> [*]
        }

        Stage01 --> Stage02

        state Stage02 {
            [*] --> stage0201 : handler<br>execute
            stage0201 --> [*]
        }

        Stage02 --> [*]
    }
```

## Stage Execute
