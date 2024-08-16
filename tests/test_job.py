from ddeutil.workflow.pipeline import Job


def test_job():
    job = Job()
    print(job)
    print(job.run_id)
