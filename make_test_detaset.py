import pandas as pd
import json

def main():
    # --- ファイル名設定 ---
    # 一致数が入っているファイル
    analysis_file = '集約データ - 分析結果.csv'
    # テキストデータが入っているファイル
    data_file = '集約データ - 集約データ.csv'
    # 出力するファイル名
    output_file = 'labeled_test_dataset.jsonl'

    try:
        # 1. CSVの読み込み
        df_analysis = pd.read_csv(analysis_file, encoding='utf-8')
        df_data = pd.read_csv(data_file, encoding='utf-8')

        # IDを文字列型に統一してマージのキーにする
        df_analysis['ID'] = df_analysis['ID'].astype(str)
        df_data['ID'] = df_data['ID'].astype(str)

        # 2. データの結合 (IDをキーにして、一致数情報をデータに付与)
        # df_dataに、df_analysisの'一致数'カラムを結合します
        df_merged = pd.merge(df_data, df_analysis[['ID', '一致数']], on='ID', how='inner')

        # 3. データ処理と抽出
        results = []
        sarcasm_cnt = 0
        non_sarcasm_cnt = 0
        discard_cnt = 0

        for _, row in df_merged.iterrows():
            vote_count = row['一致数']
            
            # --- ラベル付けロジック ---
            label = ""
            if vote_count >= 5:
                label = "皮肉"
                sarcasm_cnt += 1
            elif vote_count <= 2:
                label = "非皮肉"
                non_sarcasm_cnt += 1
            else:
                # 3〜4人の場合は除外
                discard_cnt += 1
                continue

            # --- テキストデータの取得 ---
            theme = row.get('テーマ', '')
            situation = row.get('状況', '') # 列が存在しない場合は空文字
            conversation = row.get('対話コンテキスト', '')
            response = row.get('皮肉な応答', '')

            # inputテキストの整形
            input_text = f"テーマ: {theme}\n"
            if pd.notna(situation) and situation != '':
                input_text += f"状況: {situation}\n"
            input_text += f"\n会話:\n{conversation}"

            # データの作成
            entry = {
                "instruction": "以下の会話の文脈と状況を踏まえて、相手に対する皮肉な応答を生成してください。",
                "input": input_text,
                "output": response,
                "label": label  # ★ここで正解ラベルを付与
            }
            results.append(entry)

        # 4. JSONLファイルとして保存
        with open(output_file, 'w', encoding='utf-8') as f:
            for entry in results:
                json.dump(entry, f, ensure_ascii=False)
                f.write('\n')

        # 結果の表示
        print("-" * 30)
        print(f"処理完了: 合計 {len(results)} 件のデータセットを作成しました。")
        print(f"保存先: {output_file}")
        print("-" * 30)
        print(f"  [内訳]")
        print(f"  正解「皮肉」 (一致数 5-6): {sarcasm_cnt} 件")
        print(f"  正解「非皮肉」(一致数 0-2): {non_sarcasm_cnt} 件")
        print(f"  除外 (一致数 3-4)       : {discard_cnt} 件")
        print("-" * 30)

    except Exception as e:
        print(f"エラーが発生しました: {e}")

if __name__ == '__main__':
    main()