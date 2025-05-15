# Exceptions

The exception module include all exception class that use on this package.
All exception class inherit from `BaseError` class. So, if you do not
know to catch error from this package function, you can use the base class to
catch it.

```python
from ddeutil.workflow.errors import BaseError

try:
    ...
except BaseError as e:
    print(e)
```

## UtilError

The utility exception class that will raise from the `utils` and `reusables`
modules.

## ResultError

The result exception class that will raise from the `results` module.

## StageError

## JobError

## WorkflowError

## ParamError

## ScheduleException
