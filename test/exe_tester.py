import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta


VERSION = "0.9.9"
TEST_DIR = "c:/tmp/cron-python/test/run"
CRON_EXE = "c:/tmp/cron-python/dist/cron_python.exe"
TARGET_TOOL = "c:/tmp/cron-python/test/target_tool.py"
REPORT_PATH = "c:/tmp/cron-python/test/exe_test_report.md"


def setup_test_env():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)


def run_cmd(args, timeout=120):
    full_cmd = [CRON_EXE] + args
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)


def run_async(args):
    full_cmd = [CRON_EXE] + args
    return subprocess.Popen(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def kill_process_tree(pid):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, text=True)


def collect_output_async(process, duration_seconds):
    stdout_lines = []
    stderr_lines = []

    def reader(stream, bucket):
        for line in stream:
            bucket.append(line.rstrip())

    t_out = threading.Thread(target=reader, args=(process.stdout, stdout_lines), daemon=True)
    t_err = threading.Thread(target=reader, args=(process.stderr, stderr_lines), daemon=True)
    t_out.start()
    t_err.start()

    time.sleep(duration_seconds)
    kill_process_tree(process.pid)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)

    t_out.join(timeout=2)
    t_err.join(timeout=2)
    return "\n".join(stdout_lines), "\n".join(stderr_lines)


def build_six_field(dt):
    return f"{dt.second} {dt.minute} {dt.hour} {dt.day} {dt.month} *"


def main():
    setup_test_env()
    results = []

    print(f"--- [EXE] cron-python v{VERSION} test start ---")

    print("Test 1: Version output...")
    res = run_cmd(["--version"], timeout=20)
    version_ok = VERSION in res.stdout
    results.append({
        "case": "[EXE] version",
        "result": "PASS" if version_ok and res.returncode == 0 else "FAIL",
        "detail": f"stdout={res.stdout.strip()}",
    })

    print("Test 2: Flexible argument order...")
    res = run_cmd([TARGET_TOOL, "echo", "exe_flex_test", "--once", "--log-format", "json"])
    flex_ok = "exe_flex_test" in res.stdout
    results.append({
        "case": "[EXE] flexible args",
        "result": "PASS" if flex_ok and res.returncode == 0 else "FAIL",
        "detail": f"Output contained exe_flex_test: {flex_ok}",
    })

    print("Test 3: Timeout handling...")
    res = run_cmd(["--once", "--timeout", "1", TARGET_TOOL, "sleep", "5"])
    results.append({
        "case": "[EXE] timeout",
        "result": "PASS" if res.returncode == 3 else "FAIL",
        "detail": f"Exit code: {res.returncode}",
    })

    print("Test 4: Window mode with run-on-start (6-field)...")
    now = datetime.now()
    start_dt = now + timedelta(seconds=25)
    end_dt = now + timedelta(seconds=10)
    p = run_async([
        "--window-start-cron", build_six_field(start_dt),
        "--window-end-cron", build_six_field(end_dt),
        "--run-on-start",
        "--log-format", "json",
        TARGET_TOOL, "heartbeat", "0.5",
    ])
    out, err = collect_output_async(p, 18)
    window_ok = (
        '"state": "run_on_start"' in out
        and '"event": "job_started"' in out
        and '"reason": "window_end"' in out
    )
    results.append({
        "case": "[EXE] window run-on-start",
        "result": "PASS" if window_ok else "FAIL",
        "detail": f"started/logged/stopped={window_ok}",
    })

    print("Test 5: 5-field cron execution (about 75 seconds)...")
    started_at = time.time()
    p = run_async([TARGET_TOOL, "--cron", "* * * * *", "--log-format", "json", "echo", "exe_min_hit"])
    out, err = collect_output_async(p, 75)
    hit_found = "exe_min_hit" in out
    results.append({
        "case": "[EXE] 5-field cron",
        "result": "PASS" if hit_found else "FAIL",
        "detail": f"Hit found: {hit_found}, elapsed: {round(time.time() - started_at)}s",
    })

    print("\n--- [EXE] test summary ---")
    report = f"# cron-python v{VERSION} EXE test report\n\n"
    report += f"Generated: {time.ctime()}\n\n"
    report += "| Test case | Result | Detail |\n"
    report += "| :--- | :--- | :--- |\n"
    for row in results:
        report += f"| {row['case']} | {row['result']} | {row['detail']} |\n"
        print(f"{row['case']}: {row['result']} - {row['detail']}")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
