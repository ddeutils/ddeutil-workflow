# Data Utility Package: _Pipeline_

**Table of Contents**:

- [Installation](#installation)
- [Features](#features)
  - [Link](#link)
  - [Model](#model)
  - [Node](#node)
  - [Schedule](#schedule)

This **Utility Pipeline** Object was created for easy to make a simple data
pipeline that able to ETL, T, EL, or ELT by `.yaml` file.

## Installation

```shell
pip install ddeutil-pipe
```

## Features

### Link

```yaml
connection_local_file_landing:
    type: "connection.LocalSystem"
    endpoint: "file:///${APP_PATH}/data/demo/landing"
```

```python
from ddeutil.pipe.connection import Connection

with Connection('demo:connection_local_file_landing').connect() as conn:
    conn.glob('*_csv*')
```

### Model

```yaml
catalog_customer:
    type: "catalog.PandasCSVFile"
    connection: "demo:conn_local_data_landing"
    endpoint: "customer_csv.type01.csv"
    schemas:
        customer_id: {alias: "id::int", nullable: false}
        customer_name: {alias: "name::str", nullable: true}
        customer_age: {alias: "age::str", nullable: true}
        phone_number: {alias: "phone::str", nullable: true}
        register_date: {alias: "datetime64", nullable: false}
        active_flag: {alias: "active::bool", nullable: false}
    encoding: "utf-8"
    delimiter: "|"
    header: 0
    quoting: 3
```

```python
from ddeutil.pipe.catalog import Catalog

Catalog('demo:catalog_customer').load()
```

```text
>>>    customer_id   customer_name customer_age phone_number register_date  active_flag
>>> 0            1  John@email.com          NaN      01-1341    2022-01-01         True
>>> 1            2    Sara Toronto           37      01-2201    2022-01-01         True
>>> 2            3             NaN          NaN      04-1772    2022-01-01        False
>>> 3            4        Tome Vee           15      02-1821    2022-01-01        False
>>> 4            5           Vimmy           23      08-2215    2022-01-01         True
>>> 5            6        Queen J.           19      01-1003    2022-01-01         True
```

### Node

```yaml
node_seller_prepare:
    type: 'node.PandasNode'
    input:
        - alias: "seller"
          from: "demo:catalog_seller_csv"
    transform:
        - alias: "seller_prepare"
          input: "seller"
          actions:
              - type: "GroupBy"
                columns: ['customer_id', 'product_id']
                aggregate:
                    order: "('document_date', 'count')"
                    value_max: "('sales_value', 'max')"
                    value_margin: "('sales_value', 'lambda x: x.max() - x.min()')"
              - type: "RenameColumn"
                columns:
                    order: "order_sales"
              - type: "Filter"
                condition: 'order_sales >= 2'
        - alias: "seller_dq"
          input: "seller_prepare"
          actions:
              - type: "DataQuality"
                dq_function: "is_null"
                columns: ["customer_id"]
              - type: "DataQuality"
                dq_function: "outlier"
                columns: ["value_margin"]
                options:
                    std_value: 3
    output:
        - from: "seller_prepare"
          to: "demo:catalog_seller_csv_prepare"
          mode: "overwrite"
```

```python
from ddeutil.pipe.node import Node

node = Node('demo:node_seller_prepare')
node.deploy()
```

```text
>>> This task: 'seller_prepare' will running in action mode ...
>>> Start action: GroupBy ...
>>>     customer_id product_id  order  value_max  value_margin
>>> 0             1        00A      2      300.0         280.0
>>> 1             1        00B      1      300.0           0.0
>>> 2             1        00C      1       75.0           0.0
>>> 3             2        00A      1      300.0           0.0
>>> 4             2        00B      2      250.0         150.0
>>> 5             2        00C      1      105.0           0.0
>>> 6             2        00D      1       15.0           0.0
>>> 7             3        00B      1      550.0           0.0
>>> 8             3        00C      1       60.0           0.0
>>> 9             3        00D      1      300.0           0.0
>>> 10            4        00A      2      300.0         270.0
>>> 11            4        00B      2      200.0         150.0
>>> 12            5        00C      1       30.0           0.0
>>> 13            6        00B      1       50.0           0.0
>>> Start action: RenameColumn ...
>>>     customer_id product_id  order_sales  value_max  value_margin
>>> 0             1        00A            2      300.0         280.0
>>> 1             1        00B            1      300.0           0.0
>>> 2             1        00C            1       75.0           0.0
>>> 3             2        00A            1      300.0           0.0
>>> 4             2        00B            2      250.0         150.0
>>> 5             2        00C            1      105.0           0.0
>>> 6             2        00D            1       15.0           0.0
>>> 7             3        00B            1      550.0           0.0
>>> 8             3        00C            1       60.0           0.0
>>> 9             3        00D            1      300.0           0.0
>>> 10            4        00A            2      300.0         270.0
>>> 11            4        00B            2      200.0         150.0
>>> 12            5        00C            1       30.0           0.0
>>> 13            6        00B            1       50.0           0.0
>>> Start action: Filter ...
>>>     customer_id product_id  order_sales  value_max  value_margin
>>> 0             1        00A            2      300.0         280.0
>>> 4             2        00B            2      250.0         150.0
>>> 10            4        00A            2      300.0         270.0
>>> 11            4        00B            2      200.0         150.0
```

```text
>>> This task: 'seller_dq' will running in action mode ...
>>> Start action: DataQuality ...
>>>     customer_id product_id  ...  value_margin  customer_id_dq_isnull
>>> 0             1        00A  ...         280.0                  False
>>> 4             2        00B  ...         150.0                  False
>>> 10            4        00A  ...         270.0                  False
>>> 11            4        00B  ...         150.0                  False
>>> Start action: DataQuality ...
>>>     customer_id product_id  ...  customer_id_dq_isnull  value_margin_dq_outlier
>>> 0             1        00A  ...                  False                    False
>>> 4             2        00B  ...                  False                    False
>>> 10            4        00A  ...                  False                    False
>>> 11            4        00B  ...                  False                    False
```

### Schedule

```yaml
schd_for_node:
    type: 'schedule.BaseSchedule'
    cron: "*/5 * * * *"
```

```python
from ddeutil.pipe.schedule import Schedule

schedule = Schedule('schd_for_node')
schedule.cronjob
```

```text
>>> '*/5 * * * *'
```

```python
cron_iterate = schedule.generate('2022-01-01 00:00:00')
for _ in range(5):
   cron_iterate.next.strftime('%Y-%m-%d %H:%M:%S')
```

```text
>>> 2022-01-01 00:05:00
>>> 2022-01-01 00:10:00
>>> 2022-01-01 00:15:00
>>> 2022-01-01 00:20:00
>>> 2022-01-01 00:25:00
```

## License

This project was licensed under the terms of the [MIT license](LICENSE).
