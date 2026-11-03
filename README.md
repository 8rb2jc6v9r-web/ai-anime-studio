# AI Anime Studio（デモ版）

日本語の物語から、縦型 9:16 の2Dアニメ風MP4を作るスマホ対応Webアプリです。
**外部API不使用・無料**。主人公は物語ごとに固定の見た目で、全6シーンに登場します。

## スマホだけで動かす（GitHub Codespaces）
1. このフォルダをGitHubのリポジトリにアップロード
2. リポジトリ画面で **Code → Codespaces → Create codespace**
3. 準備が終わったら、ターミナルで `python app.py`
4. 表示される「ポート5000を開く」から画面を開く

## パソコンで動かす
```
pip install -r requirements.txt
# FFmpeg が必要（Windows: winget install ffmpeg / Mac: brew install ffmpeg）
python app.py   →  http://127.0.0.1:5000
```

## 公開する（Render等）
`Dockerfile` 入りなので、Renderの「Web Service（Docker）」にそのまま載せられます。

## 構成
- `app.py` … 台本分割・絵の描画・ナレーション・字幕・FFmpeg結合・進捗API
- `templates/index.html` … スマホ向け画面
- `.devcontainer/` … Codespaces用の自動セットアップ

## 注意
- ナレーションは `espeak-ng`（無料・機械的な声）。Codespacesでは自動で入ります。入っていない環境は無音になります。
- 生成した動画は `output/` に残ります（GitHubには上がりません）。
- 次の段階：台本=Claude、映像=Kling、声=高品質TTSに差し替え（前回の試作品に実装済み）。
