import logging
import os
import threading
import time

from cron_python import EXIT_SUCCESS
from cron_python import ManagedScriptRunner
from cron_python import execute_job


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_TOOL = os.path.join(ROOT_DIR, "test", "target_tool.py")


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []
        self.records_lock = threading.Lock()

    def emit(self, record):
        with self.records_lock:
            self.records.append(record.msg)

    def snapshot(self):
        with self.records_lock:
            return list(self.records)


def build_logger():
    logger = logging.getLogger("cron_python_test_signal_shutdown")
    logger.setLevel(logging.INFO)
    logger.handlers = []
    logger.propagate = False
    handler = ListHandler()
    logger.addHandler(handler)
    return logger, handler


def wait_for_log(handler, predicate, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for item in handler.snapshot():
            if isinstance(item, dict) and predicate(item):
                return item
        time.sleep(0.1)
    raise AssertionError(f"Timed out waiting for log event. Captured logs: {handler.snapshot()}")


def test_execute_job_can_be_stopped_from_another_thread():
    logger, handler = build_logger()
    runner = ManagedScriptRunner(TARGET_TOOL, ["heartbeat", "0.2"], timeout=None, logger=logger)
    result = {}

    worker = threading.Thread(
        target=lambda: result.setdefault(
            "exit_code",
            execute_job(TARGET_TOOL, ["heartbeat", "0.2"], timeout=None, logger=logger, runner=runner),
        )
    )
    worker.start()

    wait_for_log(
        handler,
        lambda event: event.get("event") == "script_output" and event.get("message") == "heartbeat",
        10,
    )

    assert runner.stop(reason="signal", exit_code=EXIT_SUCCESS)
    worker.join(timeout=10)

    assert not worker.is_alive(), "execute_job did not return after runner.stop()"
    assert result["exit_code"] == EXIT_SUCCESS
    assert any(
        event.get("event") == "job_finished" and event.get("reason") == "signal"
        for event in handler.snapshot()
        if isinstance(event, dict)
    )


def test_runner_stop_marks_process_as_not_running():
    logger, handler = build_logger()
    runner = ManagedScriptRunner(TARGET_TOOL, ["heartbeat", "0.2"], timeout=None, logger=logger)

    assert runner.start() == EXIT_SUCCESS
    wait_for_log(
        handler,
        lambda event: event.get("event") == "script_output" and event.get("message") == "heartbeat",
        10,
    )

    assert runner.is_running()
    assert runner.stop(reason="signal", exit_code=EXIT_SUCCESS)
    assert runner.wait_for_completion() == EXIT_SUCCESS
    assert not runner.is_running()
