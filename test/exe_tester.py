import subprocess
import json
import os
import time
import shutil
import sys
import signal

TEST_DIR = "c:/tmp/cron-python/test/run"
# テスト対象を EXE に変更
CRON_EXE = "c:/tmp/cron-python/dist/cron_python.exe"
TARGET_TOOL = "c:/tmp/cron-python/test/target_tool.py"

def setup_test_env():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

def run_cmd(args):
    # 直接 EXE を起動
    full_cmd = [CRON_EXE] + args
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=120)

def run_async(args):
    full_cmd = [CRON_EXE] + args
    return subprocess.Popen(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main():
    setup_test_env()
    results = []

    print("--- [EXE版] v0.9.6 網羅的テスト開始 ---")

    # Case 1: 柔軟な引数順序 (--once を後ろに)
    print("Test 1: Flexible Argument Order (flag at the end)...")
    res = run_cmd([TARGET_TOOL, "echo", "exe_flex_test", "--once", "--log-format", "json"])
    has_flex = "exe_flex_test" in res.stdout
    results.append({
        "case": "[EXE] 柔軟な引数解析",
        "result": "PASS" if has_flex and res.returncode == 0 else "FAIL",
        "detail": f"Output contained exe_flex_test: {has_flex}"
    })

    # Case 2: タイムアウト
    print("Test 2: Timeout Handling...")
    res = run_cmd(["--once", "--timeout", "1", TARGET_TOOL, "sleep", "5"])
    results.append({
        "case": "[EXE] タイムアウト強制終了",
        "result": "PASS" if res.returncode == 3 else "FAIL",
        "detail": f"Exit Code: {res.returncode}"
    })

    # Case 3: 5フィールド Cron (1分待機)
    print("Test 3: 5-field Cron (1 min wait)...")
    print("  ※ 実際に1分以上待機します...")
    p = run_async([TARGET_TOOL, "--cron", "* * * * *", "--log-format", "json", "echo", "exe_min_hit"])
    time.sleep(75)
    p.terminate() 
    out, _ = p.communicate()
    hit_found = "exe_min_hit" in out
    
    results.append({
        "case": "[EXE] 5フィールドCron実行",
        "result": "PASS" if hit_found else "FAIL",
        "detail": f"Hit found: {hit_found}"
    })

    # レポート生成
    print("\n--- [EXE版] テストレポート作成中 ---")
    report = "# cron-python v0.9.6 EXE版テストリポート\n\n"
    report += f"実行日時: {time.ctime()}\n\n"
    report += "| テストケース | 結果 | 詳細 |\n"
    report += "| :--- | :--- | :--- |\n"
    for r in results:
        report += f"| {r['case']} | {r['result']} | {r['detail']} |\n"
    
    with open("c:/tmp/cron-python/test/exe_test_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    print("レポートを c:/tmp/cron-python/test/exe_test_report.md に保存しました。")

if __name__ == "__main__":
    main()
