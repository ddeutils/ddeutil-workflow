# Logs

A Logs module contain Trace and Audit Pydantic models for process log from
the core workflow engine.

**I separate part of log to 2 types:**

- **Trace**: A stdout and stderr log
- **Audit**: An audit release log for tracking incremental running workflow.

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
