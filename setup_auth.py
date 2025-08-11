#!/usr/bin/env python3
"""
Google Photos API 初回認証セットアップスクリプト

このスクリプトは以下を実行します：
1. Google Photos APIの初回認証
2. トークンファイルの生成
3. 認証テスト（アルバム一覧取得）
4. オプション：テスト画像のアップロード

使用方法:
    python setup_auth.py
    python setup_auth.py --test-upload  # テスト画像もアップロード
"""

import os
import sys
import yaml
import argparse
from pathlib import Path
from google_photos import GooglePhotos
from camera_module import CameraModule

def main():
    parser = argparse.ArgumentParser(description='Google Photos API 初回認証セットアップ')
    parser.add_argument('--config', default='config.yaml', help='設定ファイルパス')
    parser.add_argument('--test-upload', action='store_true', help='テスト画像のアップロードも実行')
    parser.add_argument('--test-camera', action='store_true', help='カメラテスト撮影も実行')
    args = parser.parse_args()

    print("Google Photos API 初回認証セットアップを開始します...")

    # 設定ファイル確認
    if not os.path.exists(args.config):
        print(f"ERROR: 設定ファイルが見つかりません: {args.config}")
        print("   config.sample.yaml をコピーして config.yaml を作成してください。")
        sys.exit(1)

    # 設定読み込み
    with open(args.config) as f:
        config = yaml.safe_load(f)

    # 必要なディレクトリ作成
    os.makedirs(config['camera']['photo_dir'], exist_ok=True)

    # client_secrets.json確認
    client_secrets_path = config['google_photos']['client_secrets_path']
    if not os.path.exists(client_secrets_path):
        print(f"ERROR: OAuth認証ファイルが見つかりません: {client_secrets_path}")
        print("   Google Cloud Consoleで作成したclient_secrets.jsonをプロジェクトルートに配置してください。")
        sys.exit(1)

    print(f"OK: 設定ファイル読み込み完了: {args.config}")
    print(f"OK: OAuth認証ファイル確認完了: {client_secrets_path}")

    # Google Photos クライアント初期化
    google_photos_client = GooglePhotos(
        config['google_photos']['client_secrets_path'],
        config['google_photos']['token_path']
    )

    try:
        print("\nGoogle Photos API認証を開始します...")
        print("   ブラウザが開かない場合は、表示されるURLにアクセスしてください。")

        # 認証テスト（アルバム一覧取得）
        album_list = google_photos_client.get_album_list()
        print(f"OK: 認証成功 アルバム数: {len(album_list)}")

        # トークンファイル確認
        token_path = config['google_photos']['token_path']
        if os.path.exists(token_path):
            print(f"OK: トークンファイル生成完了: {token_path}")

        # 対象アルバム確認・作成
        album_title = config['google_photos']['album_title']
        album = google_photos_client.get_album(album_title)
        if album:
            print(f"OK: 対象アルバム確認完了: '{album_title}' (ID: {album['id']})")
            album_id = album['id']
        else:
            print(f"INFO: 対象アルバム '{album_title}' が見つかりません。新規作成します...")
            album_id = google_photos_client.create_album(album_title)
            print(f"OK: アルバム作成完了: '{album_title}' (ID: {album_id})")

    except Exception as e:
        print(f"ERROR: Google Photos API認証に失敗しました: {e}")
        sys.exit(1)

    # カメラテスト
    if args.test_camera and config['camera']['use']:
        try:
            print(f"\nカメラテスト撮影を実行します...")
            camera_module = CameraModule()
            test_image_path = f"{config['camera']['photo_dir']}/setup_test.jpg"

            result = camera_module.save_photo(test_image_path, config['camera']['settings'])
            if result:
                print(f"OK: カメラテスト撮影完了: {test_image_path}")

                if args.test_upload:
                    print(f"テスト画像をGoogle Photosにアップロードします...")
                    upload_result = google_photos_client.upload_image(album_id, test_image_path)
                    if upload_result:
                        print(f"OK: テスト画像アップロード完了")
                        os.remove(test_image_path)
                        print(f"INFO: テスト画像を削除しました")
                    else:
                        print(f"ERROR: テスト画像アップロードに失敗しました")
            else:
                print(f"ERROR: カメラテスト撮影に失敗しました")

        except Exception as e:
            print(f"ERROR: カメラテストに失敗しました: {e}")

    # テストアップロード（既存画像）
    elif args.test_upload:
        print(f"\n既存画像でアップロードテストを実行します...")
        photo_dir = Path(config['camera']['photo_dir'])
        image_files = list(photo_dir.glob('*.jpg')) + list(photo_dir.glob('*.png'))

        if image_files:
            test_image = image_files[0]
            print(f"   テスト画像: {test_image}")
            upload_result = google_photos_client.upload_image(album_id, str(test_image))
            if upload_result:
                print(f"OK: テストアップロード完了")
            else:
                print(f"ERROR: テストアップロードに失敗しました")
        else:
            print(f"WARNING: テスト用画像が見つかりません（{photo_dir}/*.jpg, *.png）")

    print(f"\nセットアップ完了")
    print(f"   これで 'python main.py' を実行できます。")

    # 次のステップ案内
    print(f"\n次のステップ:")
    print(f"   1. 設定確認: vi {args.config}")
    print(f"   2. メイン実行: python main.py")
    print(f"   3. ログ確認: tail -f logs/main.log")

if __name__ == "__main__":
    main()
