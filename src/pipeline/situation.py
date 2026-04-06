"""
Step 1: 状況抽出スクリプト

dialogues/ 内の雑談対話 JSON から Gemini API を使って
対話の主題（theme）と状況サマリ（summary）を抽出する。
"""

import json
import os
import re
import sys
import time
from json import JSONDecodeError
from typing import List, Optional

from pydantic import ValidationError
from tenacity import retry, stop_after_attempt, wait_exponential

# src/ を Python パスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import (
    API_SLEEP_SECONDS,
    GEMINI_MODEL,
    get_dialogue_files,
    get_gemini_model,
    setup_logger,
)
from schemas import Situation, SituationRecord

logger = setup_logger(__name__)

# =============================
# 設定
# =============================
START_INDEX = 501
END_INDEX = 1200
OUT_PATH = os.getenv("OUT_PATH", "situations.jsonl")

# =============================
# Gemini モデル初期化
# =============================
model = get_gemini_model(temperature=0.2, top_p=0.9)
logger.info("モデル: %s", GEMINI_MODEL)

# =============================
# プロンプト
# =============================
SYSTEM_HINT = """あなたは日本語の対話要約者です。入力の「2人の雑談対話」から次を抽出してください:
1) theme: 主題を10〜20字程度で（例: 夏バテと食欲）
2) summary: その対話の状況を1文で簡潔に説明（〜している、の文体）

厳守:
- 有害/個人特定は書かない
- 原文のコピーでなく抽象化
- JSONのみ出力（他の文字を出さない）
"""

# =============================
# 文体判定
# =============================
KEITAI_ENDINGS = (
    "です", "ます", "でした", "ません", "ですね",
    "でしたね", "でしょう", "でしょうか", "ください",
)
JOUTAI_ENDINGS = (
    "だ", "ない", "よね", "かよ", "じゃん",
    "だよ", "だな", "だね", "だろ", "だろう",
)

ENDING_RE = re.compile(r"[。.!?！？]\s*$")


def normalize_text_for_ending(text: str) -> str:
    """末尾の句読点等を落として文末判定しやすくする。"""
    t = text.strip()
    return ENDING_RE.sub("", t)


def detect_style(utterances: List[dict], speaker_id: str) -> str:
    """各話者の発話末尾を見て敬体/常体を推定する。

    いずれにも合致しない場合は '混合' を返す。
    """
    formal, informal = 0, 0

    for u in utterances:
        if u.get("interlocutor_id") != speaker_id:
            continue
        txt = normalize_text_for_ending(u.get("text", ""))
        if not txt:
            continue
        if txt.endswith(KEITAI_ENDINGS):
            formal += 1
        elif txt.endswith(JOUTAI_ENDINGS):
            informal += 1

    if formal == informal == 0:
        return "混合"
    return "敬体" if formal >= informal else "常体"


def format_dialogue_for_prompt(
    utterances: List[dict], max_turns: Optional[int] = None
) -> str:
    """発話リストをプロンプト用のテキストに整形する。"""
    uts = utterances[-max_turns:] if max_turns else utterances
    lines = []
    for u in uts:
        spk = u.get("interlocutor_id", "UNK")
        txt = u.get("text", "").strip().replace("\n", " ")
        lines.append(f"{spk}: {txt}")
    return "\n".join(lines)


# =============================
# Gemini 呼び出し
# =============================
@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
def call_gemini(dialogue_text: str) -> Situation:
    """Gemini API を呼び出して状況情報を抽出する。"""
    prompt = f"{SYSTEM_HINT}\n\n# 入力対話\n{dialogue_text}"
    resp = model.generate_content([prompt])

    if resp.usage_metadata:
        logger.info(
            "  (Tokens: In=%d, Out=%d)",
            resp.usage_metadata.prompt_token_count,
            resp.usage_metadata.candidates_token_count,
        )

    # SDK 差異に備えて堅く取り出す
    raw = None
    try:
        if hasattr(resp, "text") and resp.text:
            raw = resp.text
        else:
            candidates = getattr(resp, "candidates", None)
            if candidates:
                cand0 = candidates[0]
                content = getattr(cand0, "content", None)
                if content:
                    if isinstance(content, list) and content:
                        part = content[0]
                        raw = getattr(part, "text", None) or str(part)
                    else:
                        raw = getattr(content, "text", None) or str(content)
    except Exception:
        raw = None

    if raw is None:
        raw = str(resp)

    data = json.loads(raw)
    return Situation(**data)


# =============================
# 対話ファイル読み込み
# =============================
def load_dialogue(file_path: str):
    """対話 JSON ファイルを読み込み、(dialogue_id, utterances) を返す。"""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "utterances" in data:
        dlg_id = str(data.get("dialogue_id") or os.path.basename(file_path))
        return dlg_id, data["utterances"]
    if (
        isinstance(data, list)
        and data
        and isinstance(data[0], dict)
        and "utterances" in data[0]
    ):
        dlg_id = str(data[0].get("dialogue_id") or os.path.basename(file_path))
        return dlg_id, data[0]["utterances"]

    raise ValueError(f"未知のJSON構造: {file_path}")


# =============================
# メイン処理
# =============================
def main():
    files = get_dialogue_files(START_INDEX, END_INDEX)
    assert files, "指定された範囲のファイルが1件も見つかりませんでした。"

    logger.info(
        "%05d.json から %05d.json まで %d 件を処理します",
        START_INDEX, END_INDEX, len(files),
    )

    n_ok, n_ng = 0, 0

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for fp in files:
            try:
                dlg_id, utterances = load_dialogue(str(fp))

                if len(utterances) < 2:
                    raise ValueError("発話が2つ未満です")

                # 話者 ID を推定
                a_id = utterances[0].get("interlocutor_id")
                b_id = None
                for u in utterances[1:]:
                    if u.get("interlocutor_id") != a_id:
                        b_id = u.get("interlocutor_id")
                        break
                if not b_id:
                    raise ValueError("2人の話者が特定できません")

                a_style = detect_style(utterances, a_id)
                b_style = detect_style(utterances, b_id)
                dialogue_text = format_dialogue_for_prompt(utterances)
                sit = call_gemini(dialogue_text)

                rec = SituationRecord(
                    dialogue_id=str(dlg_id),
                    situation=sit,
                    A_style=a_style,
                    B_style=b_style,
                )
                out.write(rec.model_dump_json(ensure_ascii=False) + "\n")
                n_ok += 1
                time.sleep(API_SLEEP_SECONDS)

                logger.info(
                    "[OK] %s -> theme=%s, A_style=%s, B_style=%s",
                    fp, sit.theme, a_style, b_style,
                )

            except (ValidationError, ValueError, JSONDecodeError) as e:
                n_ng += 1
                logger.error("[NG] %s: %s", fp, e)

    logger.info("Done. OK=%d, NG=%d, out=%s", n_ok, n_ng, OUT_PATH)


if __name__ == "__main__":
    main()
