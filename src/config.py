"""
共通設定モジュール

プロジェクト全体で使用するパス定数、API設定、ユーティリティ関数を提供する。
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Iterator

from dotenv import load_dotenv

# =============================
# プロジェクトパス
# =============================
# src/ の親ディレクトリ = プロジェクトルート
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# 主要ディレクトリ
RAW_DIR = PROJECT_ROOT / "raw"
DATA_DIR = PROJECT_ROOT / "data"
SRC_DIR = PROJECT_ROOT / "src"
PIPELINE_DIR = SRC_DIR / "pipeline"

# raw 配下
DIALOGUES_DIR = RAW_DIR / "dialogues"
MATERIAL_DIR = RAW_DIR / "material"

# data 配下
SAMPLE_DIR = DATA_DIR / "sample"

# =============================
# 環境変数の読み込み
# =============================
load_dotenv(PROJECT_ROOT / ".env")

GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-1.5-flash-lite")

# =============================
# API レートリミット
# =============================
API_SLEEP_SECONDS: float = 4.2


# =============================
# Gemini 初期化
# =============================
def get_gemini_model(
    temperature: float = 1.0,
    top_p: float = 0.95,
    top_k: int = 40,
    response_mime_type: str = "application/json",
):
    """Gemini GenerativeModel を生成して返す。

    Args:
        temperature: 生成の温度パラメータ
        top_p: nucleus sampling の閾値
        top_k: top-k sampling の値
        response_mime_type: レスポンスの MIME タイプ

    Returns:
        google.generativeai.GenerativeModel インスタンス
    """
    import google.generativeai as genai

    assert GOOGLE_API_KEY, "❌ GOOGLE_API_KEY が .env に設定されていません。"

    genai.configure(api_key=GOOGLE_API_KEY)

    generation_config = {
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k,
        "response_mime_type": response_mime_type,
    }
    return genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        generation_config=generation_config,
    )


# =============================
# ロギング設定
# =============================
def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """プロジェクト共通のロガーを設定して返す。

    Args:
        name: ロガー名（通常は __name__ を渡す）
        level: ログレベル

    Returns:
        設定済みの Logger インスタンス
    """
    logger = logging.getLogger(name)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger


# =============================
# JSONL ユーティリティ
# =============================
def write_jsonl(filepath: str | Path, records: list[dict[str, Any]]) -> int:
    """レコードのリストを JSONL ファイルに書き出す。

    Args:
        filepath: 出力先のファイルパス
        records: 書き出すレコードのリスト

    Returns:
        書き出した件数
    """
    with open(filepath, "w", encoding="utf-8") as f:
        for record in records:
            json.dump(record, f, ensure_ascii=False)
            f.write("\n")
    return len(records)


def read_jsonl(filepath: str | Path) -> Iterator[dict[str, Any]]:
    """JSONL ファイルを1行ずつ読み取るジェネレータ。

    Args:
        filepath: 読み込むファイルパス

    Yields:
        パースされた辞書オブジェクト
    """
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def get_dialogue_files(start_id: int, end_id: int) -> list[Path]:
    """指定した ID 範囲の対話 JSON ファイルパスのリストを返す。

    存在しないファイルはスキップし、警告をログに出力する。

    Args:
        start_id: 開始 ID（含む）
        end_id: 終了 ID（含む）

    Returns:
        存在するファイルの Path リスト
    """
    logger = setup_logger(__name__)
    files: list[Path] = []

    for i in range(start_id, end_id + 1):
        filepath = DIALOGUES_DIR / f"{i:05d}.json"
        if filepath.exists():
            files.append(filepath)
        else:
            logger.warning("スキップ: %s が見つかりません。", filepath)

    return files
