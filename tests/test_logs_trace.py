from ddeutil.workflow.logs import FileTrace


def test_file_trace_find_traces():
    for log in FileTrace.find_traces():
        print(log.meta)
