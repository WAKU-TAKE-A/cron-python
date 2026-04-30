import os
import signal
import subprocess
import sys
import time


ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CRON_PYTHON = os.path.join(ROOT_DIR, "cron_python.py")
TARGET_TOOL = os.path.join(ROOT_DIR, "test", "target_tool.py")


def start_process(extra_args):
    cmd = [
        sys.executable,
        CRON_PYTHON,
        "--cron",
        "* * * * *",
        "--run-on-start",
        TARGET_TOOL,
        "exit_with",
        "1",
    ] + extra_args
    return subprocess.Popen(
        cmd,
        cwd=ROOT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def stop_process(proc):
    if proc.poll() is not None:
        return proc.communicate(timeout=5)

    proc.send_signal(signal.SIGTERM)
    try:
        return proc.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        return proc.communicate(timeout=5)


def test_default_keeps_running():
    proc = start_process([])
    time.sleep(3)
    still_running = proc.poll() is None
    out, err = stop_process(proc)

    assert still_running, f"Process exited unexpectedly.\nSTDOUT:\n{out}\nSTDERR:\n{err}"


def test_flag_exits_on_script_error():
    proc = start_process(["--exit-on-script-error"])
    out, err = proc.communicate(timeout=10)

    assert proc.returncode == 1, f"Unexpected return code: {proc.returncode}\nSTDOUT:\n{out}\nSTDERR:\n{err}"
