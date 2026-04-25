import subprocess
import json
import os
import time
import shutil
import sys
import signal

TEST_DIR = "c:/tmp/cron-python/test/run"
CRON_PYTHON = "c:/tmp/cron-python/cron_python.py"
TARGET_TOOL = "c:/tmp/cron-python/test/target_tool.py"

def setup_test_env():
    if os.path.exists(TEST_DIR):
        shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

def run_cmd(args):
    # v0.9.6 では順序不問なのでシンプルに結合可能
    full_cmd = [sys.executable, CRON_PYTHON] + args
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=120)

def run_async(args):
    full_cmd = [sys.executable, CRON_PYTHON] + args
    return subprocess.Popen(full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

def main():
    setup_test_env()
    results = []

    print("--- v0.9.6 網羅的テスト開始 ---")

    # Case 1: 柔軟な引数順序 (--once を後ろに)
    print("Test 1: Flexible Argument Order (flag at the end)...")
    res = run_cmd([TARGET_TOOL, "echo", "flex_test", "--once", "--log-format", "json"])
    has_flex = "flex_test" in res.stdout
    results.append({
        "case": "柔軟な引数解析 (後ろにフラグ)",
        "result": "PASS" if has_flex and res.returncode == 0 else "FAIL",
        "detail": f"Output contained flex_test: {has_flex}"
    })

    # Case 2: セパレーター (--) の使用
    print("Test 2: Separator (--) usage...")
    # ターゲットスクリプトに "--once" という文字列を引数として渡す（ツールのフラグとして解釈させない）
    res = run_cmd(["--once", "--log-format", "json", TARGET_TOOL, "--", "echo", "--once-string"])
    has_string = "--once-string" in res.stdout
    results.append({
        "case": "セパレーター (--) による分離",
        "result": "PASS" if has_string else "FAIL",
        "detail": f"Output contained --once-string: {has_string}"
    })

    # Case 3: タイムアウト
    print("Test 3: Timeout Handling...")
    res = run_cmd(["--once", "--timeout", "1", TARGET_TOOL, "sleep", "5"])
    results.append({
        "case": "タイムアウト強制終了",
        "result": "PASS" if res.returncode == 3 else "FAIL",
        "detail": f"Exit Code: {res.returncode}"
    })

    # Case 4: 5フィールド Cron (1分待機)
    print("Test 4: 5-field Cron (1 min wait)...")
    print("  ※ 実際に1分以上待機します。少々お待ちください...")
    # 毎分実行
    p = run_async([TARGET_TOOL, "--cron", "* * * * *", "--log-format", "json", "echo", "min_hit"])
    
    # 1分間 + アルファ待機（次の00秒を跨ぐまで）
    start_wait = time.time()
    # 75秒待てば確実に次の「分」のトリガーが引かれる
    time.sleep(75)
            
    p.terminate() 
    out, _ = p.communicate()
    hit_found = "min_hit" in out
    # Windowsのterminateは強制終了なためshutdownログは出ないが、cron実行自体は確認可能
    
    results.append({
        "case": "5フィールドCron実行 (1分)",
        "result": "PASS" if hit_found else "FAIL",
        "detail": f"Hit found: {hit_found}, Elapsed: {round(time.time()-start_wait)}s"
    })

    # Case 5: 相互排他グループチェック (エラーになるべき)
    print("Test 5: Mutually Exclusive Group (cron + once)...")
    res = run_cmd([TARGET_TOOL, "--cron", "* * * * *", "--once"])
    is_error = res.returncode != 0 and "not allowed with argument" in res.stderr
    results.append({
        "case": "相互排他バリデーション",
        "result": "PASS" if is_error else "FAIL",
        "detail": "Correctly rejected cron + once" if is_error else "Failed to reject"
    })

    # レポート生成
    print("\n--- テストレポート作成中 ---")
    report = "# cron-python v0.9.6 網羅的テストリポート\n\n"
    report += f"実行日時: {time.ctime()}\n\n"
    report += "| テストケース | 結果 | 詳細 |\n"
    report += "| :--- | :--- | :--- |\n"
    for r in results:
        report += f"| {r['case']} | {r['result']} | {r['detail']} |\n"
    
    with open("c:/tmp/cron-python/test/test_report.md", "w", encoding="utf-8") as f:
        f.write(report)
    
    print("レポートを c:/tmp/cron-python/test/test_report.md に保存しました。")

if __name__ == "__main__":
    main()
