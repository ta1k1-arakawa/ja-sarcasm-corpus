"""
テストデータセット作成スクリプト

アノテーション結果（CSV）を読み込み、多数決で
ラベル付きテストデータセット（JSONL）を作成する。
"""

import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

from config import DATA_DIR, MATERIAL_DIR, setup_logger, write_jsonl

logger = setup_logger(__name__)

# =============================
# 設定
# =============================
ANALYSIS_FILE = MATERIAL_DIR / "集約データ - 分析結果.csv"
DATA_FILE = MATERIAL_DIR / "集約データ - 集約データ.csv"
OUTPUT_FILE = DATA_DIR / "labeled_test_dataset.jsonl"

# ラベル付けの閾値
SARCASM_THRESHOLD = 5  # 一致数がこれ以上なら「皮肉」
NON_SARCASM_THRESHOLD = 2  # 一致数がこれ以下なら「非皮肉」


def main():
    try:
        # 1. CSV の読み込み
        df_analysis = pd.read_csv(ANALYSIS_FILE, encoding="utf-8")
        df_data = pd.read_csv(DATA_FILE, encoding="utf-8")

        # ID を文字列型に統一
        df_analysis["ID"] = df_analysis["ID"].astype(str)
        df_data["ID"] = df_data["ID"].astype(str)

        # 2. データの結合
        df_merged = pd.merge(
            df_data, df_analysis[["ID", "一致数"]], on="ID", how="inner"
        )

        # 3. データ処理と抽出
        results = []
        sarcasm_cnt = 0
        non_sarcasm_cnt = 0
        discard_cnt = 0

        for _, row in df_merged.iterrows():
            vote_count = row["一致数"]

            # ラベル付けロジック
            if vote_count >= SARCASM_THRESHOLD:
                label = "皮肉"
                sarcasm_cnt += 1
            elif vote_count <= NON_SARCASM_THRESHOLD:
                label = "非皮肉"
                non_sarcasm_cnt += 1
            else:
                # 3〜4人の場合は除外
                discard_cnt += 1
                continue

            # テキストデータの取得
            theme = row.get("テーマ", "")
            situation = row.get("状況", "")
            conversation = row.get("対話コンテキスト", "")
            response = row.get("皮肉な応答", "")

            # input テキストの整形
            input_text = f"テーマ: {theme}\n"
            if pd.notna(situation) and situation != "":
                input_text += f"状況: {situation}\n"
            input_text += f"\n会話:\n{conversation}"

            entry = {
                "instruction": "以下の会話の文脈と状況を踏まえて、相手に対する皮肉な応答を生成してください。",
                "input": input_text,
                "output": response,
                "label": label,
            }
            results.append(entry)

        # 4. JSONL として保存
        written = write_jsonl(OUTPUT_FILE, results)

        logger.info("-" * 30)
        logger.info("処理完了: 合計 %d 件のデータセットを作成しました。", written)
        logger.info("保存先: %s", OUTPUT_FILE)
        logger.info("-" * 30)
        logger.info("  [内訳]")
        logger.info("  正解「皮肉」 (一致数 %d-%d): %d 件", SARCASM_THRESHOLD, 6, sarcasm_cnt)
        logger.info("  正解「非皮肉」(一致数 0-%d): %d 件", NON_SARCASM_THRESHOLD, non_sarcasm_cnt)
        logger.info("  除外 (一致数 3-4)       : %d 件", discard_cnt)
        logger.info("-" * 30)

    except Exception as e:
        logger.error("エラーが発生しました: %s", e)


if __name__ == "__main__":
    main()