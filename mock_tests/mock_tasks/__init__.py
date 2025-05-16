from ddeutil.workflow import Result, tag


@tag("v1", alias="get-info")
def get_info(result: Result):
    result.trace.info("... [CALLER]: Info from mock tasks")
    return {"get-info": "success"}
