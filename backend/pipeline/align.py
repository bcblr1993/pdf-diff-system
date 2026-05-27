"""三级对齐：页 → 块/段落 → 行。"""
from __future__ import annotations
from dataclasses import dataclass
from .normalize import normalize


@dataclass
class LinePair:
    orig_page: int
    scan_page: int
    orig_line: object | None  # TextLine
    scan_line: object | None  # OcrLine


def _line_text(line) -> str:
    return getattr(line, "text", "") if line is not None else ""


def _ngram_set(text: str, n: int = 3) -> set[str]:
    t = normalize(text)
    if len(t) < n:
        return {t} if t else set()
    return {t[i:i + n] for i in range(len(t) - n + 1)}


def _page_fingerprint(lines: list, top_k: int = 8) -> set[str]:
    """页指纹：前 top_k 行的 3-gram 并集。"""
    fp: set[str] = set()
    for ln in lines[:top_k]:
        fp |= _ngram_set(_line_text(ln))
    return fp


def _sim(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / max(1, len(a | b))


def align_pages(orig_pages, scan_pages, sim_threshold: float = 0.1):
    """页对齐：单调对齐 + Needleman-Wunsch 风格 DP。"""
    n = len(orig_pages)
    m = len(scan_pages)
    fps_o = [_page_fingerprint(p.lines) for p in orig_pages]
    fps_s = [_page_fingerprint(p.lines) for p in scan_pages]

    # DP: dp[i][j] = 最大累计相似度
    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    bt = [[0] * (m + 1) for _ in range(n + 1)]  # 0=skip orig, 1=skip scan, 2=pair
    GAP = -0.05
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = _sim(fps_o[i - 1], fps_s[j - 1])
            pair = dp[i - 1][j - 1] + (s if s >= sim_threshold else GAP)
            skip_o = dp[i - 1][j] + GAP
            skip_s = dp[i][j - 1] + GAP
            best = max(pair, skip_o, skip_s)
            dp[i][j] = best
            bt[i][j] = 2 if best == pair else (0 if best == skip_o else 1)
    # 回溯
    pairs: list[tuple[int | None, int | None]] = []
    i, j = n, m
    while i > 0 and j > 0:
        op = bt[i][j]
        if op == 2:
            pairs.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif op == 0:
            pairs.append((i - 1, None))
            i -= 1
        else:
            pairs.append((None, j - 1))
            j -= 1
    while i > 0:
        pairs.append((i - 1, None))
        i -= 1
    while j > 0:
        pairs.append((None, j - 1))
        j -= 1
    pairs.reverse()
    return pairs


def align_lines(orig_lines: list, scan_lines: list,
                gap_penalty: float = -0.4,
                match_threshold: float = 0.5) -> list[LinePair]:
    """页内行对齐：Needleman-Wunsch，得分=两行文本的字符级相似度。"""
    n = len(orig_lines)
    m = len(scan_lines)
    # 预算相似度
    norm_o = [normalize(_line_text(ln)) for ln in orig_lines]
    norm_s = [normalize(_line_text(ln)) for ln in scan_lines]

    def sim(i: int, j: int) -> float:
        a, b = norm_o[i], norm_s[j]
        if not a and not b:
            return 0.0
        # 用 LCS 长度/最大长度 作为相似度（粗略但够用）
        lcs = _lcs_len(a, b)
        return lcs / max(len(a), len(b), 1)

    dp = [[0.0] * (m + 1) for _ in range(n + 1)]
    bt = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = dp[i - 1][0] + gap_penalty
        bt[i][0] = 1
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + gap_penalty
        bt[0][j] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = sim(i - 1, j - 1)
            score = s if s >= match_threshold else (s - 0.3)
            diag = dp[i - 1][j - 1] + score
            up = dp[i - 1][j] + gap_penalty
            left = dp[i][j - 1] + gap_penalty
            best = max(diag, up, left)
            dp[i][j] = best
            bt[i][j] = 0 if best == diag else (1 if best == up else 2)

    pairs: list[LinePair] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and bt[i][j] == 0:
            orig_l = orig_lines[i - 1]
            scan_l = scan_lines[j - 1]
            pairs.append(LinePair(
                orig_page=getattr(orig_l, "page", -1),
                scan_page=getattr(scan_l, "page", -1),
                orig_line=orig_l,
                scan_line=scan_l,
            ))
            i -= 1
            j -= 1
        elif i > 0 and (j == 0 or bt[i][j] == 1):
            orig_l = orig_lines[i - 1]
            pairs.append(LinePair(
                orig_page=getattr(orig_l, "page", -1),
                scan_page=-1,
                orig_line=orig_l,
                scan_line=None,
            ))
            i -= 1
        else:
            scan_l = scan_lines[j - 1]
            pairs.append(LinePair(
                orig_page=-1,
                scan_page=getattr(scan_l, "page", -1),
                orig_line=None,
                scan_line=scan_l,
            ))
            j -= 1
    pairs.reverse()
    return pairs


def _lcs_len(a: str, b: str) -> int:
    if not a or not b:
        return 0
    n, m = len(a), len(b)
    if n * m > 200000:
        # 行太长时用 difflib 估算
        from difflib import SequenceMatcher
        sm = SequenceMatcher(a=a, b=b, autojunk=False)
        return int(sm.ratio() * min(n, m))
    dp = [0] * (m + 1)
    for i in range(1, n + 1):
        prev = 0
        ai = a[i - 1]
        for j in range(1, m + 1):
            tmp = dp[j]
            if ai == b[j - 1]:
                dp[j] = prev + 1
            else:
                dp[j] = max(dp[j], dp[j - 1])
            prev = tmp
    return dp[m]
