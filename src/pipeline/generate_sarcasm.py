"""
Step 2: 皮肉対話生成スクリプト

状況情報（situations.jsonl）をもとに、Gemini API で
皮肉を含む対話を生成する。
"""

import json
import os
import sys
import time
from typing import Any, Dict, List

from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

# src/ を Python パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    API_SLEEP_SECONDS,
    GEMINI_MODEL,
    get_gemini_model,
    read_jsonl,
    setup_logger,
    MATERIAL_DIR,
)
from schemas import (
    FinalRecord,
    GeneratedSarcasm,
    Situation,
    SituationRecord,
    Utterance,
)

logger = setup_logger(__name__)

# =============================
# 設定
# =============================
INPUT_PATH = os.getenv("INPUT_PATH", str(MATERIAL_DIR / "situations.jsonl"))
OUT_PATH = os.getenv("OUT_PATH", str(MATERIAL_DIR / "sarcasm_dataset.jsonl"))

# =============================
# Gemini モデル初期化
# =============================
model = get_gemini_model(temperature=1.0, top_p=0.95)
logger.info("Model: %s", GEMINI_MODEL)
logger.info("Input: %s", INPUT_PATH)
logger.info("Output: %s", OUT_PATH)

# =============================
# プロンプト
# =============================
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
# レスポンス正規化
# =============================
def normalize_gemini_response(data: Dict[str, Any]) -> Dict[str, Any]:
    """Gemini のレスポンスにおけるキー名の揺れを正規化する。"""
    if "dialogue" in data and "context" not in data:
        data["context"] = data.pop("dialogue")

    def normalize_utterance_list(
        utterances: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        normalized = []
        for item in utterances:
            if isinstance(item, dict):
                text = (
                    item.get("line") or item.get("utterance") or item.get("text")
                )
                if "speaker" in item and text is not None:
                    normalized.append({"speaker": item["speaker"], "text": text})
        return normalized

    if "context" in data and isinstance(data["context"], list):
        data["context"] = normalize_utterance_list(data["context"])

    if "sarcastic_response" in data and isinstance(
        data["sarcastic_response"], dict
    ):
        normalized_res = normalize_utterance_list([data["sarcastic_response"]])
        if normalized_res:
            data["sarcastic_response"] = normalized_res[0]

    return data


# =============================
# Gemini 呼び出し
# =============================
@retry(wait=wait_exponential(multiplier=2, min=2, max=60), stop=stop_after_attempt(5))
def generate_sarcastic_dialogue(record: SituationRecord) -> GeneratedSarcasm:
    """Gemini API を呼び出して皮肉な対話を生成する。"""
    user_prompt = USER_PROMPT_TEMPLATE.format(
        theme=record.situation.theme,
        summary=record.situation.summary,
        A_style=record.A_style,
        B_style=record.B_style,
    )

    logger.info(
        "  > Generating for dialogue_id: %s, theme: %s",
        record.dialogue_id,
        record.situation.theme,
    )
    response = model.generate_content([SYSTEM_PROMPT, user_prompt])

    if response.usage_metadata:
        logger.info(
            "    [Usage] In: %d | Out: %d | Total: %d",
            response.usage_metadata.prompt_token_count,
            response.usage_metadata.candidates_token_count,
            response.usage_metadata.total_token_count,
        )

    response_text = response.text
    try:
        cleaned = (
            response_text.strip()
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )
        raw_data = json.loads(cleaned)
        normalized_data = normalize_gemini_response(raw_data)
        gemini_result = GeneratedSarcasm(**normalized_data)

        # 話者検証: context の最後の話者と sarcastic_response の話者が異なること
        if not gemini_result.context:
            raise ValidationError("Validation Failed: `context` が空です。")

        last_context_speaker = gemini_result.context[-1].speaker
        sarcasm_speaker = gemini_result.sarcastic_response.speaker

        if last_context_speaker == sarcasm_speaker:
            msg = (
                f"Context speaker ({last_context_speaker}) and "
                f"Sarcasm speaker ({sarcasm_speaker}) are the same."
            )
            logger.error("  [ERROR] Validation Failed: %s", msg)
            raise ValidationError(msg)

        return gemini_result

    except (json.JSONDecodeError, ValidationError) as e:
        logger.error("  [ERROR] Failed to parse or validate response: %s", e)
        logger.error("  [RAW RESPONSE] %s", response_text)
        raise


# =============================
# メイン処理
# =============================
def main():
    if not os.path.exists(INPUT_PATH):
        logger.error("入力ファイルが見つかりません: %s", INPUT_PATH)
        logger.info("`situation.py` を先に実行して `situations.jsonl` を生成してください。")
        return

    records_to_process = []
    for data in read_jsonl(INPUT_PATH):
        try:
            records_to_process.append(SituationRecord(**data))
        except (ValidationError,) as e:
            logger.warning("入力ファイルの行をスキップしました (パースエラー): %s", e)

    logger.info("%d 件の状況を読み込みました。生成を開始します...", len(records_to_process))

    n_ok, n_ng = 0, 0

    with open(OUT_PATH, "w", encoding="utf-8") as out_f:
        for i, record in enumerate(records_to_process):
            logger.info("[%d/%d] Processing...", i + 1, len(records_to_process))
            try:
                generated_data = generate_sarcastic_dialogue(record)

                final_record = FinalRecord(
                    original_dialogue_id=record.dialogue_id,
                    original_situation=record.situation,
                    speaker_styles={"A": record.A_style, "B": record.B_style},
                    context=generated_data.context,
                    response=generated_data.sarcastic_response,
                    sarcasm_explanation=generated_data.sarcasm_explanation,
                )

                out_f.write(
                    final_record.model_dump_json(ensure_ascii=False) + "\n"
                )
                n_ok += 1
                logger.info("  [OK] Successfully generated and saved.")
                time.sleep(API_SLEEP_SECONDS)

            except Exception as e:
                n_ng += 1
                if "RetryError" in str(type(e)):
                    logger.error(
                        "  [NG] Generation failed after retries for %s.",
                        record.dialogue_id,
                    )
                else:
                    logger.error(
                        "  [NG] Unexpected error for %s: %s",
                        record.dialogue_id,
                        e,
                    )

    logger.info("=" * 30)
    logger.info("🎉 処理が完了しました。")
    logger.info("  - 成功: %d 件", n_ok)
    logger.info("  - 失敗: %d 件", n_ng)
    logger.info("  - 出力ファイル: %s", OUT_PATH)

    if n_ok > 0 and n_ng == 0:
        logger.info("✅ 全ての処理が成功しました！")
    elif n_ok > 0:
        logger.warning("⚠️ いくつかの処理が失敗しました。[NG] ログを確認してください。")
    else:
        logger.error("❌ 全ての処理が失敗しました。RAW RESPONSE を確認してください。")


if __name__ == "__main__":
    main()