"""
CSV 変換ユーティリティ

可読形式テキスト（1-104.txt）を CSV に変換する。
アノテーション用の列も追加される。
"""

import csv
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import MATERIAL_DIR, RAW_DIR, setup_logger

logger = setup_logger(__name__)

# =============================
# 設定
# =============================
INPUT_FILE = MATERIAL_DIR / "1-104.txt"
OUTPUT_FILE = RAW_DIR / "dataset.csv"

# CSV ヘッダー
HEADER = [
    "ID",
    "テーマ",
    "対話コンテキスト",
    "皮肉な応答",
    "皮肉の解説",
    "ステップ1: 文脈の自然さ",
    "ステップ2: 皮肉の妥当性",
    "ステップ3: 解説の妥当性",
]

# ID 単位の分割パターン
ID_PATTERN = re.compile(
    r"={10,} \[ID: (\d+)\] ={10,}(.*?)(?=={10,} \[ID:|\Z)",
    re.DOTALL,
)


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        full_text = f.read()

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(HEADER)

        for match in ID_PATTERN.finditer(full_text):
            id_num = match.group(1).strip()
            content = match.group(2).strip()

            # タグを除去
            content = re.sub(r"\\s*", "", content)

            try:
                theme = re.search(r"■ テーマ: (.*?)\n", content).group(1).strip()
                context = (
                    re.search(
                        r"--- 対話コンテキスト ---(.*?)\n--- 皮肉な応答 ---",
                        content,
                        re.DOTALL,
                    )
                    .group(1)
                    .strip()
                )
                response = (
                    re.search(
                        r"--- 皮肉な応答 ---(.*?)\n--- 皮肉の解説 ---",
                        content,
                        re.DOTALL,
                    )
                    .group(1)
                    .strip()
                )
                explanation = (
                    re.search(r"--- 皮肉の解説 ---(.*)", content, re.DOTALL)
                    .group(1)
                    .strip()
                )

                writer.writerow(
                    [id_num, theme, context, response, explanation, "", "", ""]
                )

            except AttributeError:
                logger.warning("ID: %s の解析に失敗しました。", id_num)

    logger.info("✅ CSV ファイルの生成が完了しました: %s", OUTPUT_FILE)


if __name__ == "__main__":
    main()