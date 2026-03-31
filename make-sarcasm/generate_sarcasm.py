import os
import json
import time
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ValidationError, constr
from tenacity import retry, wait_exponential, stop_after_attempt
import google.generativeai as genai
from dotenv import load_dotenv

# =============================
# Config & Env
# =============================
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-latest")
INPUT_PATH = os.getenv("INPUT_PATH", "situations.jsonl")
OUT_PATH = os.getenv("OUT_PATH", "sarcasm_dataset.jsonl")

assert GOOGLE_API_KEY, "❌ GOOGLE_API_KEY が .env に設定されていません。"
print(f"✅ Model: {GEMINI_MODEL}")
print(f"✅ Input: {INPUT_PATH}")
print(f"✅ Output: {OUT_PATH}")


# =============================
# Initialize Gemini
# =============================
genai.configure(api_key=GOOGLE_API_KEY)

generation_config = {
    "temperature": 1.0,
    "top_p": 0.95,
    "top_k": 40,
    "response_mime_type": "application/json",
}
model = genai.GenerativeModel(
    model_name=GEMINI_MODEL,
    generation_config=generation_config,
)

# =============================
# Schemas (Pydantic Models)
# =============================

# --- Input Schemas ---
class Situation(BaseModel):
    theme: str
    summary: str

class SituationRecord(BaseModel):
    dialogue_id: str
    situation: Situation
    A_style: str
    B_style: str

# --- Gemini Output & Data Structure Schemas ---
class Utterance(BaseModel):
    """発話単体を表現するモデル"""
    speaker: str
    text: str

class GeneratedSarcasm(BaseModel):
    """Geminiが返すJSONの構造を検証するためのモデル"""
    context: List[Utterance]
    sarcasm_explanation: constr(strip_whitespace=True, min_length=10)
    sarcastic_response: Utterance

# ★★★ 修正点 1: 最終出力のJSON形式をPDFの構成に合わせる ★★★
class FinalRecord(BaseModel):
    """最終的にファイルに出力するレコードの構造"""
    original_dialogue_id: str
    original_situation: Situation
    speaker_styles: Dict[str, str]
    context: List[Utterance] = Field(..., description="皮肉な応答の直前までの対話コンテキスト")
    response: Utterance = Field(..., description="皮肉な応答（ターゲット発話）")
    sarcasm_explanation: str = Field(..., description="応答がなぜ皮肉なのかの説明")


# =============================
# Prompts
# =============================

# ★★★ 修正点 2: プロンプトの指示を明確化 ★★★
SYSTEM_PROMPT = """
あなたは、自然で面白い日本語の対話を作成するAIです。皮肉（Sarcasm）の生成も得意とします。

# 皮肉の定義
相手の発言や状況に対して、意図的に本心とは逆の、または誇張した表現を使い、からかったり非難したりする言い方。文脈やトーンが重要になる。

# タスク説明
提供された「状況サリー」と「話者の文体」に基づいて、以下のステップで全く新しい短い対話をJSON形式で生成してください。

1.  **対話の生成**: まず、状況に合った2〜4ターン程度の自然な雑談対話（AとBの会話）を`context`として生成します。各発話は`{"speaker": "A", "text": "..."}`の形式にしてください。
2.  **皮肉の説明**: 次に、生成した対話の最後の発話（`context`の末尾）に対して、**もう一方の話者**がどのような皮肉を言うかを`sarcasm_explanation`として記述します。
3.  **皮肉な応答の生成**: 最後に、その説明に沿った皮肉な応答を`sarcastic_response`として生成します。

# 制約
- 必ず指定されたJSON形式で出力してください。他のテキストは含めないでください。
- `context`のキー名は`dialogue`にしないでください。
- 話者Aと話者Bの文体（敬体/常体）は指示に従ってください。
- **最重要**: `sarcastic_response` の `speaker` は、`context` の最後の発話の `speaker` と **必ず異なる人物**（AかBのどちらか）にしてください。 (例: contextの最後がAなら、responseはB。contextの最後がBなら、responseはA)
- 生成する対話は、攻撃的・差別的な内容を含まないようにしてください。
"""

USER_PROMPT_TEMPLATE = """
# 指示
以下の情報に基づいて、皮肉な応答を含む対話を生成してください。

## 状況サマリー
- 主題: {theme}
- 状況: {summary}

## 話者の文体
- 話者A: {A_style}
- 話者B: {B_style}

# 出力 (JSON)
"""

# =============================
# Gemini Call & Data Normalization
# =============================
def normalize_gemini_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Geminiからのレスポンスのキー名の揺れを正規化する"""
    if 'dialogue' in data and 'context' not in data:
        data['context'] = data.pop('dialogue')

    def normalize_utterance_list(utterances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = []
        for item in utterances:
            if isinstance(item, dict):
                text = item.get('line') or item.get('utterance') or item.get('text')
                if 'speaker' in item and text is not None:
                    normalized.append({'speaker': item['speaker'], 'text': text})
        return normalized

    if 'context' in data and isinstance(data['context'], list):
        data['context'] = normalize_utterance_list(data['context'])

    if 'sarcastic_response' in data and isinstance(data['sarcastic_response'], dict):
        normalized_res = normalize_utterance_list([data['sarcastic_response']])
        if normalized_res:
            data['sarcastic_response'] = normalized_res[0]

    return data


@retry(wait=wait_exponential(multiplier=2, min=2, max=60), stop=stop_after_attempt(5))
def generate_sarcastic_dialogue(record: SituationRecord) -> GeneratedSarcasm:
    """Gemini APIを呼び出して皮肉な対話を生成する"""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        theme=record.situation.theme,
        summary=record.situation.summary,
        A_style=record.A_style,
        B_style=record.B_style,
    )

    full_prompt = [SYSTEM_PROMPT, user_prompt]
    
    print(f"  > Generating for dialogue_id: {record.dialogue_id}, theme: {record.situation.theme}")
    response = model.generate_content(full_prompt)

    if response.usage_metadata:
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        total_tokens = response.usage_metadata.total_token_count
        
        print(f"    [Usage] In: {input_tokens} | Out: {output_tokens} | Total: {total_tokens}")
    
    response_text = response.text
    try:
        cleaned_response_text = response_text.strip().removeprefix("```json").removesuffix("```").strip()
        raw_data = json.loads(cleaned_response_text)
        normalized_data = normalize_gemini_response(raw_data)
        
        # Pydanticモデルに変換
        gemini_result = GeneratedSarcasm(**normalized_data)

        # ★★★ 修正点 3: Python側での話者検証 ★★★
        if not gemini_result.context:
             raise ValidationError("Validation Failed: `context` が空です。")
             
        if gemini_result.context and gemini_result.sarcastic_response:
            last_context_speaker = gemini_result.context[-1].speaker
            sarcasm_speaker = gemini_result.sarcastic_response.speaker
            
            if last_context_speaker == sarcasm_speaker:
                # 最後の話者と皮肉の話者が同じ場合はエラーとして扱い、再試行を促す
                print(f"  [ERROR] Validation Failed: Context speaker ({last_context_speaker}) and Sarcasm speaker ({sarcasm_speaker}) are the same.")
                raise ValidationError(f"Generated dialogue failed speaker validation (speakers {last_context_speaker} are the same).")

        return gemini_result
        
    except (json.JSONDecodeError, ValidationError) as e:
        print(f"  [ERROR] Failed to parse or validate the response from Gemini.")
        print(f"  [ERROR] Details: {e}")
        print(f"  [RAW RESPONSE] --------------------")
        print(response_text)
        print(f"  ---------------------------------")
        raise

# =============================
# Main Logic
# =============================
def main():
    if not os.path.exists(INPUT_PATH):
        print(f"❌ 入力ファイルが見つかりません: {INPUT_PATH}")
        print("💡 `situation.py` を先に実行して、`situations.jsonl` を生成してください。")
        return

    n_ok, n_ng = 0, 0
    records_to_process = []
    with open(INPUT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                records_to_process.append(SituationRecord(**data))
            except (json.JSONDecodeError, ValidationError) as e:
                print(f"⚠️ 入力ファイルの行をスキップしました (パースエラー): {e}")

    print(f"✅ {len(records_to_process)}件の状況を読み込みました。生成を開始します...")

    with open(OUT_PATH, "w", encoding="utf-8") as out_f:
        for i, record in enumerate(records_to_process):
            print(f"[{i+1}/{len(records_to_process)}] Processing...")
            try:
                # Geminiから対話データを生成
                generated_data = generate_sarcastic_dialogue(record)

                final_record = FinalRecord(
                    original_dialogue_id=record.dialogue_id,
                    original_situation=record.situation,
                    speaker_styles={"A": record.A_style, "B": record.B_style},
                    context=generated_data.context,
                    response=generated_data.sarcastic_response,
                    sarcasm_explanation=generated_data.sarcasm_explanation
                )
                
                out_f.write(final_record.model_dump_json(ensure_ascii=False) + "\n")
                n_ok += 1
                print(f"  [OK] Successfully generated and saved.")
                
                time.sleep(4.2)

            except Exception as e:
                n_ng += 1
                if "RetryError" in str(type(e)):
                     print(f"  [NG] Generation failed after multiple retries for {record.dialogue_id}.")
                else:
                    print(f"  [NG] An unexpected error occurred for {record.dialogue_id}: {e}")


    print("\n" + "="*30)
    print("🎉 処理が完了しました。")
    print(f"  - 成功: {n_ok}件")
    print(f"  - 失敗: {n_ng}件")
    print(f"  - 出力ファイル: {OUT_PATH}")
    print("="*30)
    if n_ok > 0 and n_ng == 0:
      print("\n✅ 全ての処理が成功しました！ `sarcasm_dataset.jsonl` を確認してください。")
      print("\n次のステップは、生成されたデータセットの目視確認とアノテーション（フィルタリング）です。")
    elif n_ok > 0 and n_ng > 0:
      print("\n⚠️ いくつかの処理が失敗しました。")
      print("  [NG] のログを確認し、プロンプトやスキーマの調整を検討してください。")
    else:
      print("\n❌ 全ての処理が失敗しました。[RAW RESPONSE]の内容を確認し、プロンプトやスキーマの調整を検討してください。")


if __name__ == "__main__":
    main()