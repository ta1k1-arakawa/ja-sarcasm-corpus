import json
import re
import os
import random

# ==========================================
# 設定
# ==========================================
# ファイルパス設定
TEXT_FILE_PATH = "./material/105-1200.txt"   # 皮肉データ（AI生成）
JSON_DIR_PATH = "./dialogues"                # 元の会話データ（JSON）
OUTPUT_FILE = "train_detection.jsonl"        # 出力ファイル名

# IDの範囲指定
START_ID = 105
END_ID = 1200

# 共通のインストラクション
INSTRUCTION = "以下の会話と最後の発言を読んで、最後の発言が「皮肉」かどうか判定してください。「はい」または「いいえ」のみで答えてください。"

# ==========================================
# 1. テキストファイル（皮肉データ）の読み込み
# ==========================================
def load_sarcasm_data(file_path):
    if not os.path.exists(file_path):
        print(f"エラー: {file_path} が見つかりません。")
        return {}

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # IDごとのブロックに分割
    parts = re.split(r'={20}\s*\[ID:\s*(\d+)\]\s*={20}', content)
    sarcasm_dict = {}

    for i in range(1, len(parts), 2):
        if i + 1 >= len(parts): break
        
        data_id = int(parts[i])
        block_content = parts[i+1]
        
        # 状況抽出
        situation_match = re.search(r'■ 状況:\s*(.*?)(?:\n|$)', block_content)
        situation = situation_match.group(1).strip() if situation_match else "日常的な会話"

        # コンテキスト抽出
        context_match = re.search(r'---\s*対話コンテキスト\s*---\s*(.*?)\s*(?:---|$)', block_content, re.DOTALL)
        context_text = context_match.group(1).strip() if context_match else ""

        # 皮肉な応答抽出
        response_match = re.search(r'---\s*皮肉な応答\s*---\s*(.*?)\s*(?:---|$)', block_content, re.DOTALL)
        sarcastic_response = response_match.group(1).strip() if response_match else ""

        if context_text and sarcastic_response:
            sarcasm_dict[data_id] = {
                "situation": situation,
                "context": context_text,
                "sarcastic_response": sarcastic_response
            }
    
    print(f"テキストファイルから {len(sarcasm_dict)} 件のデータを読み込みました。")
    return sarcasm_dict

# ==========================================
# 2. JSONファイルから「文脈」と「発言」の両方を取得
# ==========================================
def load_original_data_from_json(json_path):
    """
    JSONファイルを読み込み、
    (文脈テキスト, 最後の発言) のタプルを返す
    """
    if not os.path.exists(json_path):
        return None

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        utterances = data.get('utterances', [])
        if len(utterances) < 2: return None

        # 最後の発言（ターゲット）
        last_u = utterances[-1]
        target_text = f"{last_u.get('interlocutor_id', '')}: {last_u.get('text', '')}"

        # その前の会話（文脈）
        # ※テキストファイル側の文脈と長さを合わせるため、後ろから数件（例えば5件）を取得
        context_list = utterances[-6:-1]
        context_text = "\n".join([f"{u.get('interlocutor_id', '')}: {u.get('text', '')}" for u in context_list])
        
        return context_text, target_text

    except Exception as e:
        print(f"JSON読込エラー ({json_path}): {e}")
        return None

# ==========================================
# メイン処理
# ==========================================
def main():
    sarcasm_data_map = load_sarcasm_data(TEXT_FILE_PATH)
    dataset_entries = []
    
    print(f"ID {START_ID} から {END_ID} の処理を開始します...")
    
    count_sarcasm = 0
    count_normal = 0

    for current_id in range(START_ID, END_ID + 1):
        # JSONファイル名の生成
        json_filename = f"{current_id:05}.json"
        json_path = os.path.join(JSON_DIR_PATH, json_filename)
        
        # --- A. 皮肉データの作成 ---
        if current_id in sarcasm_data_map:
            entry = sarcasm_data_map[current_id]
            # テキストファイル由来の文脈 + テキストファイル由来の皮肉応答
            input_text_sarcasm = f"テーマ: {entry['situation']}\n\n会話:\n{entry['context']}\n\n発言:\n{entry['sarcastic_response']}"
            
            dataset_entries.append({
                "original_id": str(current_id),
                "type": "sarcasm",
                "instruction": INSTRUCTION,
                "input": input_text_sarcasm,
                "output": "はい"
            })
            count_sarcasm += 1
            
            # 状況（テーマ）はJSON側でも流用するために取っておく
            current_situation = entry['situation']
        else:
            current_situation = "日常的な会話"

        # --- B. 非皮肉データの作成 ---
        original_data = load_original_data_from_json(json_path)
        
        if original_data:
            json_context, json_target = original_data
            
            if json_context and json_target:
                # ★重要変更点★
                # JSONファイル由来の文脈 + JSONファイル由来の元の応答
                # これで「会話が噛み合っているが、皮肉ではない」データになります
                input_text_normal = f"テーマ: {current_situation}\n\n会話:\n{json_context}\n\n発言:\n{json_target}"
                
                dataset_entries.append({
                    "original_id": str(current_id),
                    "type": "normal",
                    "instruction": INSTRUCTION,
                    "input": input_text_normal,
                    "output": "いいえ"
                })
                count_normal += 1

    # 3. シャッフルして保存
    print(f"作成結果: 皮肉(はい)={count_sarcasm}件, 普通(いいえ)={count_normal}件")
    print(f"合計 {len(dataset_entries)} 件のデータを保存します。")
    
    if len(dataset_entries) > 0:
        random.shuffle(dataset_entries)
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            for entry in dataset_entries:
                json.dump(entry, f, ensure_ascii=False)
                f.write('\n')
        print(f"✅ 完了: {OUTPUT_FILE}")
    else:
        print("⚠️ データが作成されませんでした。")

if __name__ == "__main__":
    main()