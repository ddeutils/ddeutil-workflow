from ddeutil.workflow.logs import FileTraceLog


def test_file_trace_find_logs():
    for log in FileTraceLog.find_logs():
        print(log)
