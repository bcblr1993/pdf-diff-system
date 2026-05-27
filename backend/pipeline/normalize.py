"""文本规范化：全半角、形近字、空白。用于比对，不影响最终展示。"""
from __future__ import annotations
import unicodedata
import re

# OCR 常见形近字归一（key→value）
LOOKALIKE = {
    "O": "0",
    "o": "0",
    "l": "1",
    "I": "1",
    "L": "1",
    "丨": "1",
    "S": "5",
    "s": "5",
    "Z": "2",
    "z": "2",
    "B": "8",
    "g": "9",
    "q": "9",
    "·": ".",
    "•": ".",
    ",": ",",
    "。": ".",
    "，": ",",
    "：": ":",
    "；": ";",
    # 中文 OCR 常见误识：分号↔冒号、句号↔逗号
    ";": ":",   # 注意：会让 ; 和 : 视作相等，仅 OCR 容错用
    "、": ",",
    "（": "(",
    "）": ")",
    "【": "[",
    "】": "]",
    "「": "[",
    "」": "]",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
    "–": "-",
    "—": "-",
    "─": "-",
    "_": "_",
}

_WS_RE = re.compile(r"\s+")


def normalize(s: str, *, lookalike: bool = True) -> str:
    """规范化：NFKC + 去空白 + 形近字归一。"""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = _WS_RE.sub("", s)
    if lookalike:
        s = "".join(LOOKALIKE.get(ch, ch) for ch in s)
    return s


def normalize_keep_pos(s: str, *, lookalike: bool = True) -> tuple[str, list[int]]:
    """规范化同时保留原索引映射：返回(规范化后的串, 每个新字符在原串中的索引)。
    用于把规范化层 diff 出的位置反查回原始字符位置。
    """
    if not s:
        return "", []
    nfkc = unicodedata.normalize("NFKC", s)
    # NFKC 可能把一字变多字（如全角→半角通常 1:1，但合字会变化）。
    # 为简单起见，按字符位置粗略对齐：先做 NFKC，再过滤空白和应用 lookalike，按位置一一保留。
    out_chars: list[str] = []
    idx_map: list[int] = []
    # 简化：把原始串字符级处理（不再用 NFKC 整体），保持索引可控。
    for i, ch in enumerate(s):
        nch = unicodedata.normalize("NFKC", ch)
        if not nch or nch.isspace():
            continue
        # 取第一个字符（NFKC 通常 1:1）
        c = nch[0]
        if lookalike:
            c = LOOKALIKE.get(c, c)
        out_chars.append(c)
        idx_map.append(i)
    return "".join(out_chars), idx_map
