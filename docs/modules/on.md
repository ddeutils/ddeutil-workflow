# On

The **On** is schedule object that receive crontab value and able to generate
datetime value with next or previous with any start point of an input datetime.

```yaml
# This file should keep under this path: `./root-path/conf-path/*`
on_every_5_min:
  type: on.On
  cron: "*/5 * * * *"
```

```python
from ddeutil.workflow.on import On

# NOTE: Start load the on data from `.yaml` template file with this key.
schedule = On.from_loader(name='on_every_5_min', externals={})

assert '*/5 * * * *' == str(schedule.cronjob)

cron_iter = schedule.generate('2022-01-01 00:00:00')

assert "2022-01-01 00:05:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert "2022-01-01 00:10:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
assert "2022-01-01 00:15:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
```

## On

## YearOn
