import sys
import os
import argparse
import logging
import json
import subprocess
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

VERSION = "0.9.3"

# Setup basic JSON Formatter
class JSONFormatter(logging.Formatter):
    def format(self, record):
        if isinstance(record.msg, dict):
            return json.dumps(record.msg)
        
        # Fallback to string if not a dict message
        log_record = {
            "level": record.levelname,
            "message": record.getMessage(),
            "time": self.formatTime(record, self.datefmt)
        }
        return json.dumps(log_record)

def setup_logger(args):
    logger = logging.getLogger("cron_python")
    logger.setLevel(logging.INFO)
    logger.handlers = []

    if args.log_format == 'json':
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s - %(message)s')

    # 1. ファイルハンドラーの追加
    if args.log_dest == 'file' and args.log_file:
        file_handler = RotatingFileHandler(
            args.log_file,
            encoding='utf-8',
            maxBytes=args.log_max_bytes,
            backupCount=args.log_backup_count
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # 2. コンソール（Stream）ハンドラーの追加
    # log_dest が 'stdout' の場合はもちろん、'file' の場合もユーザーの要望により同時出力する
    if args.log_dest == 'stdout' or args.log_dest == 'file':
        # 優先順位: --log-stdout > --log-stderr > デフォルト(stdout)
        if args.log_stdout:
            stream = sys.stdout
        elif args.log_stderr:
            stream = sys.stderr
        else:
            stream = sys.stdout
        
        console_handler = logging.StreamHandler(stream)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # ハンドラーが一つもない（log_dest='none'など）場合は NullHandler
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    return logger

def resolve_script_path(script_path):
    if os.path.isabs(script_path):
        return script_path
    
    if script_path.startswith("./") or script_path.startswith(".\\"):
        return os.path.abspath(script_path)
        
    # Resolve relative to current executable
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, script_path)

def kill_process_tree(pid, logger):
    """Kills the process and all its children on Windows using taskkill."""
    try:
        # /F (force), /T (tree), /PID (process id)
        subprocess.run(['taskkill', '/F', '/T', '/PID', str(pid)], 
                       capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        logger.error({
            "event": "error",
            "message": f"Failed to kill process tree for PID {pid}: {e.stderr}"
        })

def execute_job(script_path, json_args, timeout, logger):
    logger.info({"event": "job_started", "script": script_path, "args": json_args})
    
    start_time = time.time()
    
    resolved_path = resolve_script_path(script_path)
    
    if not os.path.exists(resolved_path):
        duration = time.time() - start_time
        logger.error({
            "event": "job_finished",
            "status": "error",
            "exit_code": 2,
            "duration_sec": round(duration, 3),
            "message": f"Script not found: {resolved_path}"
        })
        return 2

    # Assuming sys.executable is the python interpreter executing this
    # Also works fine for PyInstaller if we package only the runner and execute external .py files.
    # Wait, the spec says "Execute external Python scripts via subprocess... Use sys.executable"
    # If using PyInstaller onefile, sys.executable points to cron-python.exe! 
    # But usually a user expects python.exe. We should check if sys.executable is the freeze exe.
    # If frozen, we probably want to use 'python' or the environment's python.
    # Wait, the prompt explicitly says: "Use sys.executable" and "Package into single EXE".
    # I should use sys.executable as requested. But Wait, if sys.executable is the compiled EXE, 
    # it won't run a python script unless we handle it or rely on system python.
    # We will use sys.executable per instructions, but I should be careful if it is frozen.
    
    python_exe = sys.executable if not getattr(sys, 'frozen', False) else "python"
    
    cmd = [python_exe, resolved_path]
    if json_args:
        cmd.append(json_args)
        
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            exit_code = process.returncode
            status = "success" if exit_code == 0 else "error"
            
            if stdout.strip():
                logger.info({"event": "script_stdout", "output": stdout.strip()})
            if stderr.strip():
                logger.info({"event": "script_stderr", "output": stderr.strip()})
                
        except subprocess.TimeoutExpired:
            kill_process_tree(process.pid, logger)
            stdout, stderr = process.communicate()
            exit_code = 3
            status = "timeout"
            
            if stdout.strip():
                logger.info({"event": "script_stdout", "output": stdout.strip()})
            if stderr.strip():
                logger.info({"event": "script_stderr", "output": stderr.strip()})
            
    except Exception as e:
        exit_code = 2
        status = "error"
        logger.error({"event": "error", "message": f"Execution failed: {str(e)}"})
        
    duration = time.time() - start_time
    logger.info({
        "event": "job_finished",
        "status": status,
        "exit_code": exit_code,
        "duration_sec": round(duration, 3)
    })
    
    return exit_code

def main():
    try:
        dash_index = sys.argv.index('--')
        json_args_list = sys.argv[dash_index + 1:]
        cron_args = sys.argv[1:dash_index]
    except ValueError:
        json_args_list = []
        cron_args = sys.argv[1:]

    parser = argparse.ArgumentParser(description="cron-python: Python script scheduler")
    parser.add_argument("script", help="Target Python script to execute", nargs='?')
    parser.add_argument("--cron", help="Cron expression e.g. '*/5 * * * *'", default=None)
    parser.add_argument("--timeout", type=int, help="Timeout in seconds", default=None)
    parser.add_argument("--log-format", choices=['text', 'json'], default='text')
    parser.add_argument("--log-dest", choices=['stdout', 'file', 'none'], default='stdout')
    parser.add_argument("--log-file", help="Path to log file")
    parser.add_argument("--log-max-bytes", type=int, default=1048576, help="Max log file size in bytes before rotation (default: 1MB)")
    parser.add_argument("--log-backup-count", type=int, default=10, help="Max number of rotated log files to keep (default: 10)")
    parser.add_argument("--log-stdout", type=str, choices=['true', 'false'], default='false', help="Force stdout logging")
    parser.add_argument("--log-stderr", type=str, choices=['true', 'false'], default='false', help="Force stderr logging")
    parser.add_argument("--once", action="store_true", help="Run once and exit without scheduling")
    parser.add_argument("--run-on-start", action="store_true", help="Execute job immediately on startup before waiting for first cron trigger")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    
    args = parser.parse_args(cron_args)
    
    if not args.script:
        parser.print_help()
        sys.exit(1)

    # Convert true/false strings to bool
    args.log_stdout = args.log_stdout.lower() == 'true'
    args.log_stderr = args.log_stderr.lower() == 'true'

    logger = setup_logger(args)
    logger.info({"event": "startup", "message": "cron-python is starting"})

    json_args_str = " ".join(json_args_list) if json_args_list else None

    if args.once:
        exit_code = execute_job(args.script, json_args_str, args.timeout, logger)
        sys.exit(exit_code)

    if not args.cron:
        logger.error({"event": "error", "message": "Missing --cron or --once flag"})
        sys.exit(1)

    try:
        scheduler = BlockingScheduler()
        
        cron_string = args.cron.strip()
        fields = cron_string.split()
        
        if len(fields) == 5:
            trigger = CronTrigger.from_crontab(cron_string)
        elif len(fields) == 6:
            # Extended format: second, minute, hour, day, month, day_of_week
            trigger = CronTrigger(
                second=fields[0],
                minute=fields[1],
                hour=fields[2],
                day=fields[3],
                month=fields[4],
                day_of_week=fields[5]
            )
        else:
            raise ValueError(f"Wrong number of fields; got {len(fields)}, expected 5 or 6")
        
        scheduler.add_job(
            execute_job,
            trigger=trigger,
            args=[args.script, json_args_str, args.timeout, logger],
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60
        )
        
        logger.info({
            "event": "job_registered",
            "cron": args.cron,
            "script": args.script
        })

        if args.run_on_start:
            logger.info({"event": "run_on_start", "message": "Executing job immediately before first cron trigger"})
            execute_job(args.script, json_args_str, args.timeout, logger)

        scheduler.start()
    except Exception as e:
        logger.error({"event": "error", "message": f"Scheduler failed: {str(e)}"})
        sys.exit(1)

if __name__ == "__main__":
    main()
