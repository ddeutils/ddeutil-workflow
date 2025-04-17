from datetime import datetime
from unittest import mock

import pytest
from ddeutil.workflow.conf import Config
from ddeutil.workflow.workflow import Release, ReleaseQueue


def test_release_queue():
    queue = ReleaseQueue()

    assert not queue.is_queued
    assert queue.queue == []


def test_release_queue_from_list():
    queue = ReleaseQueue.from_list()
    release = Release.from_dt(datetime(2024, 1, 1, 1))

    assert not queue.is_queued
    assert queue.queue == []

    queue = ReleaseQueue.from_list([])

    assert not queue.is_queued
    assert queue.queue == []

    queue = ReleaseQueue.from_list(
        [datetime(2024, 1, 1, 1), datetime(2024, 1, 2, 1)]
    )

    assert queue.is_queued
    assert release == queue.queue[0]

    if release in queue.running:
        queue.running.remove(release)

    assert release == queue.queue[0]

    queue = ReleaseQueue.from_list([release])

    assert queue.is_queued
    assert queue.check_queue(Release.from_dt("2024-01-01 01:00:00"))

    queue = ReleaseQueue.from_list(
        [datetime(2024, 1, 1, 1), datetime(2024, 1, 2, 1)]
    )

    assert not queue.check_queue(Release.from_dt("2024-01-02"))
    assert queue.check_queue(Release.from_dt("2024-01-02 01:00:00"))


def test_release_queue_from_list_raise():

    # NOTE: Raise because list contain string value.
    with pytest.raises(TypeError):
        ReleaseQueue.from_list(["20240101"])

    # NOTE: Raise because invalid type with from_list method.
    with pytest.raises(TypeError):
        ReleaseQueue.from_list("20240101")


@mock.patch.object(Config, "max_queue_complete_hist", 4)
def test_release_queue_mark_complete():
    queue = ReleaseQueue(
        complete=[Release.from_dt(datetime(2024, 1, 1, i)) for i in range(5)],
    )
    queue.mark_complete(Release.from_dt(datetime(2024, 1, 1, 10)))
    assert len(queue.complete) == 4
