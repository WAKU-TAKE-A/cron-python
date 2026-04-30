import json
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CRON_PYTHON = os.path.join(ROOT_DIR, "cron_python.py")
TARGET_TOOL = os.path.join(ROOT_DIR, "test", "target_tool.py")


class EventCollector:
    def __init__(self, process):
        self.process = process
        self.events = []
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._reader, daemon=True)
        self.thread.start()

    def _reader(self):
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {"raw": line}
            payload["_seen_at"] = time.time()
            with self.lock:
                self.events.append(payload)

    def snapshot(self):
        with self.lock:
            return list(self.events)


def build_five_field(dt):
    return f"{dt.minute} {dt.hour} {dt.day} {dt.month} *"


def build_six_field(dt):
    return f"{dt.second} {dt.minute} {dt.hour} {dt.day} {dt.month} *"


def wait_for_event(collector, predicate, timeout_seconds):
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for event in collector.snapshot():
            if predicate(event):
                return event
        time.sleep(0.2)
    raise AssertionError(f"Timed out waiting for event. Captured events: {collector.snapshot()}")


def stop_process(process):
    if process.poll() is not None:
        process.communicate(timeout=5)
        return

    process.send_signal(signal.SIGTERM)
    try:
        process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=10)


def run_window_case(start_expr, end_expr, timeout_seconds):
    cmd = [
        sys.executable,
        CRON_PYTHON,
        "--window-start-cron",
        start_expr,
        "--window-end-cron",
        end_expr,
        "--log-format",
        "json",
        TARGET_TOOL,
        "heartbeat",
        "0.5",
    ]
    process = subprocess.Popen(
        cmd,
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    collector = EventCollector(process)
    try:
        started = wait_for_event(
            collector,
            lambda e: e.get("event") == "job_started",
            timeout_seconds,
        )
        finished = wait_for_event(
            collector,
            lambda e: e.get("event") == "job_finished" and e.get("reason") == "window_end",
            timeout_seconds,
        )
        return started, finished, collector.snapshot()
    finally:
        stop_process(process)


def run_window_case_with_extra_args(start_expr, end_expr, timeout_seconds, extra_args):
    launched_at = time.time()
    cmd = [
        sys.executable,
        CRON_PYTHON,
        "--window-start-cron",
        start_expr,
        "--window-end-cron",
        end_expr,
        "--log-format",
        "json",
    ] + extra_args + [
        TARGET_TOOL,
        "heartbeat",
        "0.5",
    ]
    process = subprocess.Popen(
        cmd,
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    collector = EventCollector(process)
    try:
        started = wait_for_event(
            collector,
            lambda e: e.get("event") == "job_started",
            timeout_seconds,
        )
        finished = wait_for_event(
            collector,
            lambda e: e.get("event") == "job_finished" and e.get("reason") == "window_end",
            timeout_seconds,
        )
        return launched_at, started, finished, collector.snapshot()
    finally:
        stop_process(process)


def test_window_mode_six_field_start_and_stop():
    now = datetime.now()
    start_dt = now + timedelta(seconds=8)
    end_dt = start_dt + timedelta(seconds=8)

    started, finished, events = run_window_case(
        build_six_field(start_dt),
        build_six_field(end_dt),
        timeout_seconds=40,
    )

    assert started["event"] == "job_started"
    assert finished["event"] == "job_finished"
    assert finished["reason"] == "window_end"
    assert finished["exit_code"] == 0
    assert any(event.get("event") == "script_output" for event in events)


def test_window_mode_five_field_start_and_stop():
    now = datetime.now()
    base = now.replace(second=0, microsecond=0) + timedelta(minutes=1)
    start_dt = base
    end_dt = base + timedelta(minutes=1)

    started, finished, events = run_window_case(
        build_five_field(start_dt),
        build_five_field(end_dt),
        timeout_seconds=160,
    )

    assert started["event"] == "job_started"
    assert finished["event"] == "job_finished"
    assert finished["reason"] == "window_end"
    assert finished["exit_code"] == 0
    assert any(event.get("event") == "script_output" for event in events)


def test_window_mode_run_on_start_starts_immediately():
    now = datetime.now()
    start_dt = now + timedelta(seconds=25)
    end_dt = now + timedelta(seconds=8)

    launched_at, started, finished, events = run_window_case_with_extra_args(
        build_six_field(start_dt),
        build_six_field(end_dt),
        timeout_seconds=30,
        extra_args=["--run-on-start"],
    )

    assert started["event"] == "job_started"
    assert started["_seen_at"] - launched_at < 5
    assert finished["event"] == "job_finished"
    assert finished["reason"] == "window_end"
    assert any(
        event.get("event") == "window_detected" and event.get("state") == "run_on_start"
        for event in events
    )
