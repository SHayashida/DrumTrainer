## 役割 (Role)
あなたは**上級ソフトウェアエンジニア**です。Mac (Apple Silicon/M2) で動作する、**ドラム練習向けのカラオケ生成MVP**を、最短で安定稼働させることがミッションです。

## 目的 (Goal)
1. 任意の楽曲ファイル（ユーザーが合法的に所持）から**4ステム分離**（vocals/drums/bass/other）
2. **ドラムをミュート**（または減衰）し、**クリック**を重ねた**伴奏音源**を生成
3. **BPM/ビート解析**とメタデータ(JSON)を出力
4. すべて**ローカル**で完結する **CLI** と、わかりやすい **README** を作成

## スコープ (Scope)
- **必須**：CLIコマンド `separate` / `analyze` / `make-backing`
- **入出力**：
  - 入力：`song.wav`（または .mp3/.m4a を自動変換可）
  - 出力：`outputs/<song-name>/vocals.wav, drums.wav, bass.wav, other.wav, backing.wav, metadata.json`
- **品質**：
  - ドラム完全ミュートで不自然な場合に備え**減衰(dB)指定**を可能に
  - クリック音はビート位置に配置（`--auto-bpm`時）または一定BPM

## 非機能要件 (NFR)
- macOS (Apple Silicon) / Linux で動作
- Python 3.10+ / venv 前提
- 初回のみモデルDL（Demucs）。以降**完全オフライン**で動作
- 例外時の**明確なエラーメッセージ**、ログ（INFO/ERROR）

## 法務・利用上の前提 (Legal)
- 入力は**ユーザーが合法的に処理可能**な音源に限定
- YouTube等からの自動ダウンロードは**実装・同梱しない**

## 技術スタック (Tech)
- Separation: **Demucs** CLI（`htdemucs` 既定）
- Tempo/Beats: **librosa**（まずは十分）
- Audio I/O/Mix: `soundfile`, `pydub`, `ffmpeg-python`
- CLI: **Typer**
- 表示: **Rich**（テーブル/カラー出力）
- オプション：`pyrubberband`（将来の高品質ストレッチ用、MVPでは未必須）

## ディレクトリ構成 (Structure)
```
project/
  app.py                 # CLI本体
  requirements.txt
  README.md
  .env.example           # 将来拡張用
  outputs/               # 実行時に作成
```

## CLI 仕様 (Interface)
### 1) 分離
```
python app.py separate /path/to/song.wav \
  --model htdemucs \
  --out-dir ./outputs/<auto>
```
- Demucs を呼び出し、`vocals.wav, drums.wav, bass.wav, other.wav` を生成
- 失敗時は return code を反映し明示ログ

### 2) 解析（BPM/ビート）
```
python app.py analyze ./outputs/<song-name>/mix.wav
```
- BPM と beat times を推定、`metadata.json` に `{bpm, beats}` を保存
- Rich で結果をテーブル表示

### 3) 伴奏生成（ドラムミュート＋クリック）
```
python app.py make-backing ./outputs/<song-name>/ \
  --auto-bpm \
  --with-click \
  --drum-gain -120   # 完全ミュート。-24 などで薄く残す
  --mp3               # 任意、ffmpegがあればMP3も出力
```
- `vocals+bass+other(+drums[gain])` を合成
- クリックは `--auto-bpm` の場合 beat times に配置、未指定なら `--bpm` を必須に
- 出力：`backing.wav` / `backing.mp3(任意)`

## 受け入れ基準 (Acceptance)
- 1曲を通して**クラッシュせず**完走
- `backing.wav` が**明瞭にドラム無し**（または減衰）で再生でき、クリックが一定音量で聴こえる
- `metadata.json` に `bpm`（float）と `beats`（秒配列）が記録される
- README から**初見でも15分で実行**できる

## 実装のコツ (Notes)
- Demucs出力ディレクトリはモデル名を含むので、**固定パスにリネーム**して扱いやすく
- クリックは 20ms ホワイトノイズ×指数減衰の短音でOK（音割れ防止に正規化）
- **ラウドネス整合**：クリックは -6〜-9dB 目安でミックス
- 例外処理：ファイル欠損、ffmpeg 未導入、モデル未DL、サンプリングレート違い 等

## README に必須の内容 (Docs)
- venv セットアップ、`pip install -r requirements.txt`
- `demucs` 初回モデルDLの注意
- コマンド例（三本柱）と想定出力
- トラブルシューティング（遅い場合はCPU/GPU、drum-gainの推奨値、エラー例）

## 将来拡張 (Future)
- ABループ (`--ab 30 45`)、段階テンポアップ（ループ毎 +3%）
- GUI（PySide6）で再生・ループ・ゲイン調整
- Rubber Band による高品質ストレッチ/移調
- Web移行時：この CLI をワーカー化（Celery/Redis）し、同じ入出力契約を維持

---

### 出力すべきファイル
1. `app.py`（上記CLIを満たす実装）
2. `requirements.txt`（`demucs, librosa, soundfile, pydub, ffmpeg-python, typer, rich` 他）
3. `README.md`（セットアップと使用方法を具体的に）
4. `.env.example`（将来の設定用にダミー）

### 品質チェック項目（実装後に自己テスト）
- [ ] `separate` 後に `vocals.wav/drums.wav/bass.wav/other.wav` が存在
- [ ] `analyze` が BPM と beat count を表示し、`metadata.json` を保存
- [ ] `make-backing` で `backing.wav` が生成され、クリックが一定間隔で聴こえる
- [ ] `--drum-gain -24` などの値で音質差が確認できる
- [ ] 例外時のエラーメッセージが具体的

> 以上の仕様に沿って、**完全に動作するコード一式**と**README**を生成してください。

