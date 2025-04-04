# Introduction

A workflow template handle multiple job template that able to run on any compute
node. That is mean a workflow can run job on multiple different nodes.

```mermaid
flowchart LR
    User -->|execute| Workflow
    subgraph Workflow
        direction LR
        Job01 -->|execute| SelfHosted
        Job02 -->|execute| Local

        subgraph SelfHosted [Self Hosted Node]
            direction LR
            Stage01 --> Stage02
        end

        subgraph Local [Local Node]
            direction LR
            Stage03 --> Stage04
        end
    end
```

The core models of this package is `Workflow`, `Job`, and `Stage`.
The other models is used to deploy these models.
