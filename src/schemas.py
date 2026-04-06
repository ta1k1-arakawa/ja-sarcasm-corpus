"""
共通スキーマモジュール

パイプライン全体で共有する Pydantic モデルを定義する。
"""

from typing import Dict, List

from pydantic import BaseModel, Field, constr


# =============================
# 状況抽出 (situation.py 用)
# =============================
class Situation(BaseModel):
    """対話から抽出された状況情報"""

    theme: constr(strip_whitespace=True, min_length=2, max_length=30) = Field(
        ..., description="主題（10～20字程度を推奨）"
    )
    summary: constr(strip_whitespace=True, min_length=5, max_length=200) = Field(
        ..., description="状況を1文で簡潔に説明"
    )


class SituationRecord(BaseModel):
    """状況抽出の出力レコード"""

    dialogue_id: str
    situation: Situation
    A_style: str
    B_style: str


# =============================
# 皮肉生成 (generate_sarcasm.py 用)
# =============================
class Utterance(BaseModel):
    """発話単体を表現するモデル"""

    speaker: str
    text: str


class GeneratedSarcasm(BaseModel):
    """Gemini が返す JSON の構造を検証するためのモデル"""

    context: List[Utterance]
    sarcasm_explanation: constr(strip_whitespace=True, min_length=10)
    sarcastic_response: Utterance


class FinalRecord(BaseModel):
    """最終的にファイルに出力するレコードの構造"""

    original_dialogue_id: str
    original_situation: Situation
    speaker_styles: Dict[str, str]
    context: List[Utterance] = Field(
        ..., description="皮肉な応答の直前までの対話コンテキスト"
    )
    response: Utterance = Field(..., description="皮肉な応答（ターゲット発話）")
    sarcasm_explanation: str = Field(
        ..., description="応答がなぜ皮肉なのかの説明"
    )
