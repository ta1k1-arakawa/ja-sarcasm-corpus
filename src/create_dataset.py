"""
検出用データセット作成スクリプト

皮肉データ（AI生成テキスト）と元の会話データ（JSON）を組み合わせて、
皮肉検出タスク用の訓練データセットを作成する。
"""

import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))

from config import DATA_DIR, DIALOGUES_DIR, MATERIAL_DIR, setup_logger, write_jsonl

logger = setup_logger(__name__)

# =============================
# 設定
# =============================
TEXT_FILE_PATH = MATERIAL_DIR / "105-1200.txt"
OUTPUT_FILE = DATA_DIR / "train_detection.jsonl"

START_ID = 105
END_ID = 1200

INSTRUCTION = (
    "以下の会話と最後の発言を読んで、最後の発言が「皮肉」かどうか"
    "判定してください。「はい」または「いいえ」のみで答えてください。"
)


# =============================
# 皮肉データの読み込み
# =============================
def load_sarcasm_data(file_path):
    """テキストファイルから皮肉データを ID ごとの辞書として読み込む。"""
    if not os.path.exists(file_path):
        logger.error("ファイルが見つかりません: %s", file_path)
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    parts = re.split(r"={20}\s*\[ID:\s*(\d+)\]\s*={20}", content)
    sarcasm_dict = {}

    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts):
            break

        data_id = int(parts[i])
        block_content = parts[i + 1]

        # 状況抽出
        situation_match = re.search(r"■ 状況:\s*(.*?)(?:\n|$)", block_content)
        situation = (
            situation_match.group(1).strip() if situation_match else "日常的な会話"
        )

        # コンテキスト抽出
        context_match = re.search(
            r"---\s*対話コンテキスト\s*---\s*(.*?)\s*(?:---|$)",
            block_content,
            re.DOTALL,
        )
        context_text = context_match.group(1).strip() if context_match else ""

        # 皮肉な応答抽出
        response_match = re.search(
            r"---\s*皮肉な応答\s*---\s*(.*?)\s*(?:---|$)",
            block_content,
            re.DOTALL,
        )
        sarcastic_response = (
            response_match.group(1).strip() if response_match else ""
        )

        if context_text and sarcastic_response:
            sarcasm_dict[data_id] = {
                "situation": situation,
                "context": context_text,
                "sarcastic_response": sarcastic_response,
            }

    logger.info("テキストファイルから %d 件のデータを読み込みました。", len(sarcasm_dict))
    return sarcasm_dict


# =============================
# JSON から文脈と発言を取得
# =============================
def load_original_data_from_json(json_path):
    """JSON ファイルを読み込み、(文脈テキスト, 最後の発言) を返す。"""
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        utterances = data.get("utterances", [])
        if len(utterances) < 2:
            return None

        # 最後の発言（ターゲット）
        last_u = utterances[-1]
        target_text = f"{last_u.get('interlocutor_id', '')}: {last_u.get('text', '')}"

        # その前の会話（文脈）— 後ろ5件を取得
        context_list = utterances[-6:-1]
        context_text = "\n".join(
            f"{u.get('interlocutor_id', '')}: {u.get('text', '')}"
            for u in context_list
        )

        return context_text, target_text

    except Exception as e:
        logger.error("JSON 読込エラー (%s): %s", json_path, e)
        return None


# =============================
# メイン処理
# =============================
def main():
    sarcasm_data_map = load_sarcasm_data(str(TEXT_FILE_PATH))
    dataset_entries = []

    logger.info("ID %d から %d の処理を開始します...", START_ID, END_ID)

    count_sarcasm = 0
    count_normal = 0

    for current_id in range(START_ID, END_ID + 1):
        json_path = DIALOGUES_DIR / f"{current_id:05}.json"

        # --- A. 皮肉データの作成 ---
        if current_id in sarcasm_data_map:
            entry = sarcasm_data_map[current_id]
            input_text_sarcasm = (
                f"テーマ: {entry['situation']}\n\n"
                f"会話:\n{entry['context']}\n\n"
                f"発言:\n{entry['sarcastic_response']}"
            )

            dataset_entries.append(
                {
                    "original_id": str(current_id),
                    "type": "sarcasm",
                    "instruction": INSTRUCTION,
                    "input": input_text_sarcasm,
                    "output": "はい",
                }
            )
            count_sarcasm += 1
            current_situation = entry["situation"]
        else:
            current_situation = "日常的な会話"

        # --- B. 非皮肉データの作成 ---
        original_data = load_original_data_from_json(str(json_path))

        if original_data:
            json_context, json_target = original_data

            if json_context and json_target:
                input_text_normal = (
                    f"テーマ: {current_situation}\n\n"
                    f"会話:\n{json_context}\n\n"
                    f"発言:\n{json_target}"
                )

                dataset_entries.append(
                    {
                        "original_id": str(current_id),
                        "type": "normal",
                        "instruction": INSTRUCTION,
                        "input": input_text_normal,
                        "output": "いいえ",
                    }
                )
                count_normal += 1

    # シャッフルして保存
    logger.info(
        "作成結果: 皮肉(はい)=%d 件, 普通(いいえ)=%d 件", count_sarcasm, count_normal
    )

    if dataset_entries:
        random.shuffle(dataset_entries)
        written = write_jsonl(OUTPUT_FILE, dataset_entries)
        logger.info("✅ 完了: %d 件を %s に保存しました。", written, OUTPUT_FILE)
    else:
        logger.warning("⚠️ データが作成されませんでした。")


if __name__ == "__main__":
    main()