import os
import threading
import time

from cron_python import ManagedScriptRunner

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TARGET_TOOL = os.path.join(ROOT_DIR, "test", "target_tool.py")

class DummyLogger:
    def log(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass

def test_stop_unblocks_wait_for_completion():
    logger = DummyLogger()
    runner = ManagedScriptRunner(TARGET_TOOL, ["heartbeat", "0.1"], timeout=None, logger=logger)
    
    runner.start()
    time.sleep(1)  # Let it run a bit and output some heartbeats
    
    # We call stop in another thread so we can time wait_for_completion from the main thread
    def stopper():
        time.sleep(0.5)
        runner.stop()
        
    threading.Thread(target=stopper, daemon=True).start()
    
    start = time.time()
    # wait_for_completion should return soon after stopper calls stop
    runner.wait_for_completion()
    duration = time.time() - start
    
    # Normally it should take ~0.5s for the stopper to trigger, and wait_for_completion 
    # should return almost immediately after stop() is called, thanks to stdout.close()
    assert duration < 3.0, f"Wait for completion took too long: {duration}s"
