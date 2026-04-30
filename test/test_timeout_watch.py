import os
import time

from cron_python import ManagedScriptRunner, EXIT_SUCCESS, EXIT_TIMEOUT

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_TOOL = os.path.join(ROOT_DIR, "test", "target_tool.py")

class DummyLogger:
    def log(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass

def test_timeout_watch_exits_early_on_success():
    logger = DummyLogger()
    # sleep for 0.5s, timeout is 5s
    runner = ManagedScriptRunner(TARGET_TOOL, ["sleep", "0.5"], timeout=5, logger=logger)
    
    start = time.time()
    runner.start()
    
    exit_code = runner.wait_for_completion()
    duration = time.time() - start
    
    assert exit_code == EXIT_SUCCESS
    # Thread should not sleep for 5 seconds. The whole execution should be ~0.5-1.0s
    assert duration < 2.0, f"Took too long: {duration}s"

def test_timeout_watch_kills_on_timeout():
    logger = DummyLogger()
    # heartbeat runs forever, timeout is 2s
    runner = ManagedScriptRunner(TARGET_TOOL, ["heartbeat", "0.5"], timeout=2, logger=logger)
    
    start = time.time()
    runner.start()
    
    exit_code = runner.wait_for_completion()
    duration = time.time() - start
    
    assert exit_code == EXIT_TIMEOUT
    assert 1.5 <= duration < 4.0, f"Did not timeout correctly: {duration}s"
