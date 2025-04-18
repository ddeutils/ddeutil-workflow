# Logs

The log from the Workflow can be split with 2 parts: **Trace** and **Audit**.

## Trace

The `strout` and `strerr` logs from this package executions will keep on the
config log path.

```text
logs/
 ╰─ run_id=<running-id>/
     ├─ metadata.json
     ├─ stderr.txt
     ╰─ stdout.txt
```

## Audit

The audit log that use to control release execution.
