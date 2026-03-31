import re
import csv

# 1. テキストファイル全体を読み込む
with open('1-104.txt', 'r', encoding='utf-8') as f:
    full_text = f.read()

# 2. ヘッダー行を準備してCSVファイルを開く
#    F, G, H列はアノテーション用に空にしておく
header = [
    'ID', 'テーマ', '対話コンテキスト', '皮肉な応答', '皮肉の解説',
    'ステップ1: 文脈の自然さ', 'ステップ2: 皮肉の妥当性', 'ステップ3: 解説の妥当性'
]

with open('dataset.csv', 'w', encoding='utf-8', newline='') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(header)

    # 3. データを「ID」単位で分割する (正規表現)
    #    re.DOTALLは「.」が改行文字にもマッチするようにするおまじない
    pattern = r"={10,} \[ID: (\d+)\] ={10,}(.*?)(?=={10,} \[ID:|\Z)"

    for match in re.finditer(pattern, full_text, re.DOTALL):
        id_num = match.group(1).strip()
        content = match.group(2).strip()

        # のようなタグを除去
        content = re.sub(r'\\s*', '', content)

        # 4. 各ブロックから詳細データを抽出 (正規表現)
        try:
            theme = re.search(r'■ テーマ: (.*?)\n', content).group(1).strip()
            context = re.search(r'--- 対話コンテキスト ---(.*?)\n--- 皮肉な応答 ---', content, re.DOTALL).group(1).strip()
            response = re.search(r'--- 皮肉な応答 ---(.*?)\n--- 皮肉の解説 ---', content, re.DOTALL).group(1).strip()
            explanation = re.search(r'--- 皮肉の解説 ---(.*)', content, re.DOTALL).group(1).strip()

            # 5. CSVに1行書き出す
            writer.writerow([id_num, theme, context, response, explanation, '', '', ''])

        except AttributeError:
            # 正規表現がマッチしなかった場合（=形式エラー）
            print(f"ID: {id_num} の解析に失敗しました。")

print("CSVファイルの生成が完了しました。")