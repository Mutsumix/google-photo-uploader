# Google Photo Uploader

カメラで撮影した画像を自動で Google Photos にアップロードするシステムです。

## 概要

このプロジェクトは、定期的にカメラで写真を撮影し、Google Photos API を使用して指定したアルバムに自動アップロードします。Google Photos API の認証エラー時には、AWS SNS を通じてメール通知を送信し、ディスク容量を圧迫する無限リトライを防ぎます。

## 主な機能

- **自動撮影**: 設定したスケジュールで自動的に写真撮影
- **Google Photos 連携**: 撮影した写真を指定アルバムに自動アップロード
- **認証エラー通知**: Google Photos API 認証切れ時の AWS SNS 通知
- **ログ管理**: ローテーション機能付きログシステム
- **エラー処理**: 認証エラー時の適切な処理とプログラム終了

## セットアップ

### 1. 依存関係のインストール

```bash
pip install -r requirements.txt
```

### 2. 設定ファイルの準備

```bash
# サンプル設定をコピー
cp config.sample.yaml config.yaml

# 設定ファイルを編集
vi config.yaml
```

### 3. Google Photos API 設定

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成
2. Photos Library API を有効化
3. OAuth 2.0 認証情報を作成し、`client_secrets.json`として保存
4. 初回認証セットアップを実行:

```bash
# 基本認証のみ
python setup_auth.py

# カメラテスト + アップロードテスト
python setup_auth.py --test-camera --test-upload
```

### 4. AWS SNS 設定（オプション）

認証エラー通知を使用する場合：

1. AWS SNS トピックを作成
2. メール通知を設定
3. `config.yaml`にトピック ARN を設定
4. AWS 認証情報を設定（AWS CLI、IAM ロール等）

## 設定ファイル

### config.yaml

```yaml
camera:
  use: true # カメラ機能の有効/無効
  photo_dir: "photos" # 一時保存ディレクトリ
  settings:
    width: 1920 # 撮影解像度（幅）
    height: 1080 # 撮影解像度（高さ）
    fourcc: "MJPG" # コーデック
    fps: 30 # フレームレート
    focus: 30 # フォーカス設定
  scheduler:
    day_of_week: "mon-sun" # 撮影曜日
    at_time: "09:00" # 撮影時刻

google_photos:
  use: true # Google Photos機能の有効/無効
  client_secrets_path: "client_secrets.json" # OAuth認証情報
  token_path: "photo_token.json" # アクセストークン
  album_title: "aeroponics" # アップロード先アルバム名

notifications:
  aws_sns:
    use: true # SNS通知の有効/無効
    region: "ap-northeast-1" # AWSリージョン
    topic_arn: "arn:aws:sns:ap-northeast-1:XXXXXXXXXX:your-topic" # SNSトピックARN
    subject: "[Alert] Google Photo Authentication Error" # 通知件名
    message_body: "Google Photo authentication has expired." # 通知本文
```

## 使用方法

### 基本実行

```bash
python main.py
```

### バックグラウンド実行

```bash
# nohupを使用
nohup python main.py > /dev/null 2>&1 &

# systemdサービスとして実行（推奨）
sudo systemctl start google-photo-uploader
```

### ログ確認

```bash
# 最新ログ
tail -f logs/google_photo_uploader.log

# ログ一覧
ls -la logs/
```

## ディレクトリ構造

```
google-photo-uploader/
├── main.py                 # メインプログラム
├── camera_module.py        # カメラ制御モジュール
├── google_photos.py        # Google Photos APIクライアント
├── config.yaml            # 設定ファイル（要作成）
├── config.sample.yaml     # 設定サンプル
├── requirements.txt       # Python依存関係
├── client_secrets.json    # OAuth認証情報（要作成）
├── photo_token.json       # アクセストークン（自動生成）
├── photos/                # 一時画像保存（自動作成）
├── logs/                  # ログファイル（自動作成）
└── README.md              # このファイル
```

## トラブルシューティング

### カメラが認識されない

```bash
# カメラデバイスの確認
ls /dev/video*

# OpenCVでのカメラテスト
python -c "import cv2; print(cv2.VideoCapture(0).isOpened())"
```

### 画像が低解像度（640x480）で撮影される

USB UVCカメラで高解像度撮影ができない場合、ビデオフォーマットの問題が原因の可能性があります。

**原因**: OpenCVはデフォルトでYUYVフォーマットを使用しますが、多くのUSBカメラでYUYVは低解像度（640x480）のみサポートしています。

**解決方法**: 
1. サポートされている解像度とフォーマットを確認:
```bash
v4l2-ctl -d /dev/video2 --list-formats-ext
```

2. MJPGフォーマットが1920x1080をサポートしている場合、設定で明示的にMJPGを指定:
```yaml
camera:
  settings:
    fourcc: "MJPG"  # 重要: 高解像度にはMJPGが必要
    width: 1920
    height: 1080
```

**技術的詳細**: 
- YUYVフォーマット: 通常640x480まで
- MJPGフォーマット: 高解像度（1080p, 4K）対応
- カメラモジュールは自動的にフェイルセーフとしてMJPGを設定

### Google Photos 認証エラー

1. `photo_token.json`を削除
2. プログラムを再実行して再認証
3. ブラウザで認証フローを完了

### AWS SNS 通知が届かない

1. AWS 認証情報の確認
2. SNS トピックの存在確認
3. メール購読の確認（未確認の場合は確認メールをチェック）

## 開発情報

### 依存関係

- **OpenCV**: カメラ制御
- **Google API Client**: Google Photos API
- **boto3**: AWS SNS 通知
- **PyYAML**: 設定ファイル解析
- **schedule**: タスクスケジューリング

### ログレベル

- **INFO**: 正常な動作ログ
- **WARNING**: 警告（継続可能なエラー）
- **ERROR**: エラー（処理中断）
- **CRITICAL**: 致命的エラー（プログラム終了）

## 貢献

バグ報告や機能要望は、GitHub の Issue でお知らせください。プルリクエストも歓迎します。
