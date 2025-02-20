from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.workflow import Release, ReleaseQueue


def test_release_queue():
    wf_queue = ReleaseQueue()

    assert not wf_queue.is_queued
    assert wf_queue.queue == []


def test_release_queue_from_list():
    wf_queue = ReleaseQueue.from_list()
    release = Release.from_dt(datetime(2024, 1, 1, 1))

    assert not wf_queue.is_queued
    assert wf_queue.queue == []

    wf_queue = ReleaseQueue.from_list([])

    assert not wf_queue.is_queued
    assert wf_queue.queue == []

    wf_queue = ReleaseQueue.from_list(
        [datetime(2024, 1, 1, 1), datetime(2024, 1, 2, 1)]
    )

    assert wf_queue.is_queued

    wf_queue = ReleaseQueue.from_list([release])

    assert wf_queue.is_queued
    assert wf_queue.check_queue(Release.from_dt("2024-01-01 01:00:00"))

    wf_queue = ReleaseQueue.from_list(
        [datetime(2024, 1, 1, 1), datetime(2024, 1, 2, 1)]
    )

    assert not wf_queue.check_queue(Release.from_dt("2024-01-02"))
    assert wf_queue.check_queue(Release.from_dt("2024-01-02 01:00:00"))


def test_release_queue_from_list_raise():

    # NOTE: Raise because list contain string value.
    with pytest.raises(TypeError):
        ReleaseQueue.from_list(["20240101"])

    # NOTE: Raise because invalid type with from_list method.
    with pytest.raises(TypeError):
        ReleaseQueue.from_list("20240101")


@mock.patch.object(Config, "max_queue_complete_hist", 4)
def test_release_queue_mark_complete():
    wf_queue = ReleaseQueue(
        complete=[Release.from_dt(datetime(2024, 1, 1, i)) for i in range(5)],
    )
    wf_queue.mark_complete(Release.from_dt(datetime(2024, 1, 1, 10)))
    assert len(wf_queue.complete) == 4
