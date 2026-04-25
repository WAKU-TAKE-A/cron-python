import sys
import os
import argparse
import logging
import json
import subprocess
import time
import threading
import signal
from datetime import datetime
from logging.handlers import RotatingFileHandler

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_MAX_INSTANCES

VERSION = "0.9.6"

# =========================
# 終了コード定義
# =========================
EXIT_SUCCESS = 0
EXIT_ERROR = 2
EXIT_TIMEOUT = 3

EXIT_LABELS = {
    EXIT_SUCCESS: "success",
    EXIT_ERROR: "error",
    EXIT_TIMEOUT: "timeout",
}

# =========================
# JSONログフォーマッタ
# =========================
class JSONFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            return json.dumps(record.msg, ensure_ascii=False)
        
        log_record = {
            "level": record.levelname,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt)
        }
        return json.dumps(log_record, ensure_ascii=False)

# =========================
# ロガー初期化
# =========================
def setup_logger(args):
    logger = logging.getLogger("cron_python")
    logger.setLevel(logging.INFO)
    logger.handlers = []

    formatter = JSONFormatter() if args.log_format == 'json' else logging.Formatter(
        '[%(asctime)s] %(levelname)s - %(message)s'
    )

    if args.log_dest in ('file', 'both') and args.log_file:
        file_handler = RotatingFileHandler(
            args.log_file,
            encoding='utf-8',
            maxBytes=args.log_max_bytes,
            backupCount=args.log_backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    if args.log_dest in ('stdout', 'both'):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    return logger

# =========================
# スクリプトパス解決
# =========================
def resolve_script_path(script_path):
    if not script_path:
        return None
    # 1. 絶対パスならそのまま
    if os.path.isabs(script_path):
        return script_path
    
    # 2. カレントディレクトリからの相対パスで存在すればそれを優先
    cwd_path = os.path.abspath(script_path)
    if os.path.exists(cwd_path):
        return cwd_path

    # 3. 存在しない場合のみ、EXE/ソースのある場所を基準にする
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, script_path)

# =========================
# 強制終了処理 (Windows)
# =========================
def kill_process_tree(pid, logger):
    try:
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error({"event": "error", "message": f"Kill failed PID={pid}", "stderr": e.stderr})

# =========================
# ストリーム読み取り
# =========================
def stream_reader(stream, logger, stream_name):
    for line in iter(stream.readline, ''):
        line = line.rstrip()
        if line:
            level = logging.WARNING if stream_name == "stderr" else logging.INFO
            logger.log(level, {"event": "script_output", "stream": stream_name, "message": line})
    stream.close()

# =========================
# ジョブ実行
# =========================
def execute_job(script_path, script_args, timeout, logger):
    start_time = time.time()
    logger.info({"event": "job_started", "script": script_path, "params": script_args})

    resolved_path = resolve_script_path(script_path)
    if not resolved_path or not os.path.exists(resolved_path):
        duration = time.time() - start_time
        logger.error({
            "event": "job_finished",
            "status": "error",
            "exit_code": EXIT_ERROR,
            "duration_sec": round(duration, 3),
            "message": f"Script not found: {resolved_path}"
        })
        return EXIT_ERROR

    # EXE化時は PATH 上の python を利用
    python_exe = "python" if getattr(sys, 'frozen', False) else sys.executable
    cmd = [python_exe, "-u", resolved_path] + script_args

    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        threads = []
        t_out = threading.Thread(target=stream_reader, args=(process.stdout, logger, "stdout"))
        t_err = threading.Thread(target=stream_reader, args=(process.stderr, logger, "stderr"))
        t_out.start(); t_err.start()
        threads.extend([t_out, t_err])

        try:
            process.wait(timeout=timeout)
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            kill_process_tree(process.pid, logger)
            exit_code = EXIT_TIMEOUT

        for t in threads: t.join()

    except Exception as e:
        logger.error({"event": "error", "message": f"Exec failed: {str(e)}"})
        exit_code = EXIT_ERROR

    duration = time.time() - start_time
    logger.info({
        "event": "job_finished",
        "status": EXIT_LABELS.get(exit_code, "unknown"),
        "exit_code": exit_code,
        "duration_sec": round(duration, 3)
    })
    return exit_code

def main():
    parser = argparse.ArgumentParser(description="cron-python: Advanced Python Scheduler")
    
    # 動作モードグループ (いずれか必須)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--cron", help="Cron expression (5 or 6 fields)")
    mode_group.add_argument("--once", action="store_true", help="Run once and exit")

    parser.add_argument("script", nargs="?", help="Target Python script")
    parser.add_argument("--timeout", type=int, help="Timeout in seconds")
    parser.add_argument("--log-format", choices=['text', 'json'], default='text')
    parser.add_argument("--log-dest", choices=['stdout', 'file', 'both', 'none'], default='stdout')
    parser.add_argument("--log-file", help="Log file path")
    parser.add_argument("--log-max-bytes", type=int, default=1048576)
    parser.add_argument("--log-backup-count", type=int, default=10)
    parser.add_argument("--run-on-start", action="store_true", help="Run immediately on startup")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    # スマート解析: 既知の引数だけを抽出
    args, remaining = parser.parse_known_args()

    # スクリプト引数の分離ロジック
    script_args = []
    if "--" in remaining:
        idx = remaining.index("--")
        pre_dash = remaining[:idx]
        if not args.script and pre_dash:
            args.script = pre_dash[0]
            script_args = pre_dash[1:] + remaining[idx+1:]
        else:
            script_args = remaining[idx+1:]
            if not args.script and pre_dash:
                args.script = pre_dash[0]
                script_args = pre_dash[1:] + script_args
    else:
        if not args.script and remaining:
            args.script = remaining[0]
            script_args = remaining[1:]
        else:
            script_args = remaining

    if not args.script:
        parser.print_help()
        sys.exit(1)

    logger = setup_logger(args)
    logger.info({"event": "startup", "message": "cron-python starting", "version": VERSION})

    if args.once:
        sys.exit(execute_job(args.script, script_args, args.timeout, logger))

    scheduler = BlockingScheduler()
    
    # シグナルハンドラ
    def handle_exit(signum, frame):
        logger.info({"event": "shutdown", "message": f"Signal {signum} received"})
        scheduler.shutdown(wait=False)
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, handle_exit)
        signal.signal(signal.SIGTERM, handle_exit)
    except:
        pass # WindowsでSIGTERMが失敗する場合の保険

    scheduler.add_listener(lambda e: logger.warning({"event": "job_skipped", "reason": "max_instances"}), EVENT_JOB_MAX_INSTANCES)

    try:
        fields = args.cron.strip().split()
        if len(fields) == 5: trigger = CronTrigger.from_crontab(args.cron)
        elif len(fields) == 6:
            trigger = CronTrigger(second=fields[0], minute=fields[1], hour=fields[2], day=fields[3], month=fields[4], day_of_week=fields[5])
        else: raise ValueError("Invalid cron fields (5 or 6 expected)")

        scheduler.add_job(execute_job, trigger=trigger, args=[args.script, script_args, args.timeout, logger], max_instances=1, coalesce=True, misfire_grace_time=60)
        logger.info({"event": "job_registered", "cron": args.cron, "script": args.script, "params": script_args})

        if args.run_on_start:
            execute_job(args.script, script_args, args.timeout, logger)

        scheduler.start()
    except Exception as e:
        logger.error({"event": "error", "message": f"Scheduler error: {str(e)}"})
        sys.exit(1)

if __name__ == "__main__":
    main()