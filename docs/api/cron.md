# Cron

## On

The **On** is schedule object that receive crontab value and able to generate
datetime value with next or previous with any start point of an input datetime.

!!! example "YAML"

    === "Cron"

        ```yaml
        on_every_5_min:
          type: On
          cron: "*/5 * * * *"
        ```

| field          | data type   |    default    | description |
|----------------|-------------|:-------------:|-------------|

!!! note "Usage"

    ```python
    from ddeutil.workflow.cron import On

    # NOTE: Start load the on data from `.yaml` template file with this key.
    schedule = On.from_conf(name='on_every_5_min', extras={})

    assert '*/5 * * * *' == str(schedule.cronjob)

    cron_iter = schedule.generate('2022-01-01 00:00:00')

    assert "2022-01-01 00:05:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
    assert "2022-01-01 00:10:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
    assert "2022-01-01 00:15:00" f"{cron_iter.next:%Y-%m-%d %H:%M:%S}"
    ```

## YearOn

The `On` model that add year layer.
