# cron-python

本プロジェクトは、AIコーディングアシスタント **Antigravity** によって自動生成された、プロダクション対応のPythonスクリプト・スケジューラーです。

`cron-python` は、Cron式を用いて指定したPythonスクリプトをスケジュール実行し、構造化されたJSONログを出力します。プロセス実行のタイムアウトによる子プロセスを含めた完全なキル機能（Windowsネイティブの `taskkill /T /F`）を備えており、AIによる自動テスト・システム監視への統合を強力にサポートします。

> [!WARNING]
> **This tool is Windows-only. Linux/macOS is not supported.**
> Windowsネイティブのプロセス管理機能（`taskkill`、`CREATE_NEW_PROCESS_GROUP`）に依存しているため、他のOSでは動作しません。

---

## 🚀 特徴
- **スケジュール実行**: `APScheduler` によるCronベースの定期実行制御。
- **堅牢なタイムアウト管理**: タイムアウト時間を超過した場合、Windows配下の子孫プロセスごと一括で強制終了します。
- **構造化ロギング**: AIフレンドリーな形式（JSONフォーマット）で、開始・終了・ストリーム出力等のイベントを捕捉し、システム監視への統合を容易にします。
- **柔軟な引数受渡**: CLIオプションと対象スクリプトの引数を安全に分離し、任意の引数やパラメーターを渡すことができます。

---

## 📦 機能・仕様と使い方

### CLI 基本フォーマット
`cron-python` は引数の順序を問いません。以下のいずれの形式でも実行可能です。

```powershell
# 標準的な書き方
cron_python.exe --cron "*/5 * * * *" script.py arg1 arg2

# オプションを後ろに置く書き方
cron_python.exe script.py arg1 arg2 --cron "*/5 * * * *"

# 引数が曖昧になる場合（スクリプトの引数を確実に分離する）
cron_python.exe script.py --cron "*/5 * * * *" -- arg1 arg2
```

### 主要なオプション
| 引数 | 説明 |
|---|---|
| `<script>` | 実行対象のターゲットとなるPythonスクリプトパス |
| `--cron` | 定期実行するCron式（5フィールドまたは6フィールド）。`--once` および `--window-start-cron` / `--window-end-cron` と同時指定不可。 |
| `--once` | スケジュール実行を無視して1回のみ即時実行します。`--cron` および `--window-start-cron` / `--window-end-cron` と同時指定不可。 |
| `--window-start-cron` | 常駐系スクリプトを起動するCron式（5フィールドまたは6フィールド）。`--window-end-cron` と組で使います。 |
| `--window-end-cron` | 常駐系スクリプトを停止するCron式（5フィールドまたは6フィールド）。`--window-start-cron` と組で使います。 |
| `--run-on-start` | `--cron` または `--window-start-cron` / `--window-end-cron` モードで、最初のトリガーを待たずに起動直後にまず1回開始します。 |
| `--exit-on-script-error` | ターゲットスクリプトが非0終了コードを返したら cron-python も終了します。デフォルトでは終了せず、次回スケジュールを待ちます。 |
| `--version` | バージョン情報を表示して終了します。 |
| `--timeout` | スクリプトの実行タイムアウト（秒）。超過時は強制キルを実行します。 |
| `--log-format` | ログ形式を指定します。`text` または `json`。デフォルトは `text`。 |
| `--log-dest` | ログの出力先。`stdout`, `file`, `none`。デフォルトは `stdout`。`file` 指定時もコンソールに同時出力されます。 |
| `--log-file` | `--log-dest file` 指定時の出力先ファイルパス。 |
| `--log-max-bytes` | ログファイルの最大サイズ（バイト数）。超過すると別ファイルへローテーション保存します（デフォルト: `1048576` / 1MB）。 |
| `--log-backup-count` | 保存しておく過去のローテーションログの最大ファイル数（デフォルト: `10`）。 |
| `--log-stdout` | `true` を指定すると標準出力へのロギングを強制します（デフォルト: `false`）。 |
| `--log-stderr` | `true` を指定すると標準エラー出力へのロギングを強制します（デフォルト: `false`）。 |

### Cron式の指定方法
本ツールは標準的な Unix/Linux の Crontab 形式（5フィールド）に加え、**秒単位の指定が可能な拡張形式（6フィールド）**をサポートしています。

#### 5フィールド形式 (標準)
```text
.---------------- 分 (0 - 59)
| .-------------- 時 (0 - 23)
| | .------------ 日 (1 - 31)
| | | .---------- 月 (1 - 12)
| | | | .-------- 曜日 (0 - 6) (0=日曜日)
| | | | |
* * * * *
```

#### 6フィールド形式 (拡張 - 秒単位)
高頻度な実行が必要な場合、先頭に「秒」を追加した6つのフィールドで指定できます。
```text
.------------------ 秒 (0 - 59)
| .---------------- 分 (0 - 59)
| | .-------------- 時 (0 - 23)
| | | .------------ 日 (1 - 31)
| | | | .---------- 月 (1 - 12)
| | | | | .-------- 曜日 (0 - 6) (0=日曜日)
| | | | | |
* * * * * *
```

#### 特殊記号の利用
範囲や間隔を指定することで、柔軟なスケジュール設定が可能です。

| 記法 | 意味 | 使用例 |
| :--- | :--- | :--- |
| `*` | すべての値 | 毎分、毎時など |
| `-` | 範囲指定 | `10-12` (10, 11, 12時) |
| `,` | リスト指定 | `1,3,5` (月, 水, 金曜日) |
| `/` | ステップ（間隔）指定 | `*/10` (10分おき) |

#### 指定例

- **5分おきに実行**
  `*/5 * * * *`
- **毎日午前9時に実行**
  `0 9 * * *`
- **特定の時間帯での繰り返し（例：10:00～11:59の間に5分おき）**
  `*/5 10-11 * * *`
- **曜日の範囲指定（例：月曜～水曜の午前9時）**
  `0 9 * * 1-3`
- **平日の日中（月〜金、9時〜17時）に2時間おきに実行**
  `0 9-17/2 * * 1-5`
- **毎月1日と15日の正午に実行**
  `0 12 1,15 * *`


### 実行例

#### 1. 定期スケジュール（Cron）での実行
5分ごとに実行。ログをJSON形式で標準出力に表示し、対象スクリプトには `input=data.csv` を渡す場合：
```powershell
cron_python.exe batch.py --cron "*/5 * * * *" --timeout 60 --log-format json --log-dest stdout -- input=data.csv
```

#### 2. 即時実行モードによるテスト（1回だけ実行）
```powershell
cron_python.exe batch.py --once --log-format json -- duration=3
```

#### 3. 常駐スクリプトを開始/終了のCronで管理
```powershell
cron_python.exe ve_execute.py --window-start-cron "0 10 * * *" --window-end-cron "0 15 * * *"
```

---

## 📊 出力仕様 (JSON ログフォーマット)

JSONフォーマット（`--log-format json`）を指定した場合、以下のようなイベントログが出力されます。AI等の機械学習システムでリアルタイムにパース・監視するのに最適です。

**成功時の例 (`exit_code: 0`)**:
```json
{"event": "startup", "message": "cron-python is starting", "version": "0.9.4"}
{"event": "job_started", "script": "batch.py", "params": ["duration=1"]}
{"event": "script_output", "stream": "stdout", "message": "Received arguments: ['duration=1']"}
{"event": "script_output", "stream": "stdout", "message": "Work completed successfully."}
{"event": "job_finished", "status": "success", "exit_code": 0, "duration_sec": 1.062}
```

**タイムアウト発生時の例 (`exit_code: 3`)**:
```json
{"event": "startup", "message": "cron-python is starting", "version": "0.9.4"}
{"event": "job_started", "script": "batch.py", "params": ["duration=5"]}
{"event": "job_finished", "status": "timeout", "exit_code": 3, "duration_sec": 1.129}
```
---

## 🔨 PyInstallerによるビルド方法

コードを1つの実行ファイル（`.exe`）に纏める際は以下を実行してください。
※ 仮想環境（`venv`）内でビルドすることを強く推奨します。（理由は History.md 参照）

```powershell
# 1. 仮想環境の構築とアクティベート (Windows)
python -m venv venv
.\venv\Scripts\activate

# 2. 依存パッケージのインストール
pip install -r requirements.txt

# 3. ビルド
PyInstaller --onefile cron_python.py
```
完了後、`dist/cron_python.exe` が生成されます。

---

## 🎨 クレジット・謝辞

本アプリケーションの実行ファイル（`.exe`）に組み込まれているアイコンは、以下の素材を使用しています。ありがとうございます。

* <a href="https://www.flaticon.com/free-icons/routine" title="routine icons">Routine icons created by Awicon - Flaticon</a>
