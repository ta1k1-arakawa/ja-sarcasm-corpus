import os, glob, json, time, re
from typing import List, Optional
from pydantic import BaseModel, Field, ValidationError, constr
from tenacity import retry, wait_exponential, stop_after_attempt
import google.generativeai as genai
from dotenv import load_dotenv

# =============================
# Config & Env
# =============================
load_dotenv()  # read .env if present
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
OUT_PATH = os.getenv("OUT_PATH", "situations.jsonl")

assert GOOGLE_API_KEY, "❌ GOOGLE_API_KEY が .env に設定されていません。"
print(f"✅ モデル: {GEMINI_MODEL}")

# Initialize Gemini
genai.configure(api_key=GOOGLE_API_KEY)

generation_config = {
    "temperature": 0.2,
    "top_p": 0.9,
    "top_k": 40,
    "response_mime_type": "application/json",
}
model = genai.GenerativeModel(
    model_name=GEMINI_MODEL,
    generation_config=generation_config,
)

# =============================
# Schemas
# =============================
class Situation(BaseModel):
    theme: constr(strip_whitespace=True, min_length=2, max_length=30) = Field(..., description="主題（10〜20字程度を推奨）")
    summary: constr(strip_whitespace=True, min_length=5, max_length=200) = Field(..., description="状況を1文で簡潔に説明")

class SituationRecord(BaseModel):
    dialogue_id: str
    situation: Situation
    A_style: str
    B_style: str

# =============================
# Prompts
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
# Utilities
# =============================
KEITAI_ENDINGS = (
    "です", "ます", "でした", "ません", "ですね", "でしたね", "でしょう", "でしょうか", "ください",
)
JOUTAI_ENDINGS = (
    "だ", "ない", "よね", "かよ", "じゃん", "だよ", "だな", "だね", "だろ", "だろう",
)

ENDING_RE = re.compile(r"[。.!?！？]\s*$")

def normalize_text_for_ending(text: str) -> str:
    """末尾の句読点等を落として文末判定しやすくする"""
    t = text.strip()
    t = ENDING_RE.sub("", t)
    return t

def detect_style(utterances: List[dict], speaker_id: str) -> str:
    """各話者の発話末尾を見て敬体/常体を推定。閾値は単純多数決。
    いずれにも合致しない場合は '混合' を返す。"""
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


def format_dialogue_for_prompt(utterances: List[dict], max_turns: Optional[int] = None) -> str:
    uts = utterances[-max_turns:] if max_turns else utterances
    lines = []
    for u in uts:
        spk = u.get("interlocutor_id", "UNK")
        txt = u.get("text", "").strip().replace("\n", " ")
        lines.append(f"{spk}: {txt}")
    return "\n".join(lines)

# =============================
# Gemini Call
# =============================
from json import JSONDecodeError
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5))
def call_gemini(dialogue_text: str) -> Situation:
    prompt = f"{SYSTEM_HINT}\n\n# 入力対話\n{dialogue_text}"
    resp = model.generate_content([prompt])

    if resp.usage_metadata:
        in_tok = resp.usage_metadata.prompt_token_count
        out_tok = resp.usage_metadata.candidates_token_count
        print(f"  (Tokens: In={in_tok}, Out={out_tok})")

    # SDK差異に備えて堅く取り出す
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
# IO
# =============================

def load_dialogue(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "utterances" in data:
        dlg_id = str(data.get("dialogue_id") or os.path.basename(file_path))
        return dlg_id, data["utterances"]
    if isinstance(data, list) and data and isinstance(data[0], dict) and "utterances" in data[0]:
        dlg_id = str(data[0].get("dialogue_id") or os.path.basename(file_path))
        return dlg_id, data[0]["utterances"]
    raise ValueError(f"未知のJSON構造: {file_path}")

# =============================
# Main
# =============================

def main():
    #入力素材
    dialogue_dir = "./dialogues"  
    start_index = 501
    end_index = 1200

    files = []
    print(f"フォルダ {dialogue_dir} 内の {start_index:05d}.json から {end_index:05d}.json までを処理します...")

    # 2. ファイル名のリストをループで作成
    for i in range(start_index, end_index + 1):
        # "00005.json" のように5桁ゼロ埋めのファイル名を作成
        filename = f"{i:05d}.json"
        
        # フォルダパスとファイル名を結合してフルパスを作成
        file_path = os.path.join(dialogue_dir, filename)
        
        # 3. ファイルが存在するか確認（安全のため）
        if os.path.exists(file_path):
            files.append(file_path)
        else:
            print(f"[警告] スキップ: {file_path} が見つかりません。")

    assert files, f"指定された範囲のファイルが1件も見つかりませんでした。"
    n_ok, n_ng = 0, 0

    with open(OUT_PATH, "w", encoding="utf-8") as out:
        for fp in files:
            try:
                dlg_id, utterances = load_dialogue(fp)

                # 話者ID 2名を推定（最初の2発話のinterlocutor_idを採用）
                if len(utterances) < 2:
                    raise ValueError("発話が2つ未満です")
                A_id = utterances[0].get("interlocutor_id")
                # Bは最初と異なる話者を探索
                B_id = None
                for u in utterances[1:]:
                    if u.get("interlocutor_id") != A_id:
                        B_id = u.get("interlocutor_id")
                        break
                if not B_id:
                    raise ValueError("2人の話者が特定できません")

                A_style = detect_style(utterances, A_id)
                B_style = detect_style(utterances, B_id)

                dialogue_text = format_dialogue_for_prompt(utterances)
                sit = call_gemini(dialogue_text)

                rec = SituationRecord(
                    dialogue_id=str(dlg_id),
                    situation=sit,
                    A_style=A_style,
                    B_style=B_style,
                )
                out.write(rec.model_dump_json(ensure_ascii=False) + "\n")
                n_ok += 1
                time.sleep(4.1)  # 軽いスロットリング
                print(f"[OK] {fp} -> theme={sit.theme}, A_style={A_style}, B_style={B_style}")
            except (ValidationError, ValueError, JSONDecodeError) as e:
                n_ng += 1
                print(f"[NG] {fp}: {e}")

    print(f"\nDone. OK={n_ok}, NG={n_ng}, out={OUT_PATH}")

if __name__ == "__main__":
    main()
