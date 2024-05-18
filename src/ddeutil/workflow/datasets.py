import abc


class BaseLine(abc.ABC):
    @abc.abstractmethod
    def props(self): ...

    @abc.abstractmethod
    def count(self): ...

    @abc.abstractmethod
    def schema(self): ...

    @abc.abstractmethod
    def upload(self): ...

    @abc.abstractmethod
    def download(self): ...

    @abc.abstractmethod
    def remove(self): ...


class PandasCSV:
    def __init__(self): ...


class PandasJson: ...


class PandasParquet: ...


class PandasSQLite: ...


class PandasExcel: ...
