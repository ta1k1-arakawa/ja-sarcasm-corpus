import os
import json

#入力素材
dialogue_dir = "./dialogues"  
start_index = 105
end_index = 1200

files = []
print(f"フォルダ {dialogue_dir} 内の {start_index:05d}.json から {end_index:05d}.json までを処理します...")
cnt = 0
# 2. ファイル名のリストをループで作成
for i in range(start_index, end_index + 1):
    # "00005.json" のように5桁ゼロ埋めのファイル名を作成
    filename = f"{i:05d}.json"
    
    # フォルダパスとファイル名を結合してフルパスを作成
    file_path = os.path.join(dialogue_dir, filename)
    
    # 3. ファイルが存在するか確認（安全のため）
    if os.path.exists(file_path):
        cnt += 1
        files.append(file_path)
    else:
        print(f"[警告] スキップ: {file_path} が見つかりません。")
print(f"合計 {cnt} 個のファイルを処理対象としてリストに追加しました。")