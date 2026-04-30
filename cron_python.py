import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from apscheduler.events import EVENT_JOB_MAX_INSTANCES
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

VERSION = "0.9.9"

EXIT_SUCCESS = 0
EXIT_ERROR = 2
EXIT_TIMEOUT = 3

EXIT_LABELS = {
    EXIT_SUCCESS: "success",
    EXIT_ERROR: "error",
    EXIT_TIMEOUT: "timeout",
}


def get_exit_label(exit_code):
    if exit_code == EXIT_TIMEOUT:
        return EXIT_LABELS[EXIT_TIMEOUT]
    if exit_code == EXIT_SUCCESS:
        return EXIT_LABELS[EXIT_SUCCESS]
    return EXIT_LABELS[EXIT_ERROR]


def build_cron_trigger(expr):
    fields = expr.strip().split()
    if len(fields) == 5:
        return CronTrigger.from_crontab(expr)
    if len(fields) == 6:
        return CronTrigger(
            second=fields[0],
            minute=fields[1],
            hour=fields[2],
            day=fields[3],
            month=fields[4],
            day_of_week=fields[5],
        )
    raise ValueError("Invalid cron fields (5 or 6 expected)")


class JSONFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            return json.dumps(record.msg, ensure_ascii=False)

        log_record = {
            "level": record.levelname,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt),
        }
        return json.dumps(log_record, ensure_ascii=False)


def setup_logger(args):
    logger = logging.getLogger("cron_python")
    logger.setLevel(logging.INFO)
    logger.handlers = []

    formatter = JSONFormatter() if args.log_format == "json" else logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s"
    )

    if args.log_dest in ("file", "both") and args.log_file:
        file_handler = RotatingFileHandler(
            args.log_file,
            encoding="utf-8",
            maxBytes=args.log_max_bytes,
            backupCount=args.log_backup_count,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if args.log_dest in ("stdout", "both"):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    return logger


def resolve_script_path(script_path):
    if not script_path:
        return None
    if os.path.isabs(script_path):
        return script_path

    cwd_path = os.path.abspath(script_path)
    if os.path.exists(cwd_path):
        return cwd_path

    if getattr(sys, "frozen", False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, script_path)


def kill_process_tree(pid, logger):
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error({"event": "error", "message": f"Kill failed PID={pid}", "stderr": e.stderr})


def stream_reader(stream, logger, stream_name):
    for line in iter(stream.readline, ""):
        line = line.rstrip()
        if line:
            level = logging.WARNING if stream_name == "stderr" else logging.INFO
            logger.log(level, {"event": "script_output", "stream": stream_name, "message": line})
    stream.close()


class ManagedScriptRunner:
    def __init__(self, script_path, script_args, timeout, logger, on_error=None):
        self.script_path = script_path
        self.script_args = script_args
        self.timeout = timeout
        self.logger = logger
        self.on_error = on_error
        self.lock = threading.Lock()
        self.process = None
        self.run_token = 0
        self.start_time = None
        self.forced_exit_code = None
        self.stop_reason = None
        self.last_exit_code = None
        self.last_duration = None
        self.completion_event = threading.Event()

    def start(self):
        with self.lock:
            if self.process and self.process.poll() is None:
                self.logger.warning({
                    "event": "job_skipped",
                    "reason": "already_running",
                    "script": self.script_path,
                })
                return None

        start_time = time.time()
        self.logger.info({"event": "job_started", "script": self.script_path, "params": self.script_args})

        resolved_path = resolve_script_path(self.script_path)
        if not resolved_path or not os.path.exists(resolved_path):
            duration = time.time() - start_time
            self.last_exit_code = EXIT_ERROR
            self.last_duration = duration
            self.completion_event.set()
            self.logger.error({
                "event": "job_finished",
                "status": "error",
                "exit_code": EXIT_ERROR,
                "duration_sec": round(duration, 3),
                "message": f"Script not found: {resolved_path}",
            })
            return EXIT_ERROR

        python_exe = "python" if getattr(sys, "frozen", False) else sys.executable
        cmd = [python_exe, "-u", resolved_path] + self.script_args

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            duration = time.time() - start_time
            self.last_exit_code = EXIT_ERROR
            self.last_duration = duration
            self.completion_event.set()
            self.logger.error({
                "event": "job_finished",
                "status": "error",
                "exit_code": EXIT_ERROR,
                "duration_sec": round(duration, 3),
                "message": f"Exec failed: {str(e)}",
            })
            return EXIT_ERROR

        t_out = threading.Thread(target=stream_reader, args=(process.stdout, self.logger, "stdout"), daemon=True)
        t_err = threading.Thread(target=stream_reader, args=(process.stderr, self.logger, "stderr"), daemon=True)
        t_out.start()
        t_err.start()

        with self.lock:
            self.process = process
            self.run_token += 1
            token = self.run_token
            self.start_time = start_time
            self.forced_exit_code = None
            self.stop_reason = None
            self.last_exit_code = None
            self.last_duration = None
            self.completion_event.clear()

        monitor = threading.Thread(target=self._monitor_process, args=(process, [t_out, t_err], token), daemon=True)
        monitor.start()

        if self.timeout:
            timeout_thread = threading.Thread(target=self._timeout_watch, args=(process.pid, token), daemon=True)
            timeout_thread.start()

        return EXIT_SUCCESS

    def stop(self, reason="stopped", exit_code=EXIT_SUCCESS):
        with self.lock:
            if not self.process or self.process.poll() is not None:
                return False
            self.stop_reason = reason
            self.forced_exit_code = exit_code
            pid = self.process.pid

        kill_process_tree(pid, self.logger)
        return True

    def is_running(self):
        with self.lock:
            return bool(self.process and self.process.poll() is None)

    def wait_for_completion(self):
        self.completion_event.wait()
        return self.last_exit_code if self.last_exit_code is not None else EXIT_ERROR

    def _timeout_watch(self, pid, token):
        time.sleep(self.timeout)
        with self.lock:
            if token != self.run_token:
                return
            if not self.process or self.process.pid != pid or self.process.poll() is not None:
                return
            self.stop_reason = "timeout"
            self.forced_exit_code = EXIT_TIMEOUT

        kill_process_tree(pid, self.logger)

    def _monitor_process(self, process, threads, token):
        process.wait()
        for thread in threads:
            thread.join()

        with self.lock:
            if token != self.run_token:
                return
            duration = time.time() - self.start_time if self.start_time else 0
            final_exit_code = self.forced_exit_code if self.forced_exit_code is not None else process.returncode
            stop_reason = self.stop_reason
            self.process = None
            self.start_time = None
            self.forced_exit_code = None
            self.stop_reason = None
            self.last_exit_code = final_exit_code
            self.last_duration = duration
            self.completion_event.set()

        payload = {
            "event": "job_finished",
            "status": get_exit_label(final_exit_code),
            "exit_code": final_exit_code,
            "duration_sec": round(duration, 3),
        }
        if stop_reason:
            payload["reason"] = stop_reason
        self.logger.info(payload)

        if final_exit_code != EXIT_SUCCESS and self.on_error:
            self.on_error(final_exit_code)


def execute_job(script_path, script_args, timeout, logger):
    runner = ManagedScriptRunner(script_path, script_args, timeout, logger)
    start_result = runner.start()
    if start_result is None:
        return EXIT_SUCCESS
    if start_result != EXIT_SUCCESS:
        return start_result
    return runner.wait_for_completion()


def extract_script_args(args, remaining):
    script_args = []
    if "--" in remaining:
        idx = remaining.index("--")
        pre_dash = remaining[:idx]
        if not args.script and pre_dash:
            args.script = pre_dash[0]
            script_args = pre_dash[1:] + remaining[idx + 1 :]
        else:
            script_args = remaining[idx + 1 :]
            if not args.script and pre_dash:
                args.script = pre_dash[0]
                script_args = pre_dash[1:] + script_args
    else:
        if not args.script and remaining:
            args.script = remaining[0]
            script_args = remaining[1:]
        else:
            script_args = remaining
    return script_args


def validate_mode_args(parser, args):
    window_mode = bool(args.window_start_cron or args.window_end_cron)
    mode_count = sum([1 if args.once else 0, 1 if args.cron else 0, 1 if window_mode else 0])

    if mode_count != 1:
        parser.error("Specify exactly one mode: --once, --cron, or both --window-start-cron and --window-end-cron")

    if bool(args.window_start_cron) != bool(args.window_end_cron):
        parser.error("--window-start-cron and --window-end-cron must be used together")

    if args.run_on_start and args.once:
        parser.error("--run-on-start is not available with --once")


def main():
    parser = argparse.ArgumentParser(description="cron-python: Advanced Python Scheduler")
    parser.add_argument("--cron", help="Cron expression (5 or 6 fields)")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--window-start-cron", help="Cron expression that starts a long-running script")
    parser.add_argument("--window-end-cron", help="Cron expression that stops a long-running script")

    parser.add_argument("script", nargs="?", help="Target Python script")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds")
    parser.add_argument("--log-format", choices=["text", "json"], default="text")
    parser.add_argument("--log-dest", choices=["stdout", "file", "both", "none"], default="stdout")
    parser.add_argument("--log-file", help="Log file path")
    parser.add_argument("--log-max-bytes", type=int, default=1048576)
    parser.add_argument("--log-backup-count", type=int, default=10)
    parser.add_argument("--run-on-start", action="store_true", help="Run immediately on startup")
    parser.add_argument(
        "--exit-on-script-error",
        action="store_true",
        help="Exit cron-python when the target script returns a non-zero exit code",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    args, remaining = parser.parse_known_args()
    validate_mode_args(parser, args)
    script_args = extract_script_args(args, remaining)

    if not args.script:
        parser.print_help()
        sys.exit(1)

    logger = setup_logger(args)
    logger.info({"event": "startup", "message": "cron-python starting", "version": VERSION})

    if args.once:
        sys.exit(execute_job(args.script, script_args, args.timeout, logger))

    scheduler = BlockingScheduler()
    shutdown_state = {"requested": False, "exit_code": EXIT_SUCCESS}
    managed_runner = {"runner": None}

    def request_shutdown(exit_code, message):
        if not args.exit_on_script_error or exit_code in (None, EXIT_SUCCESS):
            return
        if shutdown_state["requested"]:
            return
        shutdown_state["requested"] = True
        shutdown_state["exit_code"] = exit_code
        logger.warning({"event": "shutdown_requested", "message": message, "exit_code": exit_code})
        scheduler.shutdown(wait=False)

    def handle_exit(signum, frame):
        logger.info({"event": "shutdown", "message": f"Signal {signum} received"})
        runner = managed_runner["runner"]
        if runner:
            runner.stop(reason="signal", exit_code=EXIT_SUCCESS)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    def scheduled_job():
        exit_code = execute_job(args.script, script_args, args.timeout, logger)
        request_shutdown(exit_code, "Target script failed; stopping scheduler")

    try:
        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)
    except Exception:
        pass

    scheduler.add_listener(
        lambda e: logger.warning({"event": "job_skipped", "reason": "max_instances"}),
        EVENT_JOB_MAX_INSTANCES,
    )

    try:
        if args.cron:
            trigger = build_cron_trigger(args.cron)
            scheduler.add_job(scheduled_job, trigger=trigger, max_instances=1, coalesce=True, misfire_grace_time=60)
            logger.info({
                "event": "job_registered",
                "mode": "cron",
                "cron": args.cron,
                "script": args.script,
                "params": script_args,
            })

            if args.run_on_start:
                exit_code = execute_job(args.script, script_args, args.timeout, logger)
                request_shutdown(exit_code, "Target script failed during startup run; exiting")
                if shutdown_state["requested"]:
                    sys.exit(shutdown_state["exit_code"])
        else:
            start_trigger = build_cron_trigger(args.window_start_cron)
            end_trigger = build_cron_trigger(args.window_end_cron)
            runner = ManagedScriptRunner(
                args.script,
                script_args,
                args.timeout,
                logger,
                on_error=lambda exit_code: request_shutdown(exit_code, "Target script failed; stopping window scheduler"),
            )
            managed_runner["runner"] = runner

            scheduler.add_job(runner.start, trigger=start_trigger, max_instances=1, coalesce=True, misfire_grace_time=60)
            scheduler.add_job(
                lambda: runner.stop(reason="window_end", exit_code=EXIT_SUCCESS),
                trigger=end_trigger,
                max_instances=1,
                coalesce=True,
                misfire_grace_time=60,
            )
            logger.info({
                "event": "job_registered",
                "mode": "window",
                "start_cron": args.window_start_cron,
                "end_cron": args.window_end_cron,
                "script": args.script,
                "params": script_args,
            })

            now = datetime.now(start_trigger.timezone)
            next_start = start_trigger.get_next_fire_time(None, now)
            next_end = end_trigger.get_next_fire_time(None, now)
            should_start_now = args.run_on_start or (
                next_end and (not next_start or next_end < next_start)
            )
            if should_start_now:
                event_payload = {
                    "event": "window_detected",
                    "state": "inside" if not args.run_on_start else "run_on_start",
                    "message": "Starting script immediately because the current time is inside the active window",
                }
                if args.run_on_start:
                    event_payload["message"] = "Starting script immediately because --run-on-start was specified"
                logger.info({
                    **event_payload
                })
                start_result = runner.start()
                request_shutdown(start_result, "Target script failed during window startup; exiting")
                if shutdown_state["requested"]:
                    sys.exit(shutdown_state["exit_code"])

        scheduler.start()
        if shutdown_state["requested"]:
            sys.exit(shutdown_state["exit_code"])
    except Exception as e:
        logger.error({"event": "error", "message": f"Scheduler error: {str(e)}"})
        sys.exit(1)


if __name__ == "__main__":
    main()
