# Utilities

## gen_id

Generate running ID for able to tracking. This generates process use `md5`
algorithm function if ``WORKFLOW_CORE_WORKFLOW_ID_SIMPLE_MODE`` set to
false. But it will cut this hashing value length to 10 it the setting value
set to true.

=== "example"

    ```python
    assert "1354680202" == gen_id("{}", sensitive=False)
    ```
