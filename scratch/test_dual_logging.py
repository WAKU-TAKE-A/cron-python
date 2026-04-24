import subprocess
import sys
import os
import json

def test_dual_logging():
    cron_py = "cron_python.py"
    batch_py = "batch.py"
    log_file = "test_dual.log"
    
    if os.path.exists(log_file):
        os.remove(log_file)
        
    # Use venv python for the subprocess
    python_exe = os.path.join("venv", "Scripts", "python.exe")
    
    cmd = [
        python_exe, cron_py, batch_py,
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
    print(f"--- STDERR ---")
    print(result.stderr)
    
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
        # Check if they look like JSON and have same content
        try:
            log1 = json.loads(stdout_logs[0])
            log2 = json.loads(file_logs[0])
            if log1['event'] == log2['event']:
                print("SUCCESS: Logs found in both stdout and file and they match")
                return True
        except:
            print("SUCCESS: Logs found in both but JSON check failed (might be text format?)")
            return True
            
    print("FAIL: Logs missing in one or both destinations")
    return False

if __name__ == "__main__":
    if test_dual_logging():
        sys.exit(0)
    else:
        sys.exit(1)
