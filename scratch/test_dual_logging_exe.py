import subprocess
import sys
import os
import json

def test_dual_logging_exe():
    exe_path = r"dist\cron_python.exe"
    batch_py = "batch.py"
    log_file = "test_dual_exe.log"
    
    if os.path.exists(log_file):
        os.remove(log_file)
        
    cmd = [
        exe_path, batch_py,
        "--once",
        "--log-format", "json",
        "--log-dest", "file",
        "--log-file", log_file,
        "--", "{}"
    ]
    
    print(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(f"--- STDOUT ---")
    print(result.stdout)
    
    # Check stdout
    stdout_logs = [l for l in result.stdout.strip().split('\n') if l.strip()]
    print(f"STDOUT lines: {len(stdout_logs)}")
    
    # Check log file
    if not os.path.exists(log_file):
        print("FAIL: Log file not created")
        return False
        
    with open(log_file, 'r', encoding='utf-8') as f:
        file_logs = [l for l in f.read().strip().split('\n') if l.strip()]
    print(f"File lines: {len(file_logs)}")
    
    if len(stdout_logs) > 0 and len(file_logs) > 0:
        print("SUCCESS: Logs found in both stdout and file for EXE")
        return True
            
    print("FAIL: Logs missing in one or both destinations")
    return False

if __name__ == "__main__":
    if test_dual_logging_exe():
        sys.exit(0)
    else:
        sys.exit(1)
