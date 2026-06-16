# cron-python: AI Usage Guide

This document is an instruction manual for AI agents on how to **use and execute** `cron-python`. If you (the AI) need to schedule a Python script, manage a long-running process, or execute a background task on the user's Windows machine, read this guide to construct the correct commands.

## 1. What is cron-python?

`cron-python` is a robust Windows-native Python script scheduler. It provides features that are highly useful for AI agents:
*   **Process Tree Killing**: If a script times out, `cron-python` forcefully kills the target script and **all of its child processes**.
*   **Structured Output**: It can output logs in JSON format, making it easy for AIs to parse execution results, stdout/stderr streams, and exit codes.
*   **Cron Scheduling**: Supports 5-field and 6-field (second-level precision) cron expressions.

## 2. Execution Modes & Command Construction

You must choose exactly one execution mode. Below are the patterns you should use.

### A. Periodic Execution (Cron Mode)
Use this to run a script repeatedly at specific intervals.

**Command structure:**
```powershell
cron_python.exe <target_script.py> --cron "<cron_expression>" [options] -- <target_args...>
```
*   *Note: Always use `--` before the target script's arguments to ensure `cron-python` does not mistakenly parse them as its own options.*

**Example:** Run a data sync script every 5 minutes, pass `--verbose` to the script, and output JSON logs.
```powershell
cron_python.exe sync_data.py --cron "*/5 * * * *" --log-format json -- --verbose
```

### B. Time-Window Execution (Window Mode)
Use this to start a long-running script (e.g., a server, a resident bot) at a specific time, and forcefully terminate it at another time.

**Command structure:**
```powershell
cron_python.exe <target_script.py> --window-start-cron "<start_cron>" --window-end-cron "<end_cron>" [options] -- <target_args...>
```

**Example:** Start a scraper at 10:00 AM and forcefully kill it at 3:00 PM every day.
```powershell
cron_python.exe scraper.py --window-start-cron "0 10 * * *" --window-end-cron "0 15 * * *" --log-format json
```

### C. One-Off Execution (Once Mode)
Use this if you just want the robust process tree killing and JSON logging capabilities for a single run, without scheduling.

**Example:** Run a script once with a 60-second timeout.
```powershell
cron_python.exe risky_script.py --once --timeout 60 --log-format json
```

## 3. Options You Should Know

As an AI, you should utilize these flags to better manage the tasks you spawn:

*   `--log-format json`: **Highly Recommended.** Converts all `cron-python` logs and the target script's stdout/stderr into structured JSON lines. This makes it trivial for you to parse the outcome.
*   `--timeout <seconds>`: Forcefully kills the script and its children if it exceeds the specified time limit. Use this to prevent your automated tasks from hanging indefinitely.
*   `--run-on-start`: When using `--cron` or window modes, this flag immediately runs the target script once at startup instead of waiting for the first cron trigger.
*   `--log-dest <destination>`: `stdout`, `file`, `both`, or `none`. Use `file` or `both` with `--log-file <path>` if you are running this in the background and want to read the logs later.

## 4. Cron Expression Format

You can use standard 5-field cron, or a 6-field cron for second-level precision.

**5-Field (Standard)**
`Minute Hour Day Month Day-of-Week`
Example: `0 9 * * 1-5` (9:00 AM on weekdays)

**6-Field (Extended)**
`Second Minute Hour Day Month Day-of-Week`
Example: `*/10 * * * * *` (Every 10 seconds)

## 5. Important Notes for AI Execution

1.  **Blocking Process:** `cron-python.exe` is a blocking process. If you execute it directly in a terminal tool, it will block your tool until it is stopped. If you intend to leave it running in the background, use PowerShell's `Start-Process` and write logs to a file.
2.  **Windows Environment:** This tool relies on Windows native commands (`taskkill`). Do not attempt to use it on Linux/macOS environments.
3.  **Log Directory:** `cron-python` can create the log file, but the parent directory must already exist. Create it before starting a background process.
4.  **JSON Log Parsing:** If you use `--log-format json`, each line output to stdout or the log file will be a valid JSON object. Look for `"event": "job_finished"` to determine the `"exit_code"` and `"status"` ("success", "error", or "timeout").

**Background execution example:**
```powershell
New-Item -ItemType Directory -Force -Path ".\logs" | Out-Null
Start-Process -WindowStyle Hidden -FilePath ".\cron_python.exe" -ArgumentList 'worker.py --cron "*/5 * * * *" --log-format json --log-dest file --log-file ".\logs\worker.jsonl" -- --verbose'
```

After starting a background job, inspect the log file and parse JSON lines with `"event": "job_finished"` to confirm whether the target script succeeded, failed, or timed out.
