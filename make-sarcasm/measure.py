import subprocess
import time
import sys
import os

# 実行時間を計測したいスクリプトのリスト
scripts_to_measure = [
    'situation.py',
    'generate_sarcasm.py',
    'sarcasm_dataset_readable.py'
]

# 実行環境を準備
my_env = os.environ.copy()
my_env["PYTHONIOENCODING"] = "utf-8"

print("各スクリプトの実行時間を計測します...")
print("-" * 30)

# 1. 合計時間の変数を「ループの外」で初期化する
total_execution_time = 0.0

# スクリプトを一つずつ実行して時間を計る
for script in scripts_to_measure:
    print(f"[{script}] を実行中...")
    
    start_time = time.time()  # 実行前の時刻を記録
    # 'sum = 0' をここから削除
    
    try:
        subprocess.run(
            [sys.executable, script], 
            check=True, 
            capture_output=False,  # 出力を直接表示
            env=my_env
        )
        
        end_time = time.time()
        
        execution_time = end_time - start_time
        total_execution_time += execution_time  # 合計時間に加算
        
        print(f"[{script}] の実行が完了しました。")
        print(f"  実行時間: {execution_time:.4f} 秒")
        print("-" * 30)
        
    except subprocess.CalledProcessError as e:
        print(f"!!! [{script}] の実行中にエラーが発生しました。")
        print(f"  エラー内容:\n{e.stderr}")
        print("-" * 30)
        break
    except FileNotFoundError:
        print(f"!!! ファイル [{script}] が見つかりません。")
        print("-" * 30)
        break

# 2. f-stringを使って文字列と数値を正しく表示する
print(f"すべての合計時間: {total_execution_time:.4f} 秒")
print("全ての計測が完了しました。")