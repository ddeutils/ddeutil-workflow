# -------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# --------------------------------------------------------------------------

import ast
import copy
import logging
from typing import (
    Optional,
    Union,
)

import numpy as np
import pandas as pd
from scipy import stats

from ...errors import NodeArgumentError
from .action import BaseAction

logger = logging.getLogger(__name__)


class RDBMSAction(BaseAction):
    """Base RDBMS Action object.
    This action object contain,

        - SelectColumn
        - Filter
        - Where
        -
    """

    class SelectColumn(BaseAction.SelectColumn):
        def action(self, stm: list, **kwargs) -> list: ...

    class Filter(BaseAction.Filter):
        def action(self, stm: list, **kwargs) -> list: ...

    class Where(BaseAction.Filter):
        def action(self, stm: list, **kwargs) -> list: ...

    class Limit(BaseAction.Limit):
        def action(self, stm: list, **kwargs) -> list: ...


class PandasAction(BaseAction):
    """Base Pandas Action object.
    This action object contain,

        - SelectColumn
        - Filter
        - RenameColumn
        - AddColumn
        - Distinct
        - DropColumn
        - DropDuplicate
        - OrderBy
        - Limit
        - GroupBy
        - Join
        - Union
        - DataQuality
    """

    class SelectColumn(BaseAction.SelectColumn):
        """Select columns from the Pandas DataFrame."""

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            return df[self.props["columns"]]

    class Filter(BaseAction.Filter):
        """Filter with condition string that use `query` method for implement
        this value to the Pandas DataFrame.
        """

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            return df.query(self.props["condition"])

    class RenameColumn(BaseAction.RenameColumn):
        """Rename columns in the Pandas DataFrame from mapping of columns value."""

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            return df.rename(columns=self.props["columns"])

    class AddColumn(BaseAction.AddColumn):
        """Add new columns to the Pandas DataFrame.

        :example:
            -   def salary_stats(value):
                    if value < 10000:
                        return "very low"
                    if 10000 <= value < 25000:
                        return "low"
                    elif 25000 <= value < 40000:
                        return "average"
                    elif 40000 <= value < 50000:
                        return "better"
                    elif value >= 50000:
                        return "very good"

                df['salary_stats'] = df['salary'].map(salary_stats)
                display(df.head())

            -   df['Discounted_Price'] = df['Cost'] - (0.1 * df['Cost'])
        """

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame: ...

    class Distinct(BaseAction.Distinct):
        """Filter distinct data from the Pandas DataFrame."""

        keep: str = "first"

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            return df.drop_duplicates(
                subset=self.props["columns"], keep=self.props["keep"]
            )

    class DropColumn(BaseAction.DropColumn):
        """Drop column from the Pandas DataFrame"""

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            return df.drop(columns=self.props["columns"])

    class DropDuplicate(BaseAction.DropDuplicate):
        """Drop the duplicate values from the Pandas DataFrame."""

        keep: str = "first"

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            return df.drop_duplicates(
                subset=self.props["columns"], keep=self.props["keep"]
            )

    class OrderBy(BaseAction.OrderBy):
        """Order the Pandas DataFrame with mapping columns."""

        columns: Union[dict, list]
        ascending: bool = True

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            if isinstance((_cols := self.props["columns"]), list):
                return df.sort_values(_cols, ascending=self.props["ascending"])
            return df.sort_values(
                list(_cols.keys()), ascending=list(_cols.values())
            )

    class Limit(BaseAction.Limit):
        """Limit number of rows of the Pandas DataFrame."""

        numbers: int = 5

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            return df.head(n=self.props["numbers"])

    class GroupBy(BaseAction.GroupBy):
        """Grouping the Pandas DataFrame

        :ref: https://www.shanelynn.ie/summarising-aggregation-and-grouping-data-in-python-pandas/
        """

        @property
        def _aggregate(self):
            """Return the prepared aggregation arguments."""
            _aggs = self.props["aggregate"]
            for k in _aggs:
                if isinstance((getter := _aggs[k]), str):
                    # Convert the string value to tuple
                    _new = ast.literal_eval(getter)
                    _aggs[k] = (
                        (_new[0], eval(_new[1]))
                        if _new[1].startswith("lambda")
                        else _new
                    )
                elif isinstance(getter, list):
                    # Convert the list value of column and func to tuple
                    _func = (
                        eval(getter[1])
                        if getter[1].startswith("lambda")
                        else getter[1]
                    )
                    _aggs[k] = (getter[0], _func)
            return _aggs

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            return df.groupby(
                self.props["columns"], sort=self.props["sort"], as_index=False
            ).agg(**self._aggregate)

    class Join(BaseAction.Join):
        """Join the Pandas DataFrames together on list of columns.

        :ref: https://www.shanelynn.ie/merge-join-dataframes-python-pandas-index-1/
        """

        other: pd.DataFrame
        on: list
        how: str = "left"
        validate: Optional[str] = None

        def action(
            self, df: pd.DataFrame, other: Optional[pd.DataFrame] = None
        ) -> pd.DataFrame:
            if other is None:
                other: pd.DataFrame = self.props["other"]
            return df.join(
                other,
                on=self.props["on"],
                how=self.props["how"],
                validate=self.props["validate"],
            )

    class Union(BaseAction.Union):
        others: list[pd.DataFrame]

        def action(
            self, df: pd.DataFrame, others: Optional[list[pd.DataFrame]] = None
        ) -> pd.DataFrame:
            if others is None:
                others: list[pd.DataFrame] = self.props["others"]
            return pd.concat(([df] + others), ignore_index=True)

    class DataQuality(BaseAction.DataQuality):
        """Data Quality Check with Pandas DataFrame"""

        dq_function: str
        columns: list[str]
        options: dict = {}

        def action(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:
            if (
                _dqf := getattr(self, f"_dq_{self.props['dq_function']}", None)
            ) is None:
                raise NodeArgumentError(
                    "dq_function",
                    f'the data quality function {self.props["dq_function"]!r} '
                    f"does not implement in the action class.",
                )
            elif not callable(_dqf):
                raise NodeArgumentError(
                    "dq_function",
                    f'the data quality function {self.props["dq_function"]!r} '
                    f"does not callable.",
                )
            return _dqf(df)

        def _dq_is_null(self, df: pd.DataFrame) -> pd.DataFrame:
            """Check to True if the value of the columns is null."""
            for col in self.props["columns"]:
                df[f"{col}_dq_isnull"] = df[col].isnull()
            return df

        def _dq_outlier(self, df: pd.DataFrame) -> pd.DataFrame:
            """Check to True if the value of the columns is the outlier.

            :ref:
                - https://stackoverflow.com/questions/23199796/detect-and-exclude-outliers-in-a-pandas-dataframe
            """
            _std_value: int = self.props["options"].get("std_value", 3)
            for col in self.props["columns"]:
                df[f"{col}_dq_outlier"] = (
                    np.abs(stats.zscore(df[col])) >= _std_value
                )
            return df

    class FromYaml(BaseAction.CallYaml):
        """Action with YAML file."""

        def action(self, _input: pd.DataFrame, **kwargs) -> pd.DataFrame: ...


class BaseNode:
    """Base Node object."""

    base_action: Optional

    @classmethod
    def from_data(cls, data: dict):
        if (_trans := data.pop("transform", None)) is None:
            raise NodeArgumentError(
                "transform", "this necessary key does not exists in data."
            )
        return cls(
            transform=_trans,
            _input=data.pop("input", None),
            _output=data.pop("output", None),
            properties=data,
        )

    def __init__(
        self,
        transform: list,
        _input: Optional[dict] = None,
        _output: Optional[dict] = None,
        properties: Optional[dict] = None,
    ):
        """Main initialize of the base node object that set inputs and outputs
        mapping for the transformation process but its not necessary arguments.

        :param transform: list : A transformation mapping.

        :param _input: Optional[dict] : ...

        :param _output: Optional[dict] : ...
        """
        self._input: dict = _input or {}
        self._output: dict = _output or {}
        self._properties: dict = properties or {}

        # Validate and prepare transform data before running process
        self._transform: list = transform
        self._transform_result: dict = {}

    @property
    def transform(self):
        """Return deep copy of transform data."""
        return copy.deepcopy(self._transform)

    @property
    def properties(self) -> dict:
        """Return main properties that set in the same level of any node keys."""
        return self._properties

    def get_input(self, name: str) -> pd.DataFrame:
        """Return the Pandas DataFrame that alias by a name."""
        if name in self._transform_result:
            # Return DataFrame with deep copy mode.
            return self._transform_result[name].copy()
        elif name in self._input:
            return self._input[name]["data"].load(
                option=self._input[name]["params"]
            )
        raise NodeArgumentError(
            (
                "input",
                "from",
            ),
            f"The alias or from input {name!r} does not exists.",
        )

    def push_output(self) -> None:
        """Push the output"""
        for name in self._output:
            if name not in self._transform_result:
                raise NodeArgumentError(
                    "output",
                    f"from {name!r} does not exists in any transform result or inputs mapping.",
                )
            print(f"Start saving {name!r} ...")
            self._output[name]["data"].save(
                self._transform_result[name],
                option=self._output[name]["params"],
            )


class RDBMSNode(BaseNode):
    """Base RDBMS Node."""

    base_action = RDBMSAction

    def runner(
        self,
        catch: bool = False,
    ) -> Optional[dict[str, pd.DataFrame]]:
        for _task in self.transform:
            # if actions := task.get("actions"):
            #     ...
            # elif query := task.get("query"):
            #     ...
            ...
        if catch:
            return self._transform_result

    def run_query(self): ...


class PandasNode(BaseNode):
    """Base Pandas Node."""

    base_action = PandasAction

    def runner(
        self,
        catch: bool = False,
    ) -> Optional[dict[str, pd.DataFrame]]:
        """Runner"""
        for task in self.transform:
            if actions := task.get("actions"):
                print(
                    f'This task: {task["alias"]!r} will running in action mode ...'
                )
                _input: pd.DataFrame = self.get_input(task["input"])
                _output: pd.DataFrame = self.run_action(_input, actions=actions)
                self._transform_result[task["alias"]]: pd.DataFrame = _output
            else:
                print(f'This task: {task["alias"]!r} does not support')
        if catch:
            return self._transform_result
        self.push_output()

    def run_action(self, _input: pd.DataFrame, actions: dict) -> pd.DataFrame:
        """Run Action on DataFrame"""
        for action in actions:
            print(f"Start action: {action['type']} ...")
            if action.get("type").lower() == "join":
                # Replace alias name of `other` parameter with DataFrame in the Join action type.
                _other: pd.DataFrame = self.get_input(action.pop("other"))
                action["other"] = _other
            elif action.get("type").lower() == "union":
                # Replace alias name of `others` parameter with DataFrame in the Union action type.
                _others: list[pd.DataFrame] = [
                    self.get_input(other) for other in action.pop("others")
                ]
                action["others"] = _others
            _input: pd.DataFrame = self.base_action.from_data(action).action(
                _input
            )
            print(_input.to_string())
        return _input


__all__ = ["RDBMSNode", "PandasNode"]


def test_group_by_df():
    from src.core.loader import Catalog

    # _df = Catalog('demo:catl_customer').load()
    _df = Catalog("demo:catl_seller_csv_type01").load()
    print(_df)
    result = PandasAction.from_data(
        {
            "type": "GroupBy",
            "columns": ["customer_id", "product_id"],
            "aggregate": {
                "order": ("document_date", "count"),
                "value_max": ("sales_value", "max"),
                "value_margin": ("sales_value", lambda x: x.max() - x.min()),
            },
        }
    ).action(_df)
    print(result)
    result = PandasAction.from_data(
        {"type": "RenameColumn", "columns": {"order": "order_sales"}}
    ).action(result)
    print(result)
    # result = BasePandasAction.from_data({
    #     'type': 'Union',
    #     'others': [result]
    # }).action(result, others=[result.head(5)])
    result = PandasAction.from_data(
        {"type": "Union", "others": [result]}
    ).action(result)
    print(result)
    result = PandasAction.from_data(
        {"type": "Filter", "condition": "order_sales >= 2"}
    ).action(result)
    # result.loc[result.product_id == '00A', 'product_id'] = '00",A'
    # result.loc[result.product_id == '00A', 'product_id'] = None
    print(result)
    _df_save = Catalog("demo:catl_seller_csv_prepare")
    # _df_save.save(result)
    # print(_df_save.load())
    # print(result.pipe(lambda grp: grp.sales_value.sum() + grp.document_date.count()))


if __name__ == "__main__":
    test_group_by_df()
