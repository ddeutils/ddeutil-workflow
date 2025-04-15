# Exceptions

The exception module include all exception class that use on this package.
All exception class inherit from `BaseWorkflowException` class. So, if you do not
know to catch error from this package function, you can use the base class to
catch it.

```python
from ddeutil.workflow.exceptions import BaseWorkflowException

try:
    ...
except BaseWorkflowException as e:
    print(e)
```

## UtilException

The utility exception class that will raise from the `utils` and `reusables`
modules.

## ResultException

The result exception class that will raise from the `results` module.

## StageException

## JobException

## WorkflowException

## ParamValueException

## ScheduleException
