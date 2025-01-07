# Hook Stage

The hook stage is the hook Python function from any registry location.

## Getting Started

First, you should to start create your hook.

## Examples

### Hook (Extract & Load)

```yaml
wf_el_pg_to_lake:
  type: Workflow
  params:
    run-date: datetime
    author-email: str
  jobs:
    extract-load:
      stages:
        - name: "Extract Load from Postgres to Lake"
          id: extract-load
          uses: tasks/postgres-to-delta@polars
          with:
            source:
              conn: conn_postgres_url
              query: |
                select * from ${{ params.name }}
                where update_date = '${{ params.datetime }}'
            sink:
              conn: conn_az_lake
              endpoint: "/${{ params.name }}"
```

Implement hook:

```python
from ddeutil.workflow.hook import tag

@tag('polars', alias='postgres-to-delta')
def postgres_to_delta(source, sink):
    return {
        "source": source, "sink": sink
    }
```

### Hook (Transform)

```yaml
wf_hook_mssql_proc:
  type: Workflow
  params:
    run_date: datetime
    sp_name: str
    source_name: str
    target_name: str
  jobs:
    transform:
      stages:
        - name: "Transform Data in MS SQL Server"
          id: transform
          uses: tasks/mssql-proc@odbc
          with:
            exec: ${{ params.sp_name }}
            params:
              run_mode: "T"
              run_date: ${{ params.run_date }}
              source: ${{ params.source_name }}
              target: ${{ params.target_name }}
```

Implement hook:

```python
from ddeutil.workflow.hook import tag

@tag('odbc', alias='mssql-proc')
def odbc_mssql_procedure(_exec: str, params: dict):
    return {
        "exec": _exec, "params": params
    }
```
