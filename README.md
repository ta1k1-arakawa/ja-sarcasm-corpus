# 🎭 Japanese Sarcasm Corpus (ja-sarcasm-corpus)

日本語の対話における **皮肉（Sarcasm）** を検出・生成するための研究用コーパスです。  
既存の雑談対話コーパスから状況を抽出し、生成AIを用いて皮肉な応答を追加することで構築されました。

---

## 📖 概要

本コーパスは、日本語の雑談対話における皮肉表現を扱うデータセットです。  
自然な日常会話の流れの中に、文脈に即した皮肉な応答を組み込むことで、以下の研究などに活用できます：

- **皮肉検出（Sarcasm Detection）** — 発話が皮肉かどうかを判定するタスク
- **皮肉生成（Sarcasm Generation）** — 状況に応じた皮肉な応答を生成するタスク
- **日本語の語用論研究** — 文脈依存の言語現象の分析

## 📊 データセット構成

| ファイル名 | 件数 | 用途 | 説明 |
|---|---|---|---|
| `large_train.jsonl` | 2,144件 | 訓練用 | 皮肉 / 非皮肉のペアデータ（皮肉検出タスク向け） |
| `small_train.jsonl` | 786件 | 訓練用（小） | `large_train.jsonl` のサブセット |
| `labeled_test_dataset.jsonl` | 55件 | テスト用 | 6人による人間アノテーターのラベル付きテストデータ |
| `train_detection.jsonl` | 2,144件 | 訓練用（検出） | 皮肉検出モデル学習用 |

### サンプルデータ

`sample/` ディレクトリにデータの具体例があります：

- `sarcasm_dataset_sample.jsonl` — JSONL形式のサンプル
- `sarcasm_dataset_readable_sample.txt` — 人間が読みやすいテキスト形式のサンプル

---

## 🏗️ データ構築パイプライン

本コーパスは以下の3ステップで自動構築されます。  
パイプライン全体は `src/pipeline/measure.py` で一括実行できます。

```
raw/dialogues/           src/pipeline/
(既存対話コーパス)       (生成パイプライン)

┌─────────────┐     ┌──────────────────┐     ┌─────────────────────┐
│  対話JSON    │────▷│ 1. situation.py  │────▷│  situations.jsonl   │
│  (雑談対話)  │     │  状況抽出        │     │  (主題・状況サマリ) │
└─────────────┘     └──────────────────┘     └─────────┬───────────┘
                                                        │
                                                        ▼
                                             ┌──────────────────────┐
                                             │ 2. generate_sarcasm  │
                                             │    .py               │
                                             │  皮肉対話生成        │
                                             └─────────┬────────────┘
                                                        │
                                                        ▼
                                             ┌──────────────────────┐
                                             │ 3. sarcasm_dataset   │
                                             │    _readable.py      │
                                             │  可読形式変換        │
                                             └──────────────────────┘
```

### Step 1: 状況抽出（`situation.py`）

`raw/dialogues/` 内の雑談対話JSONファイルから、Gemini APIを用いて対話の **主題（theme）** と **状況サマリ（summary）** を抽出します。  
同時に各話者の文体（敬体 / 常体）を自動判定します。

**入力**: `raw/dialogues/XXXXX.json`（雑談対話JSON）  
**出力**: `raw/material/situations.jsonl`

```json
{
  "dialogue_id": "501",
  "situation": {
    "theme": "夏バテと食欲",
    "summary": "二人が夏バテや食欲について話しながら、天気について情報交換している。"
  },
  "A_style": "敬体",
  "B_style": "敬体"
}
```

### Step 2: 皮肉対話生成（`generate_sarcasm.py`）

Step 1 で抽出した状況情報をもとに、Gemini APIで皮肉を含む新しい対話を生成します。  
生成は以下の手順で行われます：

1. 状況に合った自然な雑談対話（2〜4ターン）を生成
2. 対話の流れに対する皮肉の説明を生成
3. 皮肉な応答を生成

**入力**: `raw/material/situations.jsonl`  
**出力**: `raw/material/sarcasm_dataset.jsonl`

```json
{
  "original_dialogue_id": "501",
  "original_situation": {
    "theme": "夏バテと食欲",
    "summary": "二人が夏バテや食欲について話している。"
  },
  "speaker_styles": {"A": "敬体", "B": "敬体"},
  "context": [
    {"speaker": "A", "text": "いやー、本当に暑いですね。食欲なんて全然なくて…。"},
    {"speaker": "B", "text": "分かります！何かさっぱりしたものでも食べたいんですけど。"},
    {"speaker": "A", "text": "この天気だと、外に出るのも億劫になりますしね。"},
    {"speaker": "B", "text": "ニュースで明日も猛暑だって言ってましたよ。"}
  ],
  "response": {
    "speaker": "A",
    "text": "あら、それはそれは。なんて素晴らしいお知らせなんでしょう。"
  },
  "sarcasm_explanation": "猛暑を歓迎するかのように、意図的に本心とは逆の表現で皮肉を言っている。"
}
```

### Step 3: 可読形式変換（`sarcasm_dataset_readable.py`）

生成されたJSONLデータを、人間が確認・アノテーションしやすいテキスト形式に変換します。

**入力**: `raw/material/sarcasm_dataset.jsonl`  
**出力**: `raw/material/sarcasm_dataset_readable.txt`

```
==================== [ID: 501] ====================
■ テーマ: 夏バテと食欲
■ 状況: 二人が夏バテや食欲について話している。

--- 対話コンテキスト ---
A: いやー、本当に暑いですね。食欲なんて全然なくて…。
B: 分かります！何かさっぱりしたものでも食べたいんですけど。
A: この天気だと、外に出るのも億劫になりますしね。
B: ニュースで明日も猛暑だって言ってましたよ。

--- 皮肉な応答 ---
A: あら、それはそれは。なんて素晴らしいお知らせなんでしょう。

--- 皮肉の解説 ---
猛暑を歓迎するかのように、意図的に本心とは逆の表現で皮肉を言っている。
```

---

## 📁 ディレクトリ構成

```
.
├── README.md                       # 本ファイル
├── .env                            # 環境変数（Git管理外）
├── .gitignore                      # Git除外設定
├── src/                            # ソースコード
│   ├── config.py                   # 共通設定・ユーティリティ
│   ├── schemas.py                  # 共通Pydanticスキーマ
│   ├── create_dataset.py           # 検出用データセット作成スクリプト
│   ├── make_test_dataset.py        # テストデータセット作成スクリプト
│   └── pipeline/                   # 皮肉データ生成パイプライン
│       ├── measure.py              # パイプライン一括実行（時間計測付き）
│       ├── situation.py            # Step 1: 状況抽出
│       ├── generate_sarcasm.py     # Step 2: 皮肉対話生成
│       ├── sarcasm_dataset_readable.py # Step 3: 可読形式変換
│       └── txt_to_csv.py           # CSV変換ユーティリティ
├── data/                           # 生成済みデータセット
│   ├── large_train.jsonl
│   ├── small_train.jsonl
│   ├── labeled_test_dataset.jsonl
│   ├── train_detection.jsonl
│   └── sample/                     # サンプルデータ
│       ├── sarcasm_dataset_sample.jsonl
│       └── sarcasm_dataset_readable_sample.txt
└── raw/                            # 元データ・中間物
    ├── dialogues/                  # 雑談対話データ（Git管理外）
    └── material/                   # 皮肉追加後などの中間素材
```

---

## 🔧 セットアップ・実行方法

### 前提条件

- Python 3.10+
- [Google Gemini API キー](https://aistudio.google.com/apikey)

### 1. 依存パッケージのインストール

```bash
pip install google-generativeai pydantic tenacity python-dotenv pandas
```

### 2. APIキーの設定

プロジェクトルートに `.env` ファイルを作成します：

```env
GOOGLE_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-1.5-flash-lite
```

### 3. 元対話データの配置

`raw/dialogues/` ディレクトリに、ソースとなる雑談対話のJSONファイルを配置します。  
各JSONファイルは以下の形式である必要があります：

```json
{
  "dialogue_id": 1,
  "utterances": [
    {
      "utterance_id": 0,
      "interlocutor_id": "AA",
      "text": "よろしくお願いいたします。",
      "timestamp": "2022-08-06T14:51:18.360000"
    },
    ...
  ]
}
```

### 4. パイプラインの実行

```bash
python src/pipeline/measure.py
```

これにより `situation.py` → `generate_sarcasm.py` → `sarcasm_dataset_readable.py` が順に実行されます。

---

## 📐 データフォーマット

### 訓練データ（`large_train.jsonl` / `small_train.jsonl`）

```json
{
  "original_id": "501",
  "type": "sarcasm",
  "instruction": "以下の会話と最後の発言を読んで、最後の発言が「皮肉」かどうか判定してください。「はい」または「いいえ」のみで答えてください。",
  "input": "テーマ: 夏バテと食欲\n\n会話:\nA: ...\nB: ...\n\n発言:\nB: ...",
  "output": "はい"
}
```

| フィールド | 説明 |
|---|---|
| `original_id` | 元対話のID |
| `type` | `sarcasm`（皮肉）または `normal`（非皮肉） |
| `instruction` | タスクの指示文 |
| `input` | テーマ・会話コンテキスト・判定対象の発言 |
| `output` | `はい`（皮肉）/ `いいえ`（非皮肉） |

### テストデータ（`labeled_test_dataset.jsonl`）

```json
{
  "instruction": "以下の会話の文脈と状況を踏まえて、相手に対する皮肉な応答を生成してください。",
  "input": "テーマ: ...\n状況: ...\n\n会話:\n...",
  "output": "皮肉な応答テキスト",
  "label": "皮肉"
}
```

| フィールド | 説明 |
|---|---|
| `label` | 人間アノテーターによる正解ラベル（`皮肉` / `非皮肉`） |

> **Note**: テストデータのラベルは、6名のアノテーターの多数決で決定しています。  
> 5名以上が「皮肉」と判定 → `皮肉`、2名以下 → `非皮肉`、3〜4名は曖昧として除外。

---

## 🔬 皮肉の定義

本コーパスにおける「皮肉（Sarcasm）」は以下のように定義されています：

> 相手の発言や状況に対して、意図的に **本心とは逆の、または誇張した表現** を使い、  
> からかったり非難したりする言い方。文脈やトーンが重要になる。

---

## ⚠️ 注意事項

- 皮肉な応答は **AI（Gemini）によって生成** されたものです。不自然な表現や不適切な内容が含まれる可能性があります。
- `raw/dialogues/` ディレクトリの元対話データは本リポジトリには含まれていません（`.gitignore` で除外）。元データのライセンスに従ってご利用ください。
- 本データセットは **研究目的** で作成されています。

## 📝 ライセンス

本コーパスは、**[RealPersonaChat](https://github.com/nu-dialogue/real-persona-chat)** コーパスを元データとして使用しています。  
RealPersonaChat は **CC BY-SA 4.0**（Creative Commons Attribution-ShareAlike 4.0 International）ライセンスで公開されています。

本コーパスの利用に際しては、以下にご留意ください：

- **元データの帰属**: 本コーパスに含まれる対話状況（テーマ・状況サマリ）は RealPersonaChat から抽出されたものです。RealPersonaChat のライセンス（CC BY-SA 4.0）に従ってご利用ください。
- **派生データのライセンス**: CC BY-SA 4.0 の条件により、本コーパスも同じく **CC BY-SA 4.0** ライセンスで公開されます。
- **生成AI由来のデータ**: 皮肉な応答は生成AI（Gemini）によって作成されたデータを含むため、商用利用にはご注意ください。
- **倫理的配慮**: RealPersonaChat の利用ガイドラインに従い、コーパスのデータから個人を特定する行為や、特定の話者になりすます行為は行わないでください。

## 📬 引用

本コーパスを研究で使用する場合は、以下を参考に引用してください：

```bibtex
@misc{ja-sarcasm-corpus,
  title={Japanese Sarcasm Corpus},
  author={Taiki Arakawa},
  year={2026},
  url={https://github.com/ta1k1-arakawa/ja-sarcasm-corpus}
}
```
