import json

# --- 設定 ---
input_file = 'sarcasm_dataset.jsonl'
output_file = 'sarcasm_dataset_readable.txt'
# -----------

print(f"'{input_file}' を読み込んで '{output_file}' に変換します...")

with open(input_file, 'r', encoding='utf-8') as f_in, \
     open(output_file, 'w', encoding='utf-8') as f_out:

    count = 0
    for line in f_in:
        try:
            data = json.loads(line)
            count += 1

            f_out.write(f"==================== [ID: {data['original_dialogue_id']}] ====================\n")
            f_out.write(f"■ テーマ: {data['original_situation']['theme']}\n")
            f_out.write(f"■ 状況: {data['original_situation']['summary']}\n\n")

            f_out.write("--- 対話コンテキスト ---\n")
            for u in data['context']:
                f_out.write(f"{u['speaker']}: {u['text']}\n")
            
            f_out.write("\n--- 皮肉な応答 ---\n")
            response_obj = data['response']
            f_out.write(f"{response_obj['speaker']}: {response_obj['text']}\n")

            f_out.write("\n--- 皮肉の解説 ---\n")
            f_out.write(f"{data['sarcasm_explanation']}\n\n\n")

        except (json.JSONDecodeError, KeyError) as e:
            print(f"エラーが発生したため、行をスキップします: {e}")

print(f"✅ 変換が完了しました！ {count}件のデータを'{output_file}' に書き込みました。")