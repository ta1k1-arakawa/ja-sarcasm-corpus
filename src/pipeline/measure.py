"""
パイプライン一括実行スクリプト

situation.py → generate_sarcasm.py → sarcasm_dataset_readable.py を
順に実行し、各スクリプトの実行時間を計測する。
"""

import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import setup_logger

logger = setup_logger(__name__)

# 実行するスクリプトのリスト
SCRIPTS = [
    "situation.py",
    "generate_sarcasm.py",
    "sarcasm_dataset_readable.py",
]

# 実行環境を準備
my_env = os.environ.copy()
my_env["PYTHONIOENCODING"] = "utf-8"


def main():
    logger.info("各スクリプトの実行時間を計測します...")
    logger.info("-" * 30)

    total_execution_time = 0.0

    for script in SCRIPTS:
        logger.info("[%s] を実行中...", script)

        start_time = time.time()

        try:
            subprocess.run(
                [sys.executable, script],
                check=True,
                capture_output=False,
                env=my_env,
            )

            execution_time = time.time() - start_time
            total_execution_time += execution_time

            logger.info("[%s] 完了。実行時間: %.4f 秒", script, execution_time)
            logger.info("-" * 30)

        except subprocess.CalledProcessError as e:
            logger.error("[%s] の実行中にエラーが発生しました: %s", script, e.stderr)
            break
        except FileNotFoundError:
            logger.error("ファイル [%s] が見つかりません。", script)
            break

    logger.info("合計実行時間: %.4f 秒", total_execution_time)
    logger.info("全ての計測が完了しました。")


if __name__ == "__main__":
    main()