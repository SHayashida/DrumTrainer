# Drum Trainer CLI (Local MVP)

ドラム練習用の伴奏音源をローカルで生成する CLI です。指定した楽曲をボーカル/ドラム/ベース/その他に分離し、ドラムをミュート（または減衰）した伴奏とクリックを重ねた音源を作れます。BPM と拍位置も解析し `metadata.json` に保存します。

## 特長
- Demucs による高品質ステム分離（ローカル実行）
- BPM/ビート解析（librosa）
- クリック生成とオーディオ合成（pydub）
- すべてローカル完結の CLI

## 動作環境
- macOS (Apple Silicon/M2 含む) または Linux
- Python 3.10+
- FFmpeg（エンコード/デコードに使用）
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg` 等
- 初回のみ Demucs のモデルがダウンロードされます（オンライン）

> 法的注意: 入力音源は必ずユーザーが合法的に所持・処理可能な範囲で使用してください。自動ダウンロード等の機能は含みません。

## セットアップ
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Demucs 実行に PyTorch が必要です。環境によっては手動でのインストールが必要な場合があります。インストールに失敗する場合は公式ドキュメントをご確認ください。

## ディレクトリ構成
```
project/
  app.py                # CLI 本体
  requirements.txt
  README.md
  .env.example          # 拡張用のダミー設定
  outputs/              # 実行時に生成（自動）
```

## 使い方
以下の3コマンドを提供します。

### 1) ステム分離
```bash
python app.py separate /path/to/song.wav \
  --model htdemucs \
  --out-dir ./outputs/<auto>
```
- 入力は `.wav/.mp3/.m4a` など。内部で `mix.wav`（44.1kHz/16bit/ステレオ）に正規化されます。
- Demucs を実行し `vocals.wav, drums.wav, bass.wav, other.wav` を出力します。
- 出力先の既定は `./outputs/<曲名>` です。

### 2) 解析（BPM/ビート）
```bash
python app.py analyze ./outputs/<song-name>/mix.wav
```
- `metadata.json` に `{"bpm": float, "beats": [seconds...]}` を保存します。
- 結果はテーブルでも表示します。

### 3) 伴奏生成（ドラムミュート＋クリック）
```bash
python app.py make-backing ./outputs/<song-name>/ \
  --auto-bpm \
  --with-click \
  --drum-gain -120   # 完全ミュート。-24 等で減衰に変更可能 \
  --mp3              # 任意: MP3 も出力
```
- `vocals+bass+other(+drums[gain])` を合成し `backing.wav` を生成します。
- `--auto-bpm` 指定時は `metadata.json` のビート、なければオンザフライで推定します。
- `--bpm` を指定すると固定テンポのクリックを生成できます（`--auto-bpm` なしの場合）。

## 受け入れ基準（目安）
- 1曲を通してクラッシュせず完走
- `backing.wav` が明瞭にドラム無/減衰で再生できる
- `metadata.json` に `bpm` と `beats`（秒）が保存される
- README から初見で 5 分以内に実行できる

## トラブルシューティング
- Demucs 失敗: PyTorch のインストールやモデルDLに失敗している可能性。`pip show demucs` と PyTorch の導入を確認。
- FFmpeg 未導入: 変換や MP3 出力に失敗します。`ffmpeg -version` で確認し、インストールしてください。
- オーディオ歪み: 入力クリップが大きい場合があります。`--drum-gain` を調整、生成後に正規化（本CLIは -1dBFS 付近に調整）。
- 出力が見つからない: `./outputs/<song>/` 以下に `mix.wav` と 4 stems が揃っているか確認。

### Windows 補足
- PowerShell の仮想環境有効化で止まる: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned -Force` 実行後、`\.venv\Scripts\Activate.ps1` を再実行。
- FFmpeg の導入: `winget install Gyan.FFmpeg`（または Chocolatey: `choco install ffmpeg`）。インストール後に新しい PowerShell を開き、`where ffmpeg` で PATH 認識を確認。
- demucs コマンドが無い: 本CLIは `python -m demucs` に自動フォールバックします。`pip install -r requirements.txt` 済みであればOK。
- torch が無い/失敗: `pip install torch torchvision torchaudio`（CPUのみで十分）。失敗する場合は公式手順に従ってください。

### クイック検証（Windows）
```powershell
python -m venv .venv
 .\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
python app.py separate "C:\\path\\to\\song.mp3" --model htdemucs
python app.py analyze .\outputs\<曲名>\mix.wav
python app.py make-backing .\outputs\<曲名>\ --auto-bpm --with-click --drum-gain -120 --mp3
```

### 検証チェックリスト
- `vocals.wav/drums.wav/bass.wav/other.wav` が存在し再生できる
- `metadata.json` に `bpm` と `beats`（秒）が保存される
- `backing.wav` でドラムがミュート/減衰し、クリックが一定間隔で鳴る

## 今後の拡張
- AB ループ、段階テンポ、+/-3% 反復練習
- GUI（PySide6）での再生・ループ・ゲイン調整
- Rubber Band による高品質ストレッチ/移調
- ワーカー化（Celery/Redis）でのバッチ処理

---
このリポジトリはローカル実行を前提としています。バグ報告や改善提案は歓迎です。
