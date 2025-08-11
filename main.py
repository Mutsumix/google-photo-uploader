import argparse
import os
import yaml
import schedule
import socket
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict, Optional
from datetime import datetime
from time import sleep

try:
    import boto3
except ImportError:
    boto3 = None

from camera_module import CameraModule
from google_photos import GooglePhotos

# ログ設定
def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
        
    logger.setLevel(logging.INFO)
    
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    file_handler = RotatingFileHandler(
        f'{log_dir}/main.log',
        maxBytes=10*1024*1024,
        backupCount=5
    )
    console_handler = logging.StreamHandler()
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

logger = setup_logger(__name__)


class Scheduler(object):
    def __init__(self, config: Dict) -> None:
        """Scheduler Job Object.

        Args:
            config: config yaml file data
        """
        self._config = config

        # Camera module
        if self.is_use_flag("camera"):
            self._camera_module = CameraModule()

        # Google Photos
        self._google_photos_client = GooglePhotos(
            self._config["google_photos"]["client_secrets_path"],
            self._config["google_photos"]["token_path"],
        )

    def is_use_flag(self, *args) -> bool:
        """Get whether the use flag is set.

        Args:
            *args: args

        Returns:
            A boolean if the use flag is set.
        """
        assert(len(args) >= 1), "args must be set to 1 or more."

        tmp_config = self._config
        for arg in args:
            tmp_config = tmp_config[arg]

        return tmp_config["use"]

    def camera_job(self) -> None:
        """Create the camera job to take a photo.
        """
        if not self.is_use_flag("camera"):
            return

        current_datetime = datetime.now().strftime("%Y%m%d_%H%M")
        photo_image_path = f"{self._config['camera']['photo_dir']}/camera_{current_datetime}.jpg"
        settings = self._config["camera"]["settings"]
        result = self._camera_module.save_photo(photo_image_path, settings)
        if not result or not self.is_use_flag("google_photos"):
            return

        try:
            album_id = self._get_album_id()
            self._google_photos_client.upload_image(album_id, photo_image_path)
            os.remove(photo_image_path)
        except Exception as e:
            if "invalid_grant" in str(e) or "expired" in str(e):
                # AWS通知API呼び出し
                self._send_auth_error_notification()
                # プログラム終了
                sys.exit(1)
            else:
                # その他のエラーはファイル削除のみ
                os.remove(photo_image_path)

        logger.info(f"Succeeded removed a photo. remove_path: {photo_image_path}")

    def _get_album_id(self) -> Optional[str]:
        """Get the target album id.

        Returns:
            Album ID
        """
        if not self.is_use_flag("google_photos"):
            return

        album_title = self._config["google_photos"]["album_title"]
        album = self._google_photos_client.get_album(album_title)
        if album:
            album_id = album["id"]
        else:
            album_id = self._google_photos_client.create_album(album_title)

        return album_id

    def _send_auth_error_notification(self) -> None:
        """Send an authentication error notification via AWS SNS."""
        if not self.is_use_flag("notifications", "aws_sns"):
            logger.error("Authentication error detected. Exiting program.")
            sys.exit(1)

        try:
            if boto3 is None:
                logger.error("boto3 not installed. Cannot send SNS notification.")
                logger.error("Authentication error detected. Exiting program.")
                sys.exit(1)

            # AWS SNS client
            sns = boto3.client(
                'sns',
                region_name=self._config["notifications"]["aws_sns"]["region"]
            )
            
            # デバイス識別情報を取得
            hostname = socket.gethostname()
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # メッセージ作成
            message = f"""
{self._config["notifications"]["aws_sns"]["message_body"]}

Details:
- Time: {current_time}
- Device: {hostname}
- Error: Google Photos API authentication expired
- Action Required: Renew OAuth token
            """
            
            # SNS publish
            response = sns.publish(
                TopicArn=self._config["notifications"]["aws_sns"]["topic_arn"],
                Subject=self._config["notifications"]["aws_sns"]["subject"],
                Message=message
            )
            
            logger.info(f"Auth error notification sent. MessageId: {response['MessageId']}")
            
        except Exception as e:
            logger.error(f"Failed to send auth error notification: {e}")
        
        logger.error("Authentication error detected. Exiting program.")
        sys.exit(1)


def main() -> None:
    """main function.
    """
    config = _full_load_config()

    scheduler = Scheduler(config)
    if scheduler.is_use_flag("camera"):
        _create_scheduler_job(scheduler.camera_job, config["camera"]["scheduler"])

    while True:
        try:
            schedule.run_pending()
            sleep(1)
        except KeyboardInterrupt as e:
            logger.info("Received interrupt signal. Shutting down...")
            raise e
        except Exception as e:
            logger.error(e)


def _full_load_config(config_path: str = "config.yaml") -> Dict:
    """Return full loaded config.

    Args:
        config_path:

    Returns:
        Config Dict
    """
    with open(config_path) as file:
        return yaml.safe_load(file)


def _create_scheduler_job(callback_job: object, scheduler_config: Dict) -> None:
    """Create the scheduler job.

    Args:
        callback_job: user callback function
        scheduler_config: scheduler yaml config
    """
    if "interval_minutes" in scheduler_config:
        schedule.every(scheduler_config["interval_minutes"]).minutes.do(callback_job)
    elif "day_of_week" in scheduler_config:
        for day_of_week in scheduler_config["day_of_week"]:
            if "at_time" in scheduler_config:
                at_time_list = [scheduler_config["at_time"]] if isinstance(scheduler_config["at_time"], str) else scheduler_config["at_time"]
                for at_time in at_time_list:
                    getattr(schedule.every(), day_of_week).at(at_time).do(callback_job)
            else:
                getattr(schedule.every(), day_of_week).do(callback_job)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google Photo Uploader")
    parser.add_argument("-f", "--function", type=str, default="main", help="set function name in this file")
    args = parser.parse_args()

    func_dict = {name: function for name, function in locals().items() if callable(function)}
    func_dict[args.function]()