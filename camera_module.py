import cv2
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from time import sleep
from typing import Dict, Optional
import os

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
        f'{log_dir}/camera.log',
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

DEVICE_ID = 0


class CameraModule(object):
    def __init__(self, device_id: int = DEVICE_ID) -> None:
        """Camera Module Object.

        Args:
            device_id: device id
        """
        self._device_id = device_id
        logger.info("camera module is starting...")

    @staticmethod
    def decode_fourcc(v) -> str:
        """Decode function to fourcc string.

        Args:
            v: frame fourcc number

        Returns:
            frame fourcc string
        """
        v = int(v)
        return "".join([chr((v >> 8 * i) & 0xFF) for i in range(4)])

    def save_photo(self, save_path: str, settings: Optional[Dict] = None, with_datetime: bool = True) -> bool:
        """Save a camera photo.

        Args:
            save_path: save camera photo path
            settings: video capture frame settings
            with_datetime: with datetime text

        Returns:
            A boolean if success to save a camera photo.
        """
        cap = cv2.VideoCapture(self._device_id)

        # 基本設定（全カメラ共通）
        if settings and "fourcc" in settings and settings["fourcc"]:
            c1, c2, c3, c4 = list(settings["fourcc"])
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(c1, c2, c3, c4))
        else:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'))

        if settings and "width" in settings and settings["width"]:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, settings["width"])
        if settings and "height" in settings and settings["height"]:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, settings["height"])
        if settings and "fps" in settings and settings["fps"]:
            cap.set(cv2.CAP_PROP_FPS, settings["fps"])

        # EMEET専用設定（camera_modelが指定されている場合のみ）
        if settings and settings.get("camera_model") == "EMEET":
            logger.info("Applying EMEET-specific settings")
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25)
            cap.set(cv2.CAP_PROP_AUTO_WB, 1)
            
            focus_value = settings.get("focus", 255)
            cap.set(cv2.CAP_PROP_AUTOFOCUS, 0)
            cap.set(cv2.CAP_PROP_FOCUS, focus_value)
            
            cap.set(cv2.CAP_PROP_BRIGHTNESS, -10)
            cap.set(cv2.CAP_PROP_CONTRAST, 35)
            cap.set(cv2.CAP_PROP_SATURATION, 110)
            cap.set(cv2.CAP_PROP_ZOOM, 50)
        else:
            logger.info("Using default camera settings")
            # C270のデフォルト値にリセット
            cap.set(cv2.CAP_PROP_BRIGHTNESS, 128)
            cap.set(cv2.CAP_PROP_CONTRAST, 32)
            cap.set(cv2.CAP_PROP_SATURATION, 32)
            cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 3)

        logger.info(f"Settings: {self.decode_fourcc(cap.get(cv2.CAP_PROP_FOURCC))}, "
                    f"{int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}, "
                    f"{int(cap.get(cv2.CAP_PROP_FPS))}fps")

        is_opened = cap.isOpened()
        if not is_opened:
            logger.error("Failed to open video capture.")
            return False
        sleep(2)

        result, img = cap.read()
        if not result:
            logger.error("Failed to read video capture.")
            return False
        
        if with_datetime:
            current_datetime = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            cv2.putText(img, current_datetime, (0, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 3, cv2.LINE_AA)

        # 保存先ディレクトリを作成
        save_dir = os.path.dirname(save_path)
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)

        result = cv2.imwrite(save_path, img)
        cap.release()
        cv2.destroyAllWindows()
        logger.info(f"Photo saved: {save_path}")

        return result


def debug() -> None:
    """debug function.
    """
    import argparse, yaml

    parser = argparse.ArgumentParser(description="Camera module script")
    parser.add_argument("--config", default="config.yaml", help="config file path")
    args = parser.parse_args()

    with open(args.config) as f:
        config = yaml.safe_load(f)

    camera_config = config["camera"]
    settings = camera_config["settings"]

    current_datetime = datetime.now().strftime("%Y%m%d_%H%M")
    save_path = f"{config['camera']['photo_dir']}/camera_{current_datetime}.jpg"

    os.makedirs(config['camera']['photo_dir'], exist_ok=True)

    camera_module = CameraModule()
    camera_module.save_photo(save_path, settings)


if __name__ == "__main__":
    debug()