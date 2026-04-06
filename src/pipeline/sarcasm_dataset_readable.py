"""
Step 3: 可読形式変換スクリプト

生成された JSONL データを人間が確認しやすいテキスト形式に変換する。
"""

import os
import sys

# src/ を Python パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import read_jsonl, setup_logger

logger = setup_logger(__name__)

# =============================
# 設定
# =============================
INPUT_FILE = os.getenv("READABLE_INPUT", "sarcasm_dataset.jsonl")
OUTPUT_FILE = os.getenv("READABLE_OUTPUT", "sarcasm_dataset_readable.txt")


def main():
    logger.info("'%s' を読み込んで '%s' に変換します...", INPUT_FILE, OUTPUT_FILE)

    count = 0

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f_out:
        for data in read_jsonl(INPUT_FILE):
            try:
                count += 1

                f_out.write(
                    f"==================== [ID: {data['original_dialogue_id']}] "
                    f"====================\n"
                )
                f_out.write(f"■ テーマ: {data['original_situation']['theme']}\n")
                f_out.write(
                    f"■ 状況: {data['original_situation']['summary']}\n\n"
                )

                f_out.write("--- 対話コンテキスト ---\n")
                for u in data["context"]:
                    f_out.write(f"{u['speaker']}: {u['text']}\n")

                f_out.write("\n--- 皮肉な応答 ---\n")
                response_obj = data["response"]
                f_out.write(f"{response_obj['speaker']}: {response_obj['text']}\n")

                f_out.write("\n--- 皮肉の解説 ---\n")
                f_out.write(f"{data['sarcasm_explanation']}\n\n\n")

            except KeyError as e:
                logger.warning("キーが見つからないため行をスキップ: %s", e)

    logger.info("✅ 変換完了: %d 件を '%s' に書き込みました。", count, OUTPUT_FILE)


if __name__ == "__main__":
    main()