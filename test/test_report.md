# cron-python v0.9.6 網羅的テストリポート

実行日時: Fri May  1 06:29:43 2026

| テストケース | 結果 | 詳細 |
| :--- | :--- | :--- |
| 柔軟な引数解析 (後ろにフラグ) | PASS | Output contained flex_test: True |
| セパレーター (--) による分離 | PASS | Output contained --once-string: True |
| タイムアウト強制終了 | PASS | Exit Code: 3 |
| 5フィールドCron実行 (1分) | PASS | Hit found: True, Elapsed: 75s |
| 相互排他バリデーション | FAIL | Failed to reject |
