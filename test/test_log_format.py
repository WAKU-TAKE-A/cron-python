import os
import time

from cron_python import ManagedScriptRunner

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_TOOL = os.path.join(ROOT_DIR, "test", "target_tool.py")

class ListLogger:
    def __init__(self):
        self.records = []
    def log(self, level, msg, *args, **kwargs):
        self.records.append(msg)
    def info(self, msg, *args, **kwargs):
        self.records.append(msg)
    def warning(self, msg, *args, **kwargs):
        self.records.append(msg)
    def error(self, msg, *args, **kwargs):
        self.records.append(msg)

def test_log_event_name_is_script_output():
    logger = ListLogger()
    # Execute an echo command
    runner = ManagedScriptRunner(TARGET_TOOL, ["echo", "hello_test"], timeout=5, logger=logger)
    runner.start()
    runner.wait_for_completion()
    
    # Check that at least one log entry has event = "script_output"
    # and that its message contains the echoed string.
    script_output_events = [r for r in logger.records if isinstance(r, dict) and r.get("event") == "script_output"]
    
    assert len(script_output_events) > 0, "No script_output event found in logs"
    assert script_output_events[0]["stream"] == "stdout", "Stream should be stdout"
    assert "hello_test" in script_output_events[0]["message"], "Output message missing"
