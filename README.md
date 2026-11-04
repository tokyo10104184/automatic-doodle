# Android 4択クイズ自動解答外部ツール (QuizBot)

Android端末（Termux）単体で完結し、Gemini Vision APIを活用して画面上の4択クイズを自動で解き、正解選択肢を自動タップする外部ツールです。

---

## 1. 特徴
- **Android端末単体で完結**: PCを介さず、Android上のTermuxとローカルワイヤレスデバッグ（ADB）を利用して画面キャプチャ・タップを実行
- **Gemini Multimodal Vision API**: 画面スクリーンショットを直接送信し、問題文・選択肢・正解の判定・タップ座標特定を一括実行（OCR誤認識ゼロ）
- **連続ループモード**: クイズアプリを監視し、出題されると即座に正解を判断して自動タップ
- **シミュレータ＆モック機能内蔵**: 実機が手元にない環境でも動作確認・テストが容易
- **Dry-runモード**: 自動タップを行わず、解答候補とタップ座標の確認のみを行うセーフティモード完備

---

## 2. 動作環境・必要条件
- **Android端末**: Android 11以上推奨（ワイヤレスデバッグ対応）
- **Termuxアプリ**: F-DroidまたはGitHubからインストール
- **Google Gemini APIキー**: Google AI Studio（https://aistudio.google.com/）にて取得

---

## 3. Termuxでのセットアップ手順

### ステップ1: Termuxに必要なパッケージをインストール
Termuxを開き、以下のコマンドを実行します：
```bash
pkg update -y
pkg install -y python android-tools git
```

### ステップ2: 本リポジトリのクローンと依存パッケージのインストール
```bash
git clone <本リポジトリURL> quiz-bot
cd quiz-bot
pip install -r requirements.txt
```

### ステップ3: Android端末単体でのローカルADB接続（初回のみ）
1. Androidの **「設定」 > 「開発者向けオプション」** を開きます。
2. **「ワイヤレスデバッグ」** をONにします。
3. **「ペア設定コードでデバイスをペアリング」** をタップします。
   - 表示される「IPアドレスとポート」（例: `127.0.0.1:41234`）と「Wi-Fiペア設定コード」（6桁）を確認。
4. Termux上でペアリングを実行：
   ```bash
   adb pair 127.0.0.1:<表示されたペアリングポート>
   # プロンプトが出たら6桁のコードを入力
   ```
5. ワイヤレスデバッグのメイン画面に表示されているポート（例: `127.0.0.1:39876`）に対して接続：
   ```bash
   adb connect 127.0.0.1:<ワイヤレスデバッグのポート>
   ```
6. 接続確認：
   ```bash
   adb devices
   # 127.0.0.1:XXXXX device と表示されれば接続完了
   ```

---

## 4. 設定ファイルの準備

`config.example.yaml` をコピーして `config.yaml` を作成します：
```bash
cp config.example.yaml config.yaml
```

`config.yaml` を開き、取得したGemini APIキーとADBポートを設定します：
```yaml
gemini_api_key: "YOUR_GEMINI_API_KEY"
model_name: "gemini-2.5-flash"
device_mode: "termux_adb"
adb_host: "127.0.0.1"
adb_port: 39876  # ワイヤレスデバッグのポート番号

loop_interval_sec: 2.5
max_iterations: 0 # 0は無限ループ
dry_run: false
```
※ APIキーは環境変数 `export GEMINI_API_KEY="YOUR_KEY"` でも指定可能です。

---

## 5. 実行方法

### 連続ループモード（自動解答・タップ）
クイズアプリを画面に表示（画面分割またはフローティング、バックグラウンド起動など）した状態で実行します：
```bash
python src/quiz_bot.py
```
- クイズ画面を検出すると自動でGeminiが推論し、正解ボタンの座標をタップします。
- 終了するには `Ctrl + C` を押します。

### ドライランモード（タップせず解答と座標だけ表示）
安全にテストしたい場合：
```bash
python src/quiz_bot.py --dry-run
```

### 単発モード（現在の画面のみ1回解答）
```bash
python src/quiz_bot.py --once
```

### オフラインシミュレーションモード（端末・APIキー不要でテスト）
```bash
python tests/simulation_runner.py
# または
python src/quiz_bot.py --mock --once
```

---

## 6. テストの実行
```bash
pytest -v
```
全単体テストおよびパーサー・モックドライバーの検証がパスします。
