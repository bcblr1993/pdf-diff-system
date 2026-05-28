"""文档级 / 页级字符流 diff + bbox 反查 + 同位置聚类 + 块位移识别。"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher
from .stream import PageStream, DocStream, Char
from .stamp_mask import bbox_in_any
from .normalize import normalize
from .key_fields import compare_fields, FieldDiff


@dataclass
class DiffItem:
    id: str
    category: str
    severity: str
    orig_page: int
    scan_page: int
    orig_text: str
    scan_text: str
    orig_bbox: tuple[float, float, float, float] | None
    scan_bbox: tuple[float, float, float, float] | None
    context: str = ""
    is_footer: bool = False

    def to_dict(self):
        return asdict(self)


CRITICAL_KEYWORDS = (
    "合同编号", "金额", "总价", "单价", "账号", "税号", "开户行",
    "电话", "传真", "签订日期", "甲方", "乙方", "法定代表人",
)


def _is_critical(context: str) -> bool:
    return any(k in context for k in CRITICAL_KEYWORDS)


def _bbox_union(chars_slice: list[Char]) -> tuple[float, float, float, float] | None:
    """对一段字符的 bbox 求并集（用于高亮框）。
    跨行时按行分组——这里简化：返回所有字符的整体外接框。
    更精细可在调用侧按 line_id 切分。"""
    if not chars_slice:
        return None
    xs0 = [c.bbox[0] for c in chars_slice]
    ys0 = [c.bbox[1] for c in chars_slice]
    xs1 = [c.bbox[2] for c in chars_slice]
    ys1 = [c.bbox[3] for c in chars_slice]
    return (min(xs0), min(ys0), max(xs1), max(ys1))


def _bbox_groups_by_line(chars_slice: list[Char]) -> list[tuple[tuple, list[Char]]]:
    """按 line_id 分组，每组返回 (line_bbox 子区域, chars)。跨行差异会生成多个高亮框。"""
    if not chars_slice:
        return []
    groups: list[tuple[tuple, list[Char]]] = []
    current_id = None
    current: list[Char] = []
    for c in chars_slice:
        if c.line_id != current_id:
            if current:
                groups.append((_bbox_union(current), current))
            current = [c]
            current_id = c.line_id
        else:
            current.append(c)
    if current:
        groups.append((_bbox_union(current), current))
    return groups


def diff_page_pair(orig_ps: PageStream | None, scan_ps: PageStream | None,
                   *,
                   stamp_regions: list[tuple] | None = None,
                   idx_offset: int = 0) -> list[DiffItem]:
    """对一对页面做字符流 diff。返回差异条目，每条已带高亮 bbox。"""
    items: list[DiffItem] = []
    # 整页缺失
    if orig_ps is None and scan_ps is not None:
        # 扫描件多出的整页（如多出的盖章页）
        return _whole_page_diff(scan_ps, side="scan", idx_offset=idx_offset)
    if scan_ps is None and orig_ps is not None:
        return _whole_page_diff(orig_ps, side="orig", idx_offset=idx_offset)
    if orig_ps is None or scan_ps is None:
        return items

    a = orig_ps.norm_text
    b = scan_ps.norm_text
    if a == b:
        return items

    sm = SequenceMatcher(a=a, b=b, autojunk=False)
    opcodes = sm.get_opcodes()
    # 合并相邻非 equal opcode 为聚类
    clusters = _cluster_opcodes(opcodes)

    # 第一遍：块位移识别 —— 把 delete 块和 insert 块两两配对，相似度高则视为 move
    clusters = _detect_moves(clusters, orig_ps, scan_ps)

    sub = 0
    for op_kind, ai1, ai2, bj1, bj2 in clusters:
        # 反查原始 char 索引
        o_chars = _slice_chars(orig_ps, ai1, ai2)
        s_chars = _slice_chars(scan_ps, bj1, bj2)
        o_text = "".join(c.ch for c in o_chars)
        s_text = "".join(c.ch for c in s_chars)

        context_line = (o_chars[0].line_text if o_chars else "") or (s_chars[0].line_text if s_chars else "")
        critical = _is_critical(context_line)
        is_footer = any(c.is_footer for c in (o_chars + s_chars))

        # 章遮挡判定
        covered = False
        if stamp_regions and s_chars:
            bb = _bbox_union(s_chars)
            if bb and bbox_in_any(bb, stamp_regions, overlap_ratio=0.2):
                covered = True

        # 分类
        if op_kind == "moved":
            category = "moved"
        elif covered:
            category = "stamp_covered"
        elif op_kind == "insert":
            category = "handwritten" if _looks_handwritten(s_chars, o_chars) else "insert"
        elif op_kind == "delete":
            category = "delete"
        else:
            category = "replace"

        # 跨行的差异 → 拆成多条（每行一个高亮框）
        o_groups = _bbox_groups_by_line(o_chars) if o_chars else [(None, [])]
        s_groups = _bbox_groups_by_line(s_chars) if s_chars else [(None, [])]
        max_groups = max(len(o_groups), len(s_groups))
        for gi in range(max_groups):
            o_g = o_groups[gi] if gi < len(o_groups) else (None, [])
            s_g = s_groups[gi] if gi < len(s_groups) else (None, [])
            o_bb, o_chunk = o_g
            s_bb, s_chunk = s_g
            items.append(DiffItem(
                id=f"d{idx_offset}-{sub}",
                category=category,
                severity="critical" if critical else ("info" if is_footer else "normal"),
                orig_page=orig_ps.page,
                scan_page=scan_ps.page,
                orig_text="".join(c.ch for c in o_chunk) if o_chunk else (o_text if gi == 0 else ""),
                scan_text="".join(c.ch for c in s_chunk) if s_chunk else (s_text if gi == 0 else ""),
                orig_bbox=o_bb,
                scan_bbox=s_bb,
                context=context_line,
                is_footer=is_footer,
            ))
            sub += 1
    return items


def _slice_chars(ps: PageStream, ni1: int, ni2: int) -> list[Char]:
    """从规范化字符串区间 [ni1, ni2) 反查回原始 Char 列表。"""
    if ni2 <= ni1:
        return []
    if ni1 >= len(ps.norm_to_orig):
        return []
    start = ps.norm_to_orig[ni1]
    end_norm = min(ni2 - 1, len(ps.norm_to_orig) - 1)
    end = ps.norm_to_orig[end_norm] + 1
    return ps.chars[start:end]


def _detect_moves(clusters, orig_ps: PageStream, scan_ps: PageStream,
                  min_len: int = 3, sim_threshold: float = 0.85):
    """块位移识别：把 delete 块和 insert 块两两配对。

    标准 diff 不识别 move，只产生 delete + insert。
    本函数对所有 delete 和 insert 做相似度匹配：相似度 ≥ 阈值的配对，标记为 'moved'。
    """
    # 收集 delete 与 insert
    delete_idxs = [i for i, c in enumerate(clusters) if c[0] == "delete"]
    insert_idxs = [i for i, c in enumerate(clusters) if c[0] == "insert"]
    if not delete_idxs or not insert_idxs:
        return clusters

    # 预计算每段文本
    def _seg_text(side: str, c) -> str:
        _, ai1, ai2, bj1, bj2 = c
        if side == "a":
            return orig_ps.norm_text[ai1:ai2]
        return scan_ps.norm_text[bj1:bj2]

    del_texts = {i: _seg_text("a", clusters[i]) for i in delete_idxs}
    ins_texts = {j: _seg_text("b", clusters[j]) for j in insert_idxs}

    # 计算所有配对相似度，按降序贪心匹配
    pairs: list[tuple[float, int, int]] = []
    for i in delete_idxs:
        a = del_texts[i]
        if len(a) < min_len:
            continue
        for j in insert_idxs:
            b = ins_texts[j]
            if len(b) < min_len:
                continue
            # 长度差太大直接跳过（剪枝）
            if max(len(a), len(b)) / min(len(a), len(b)) > 3:
                continue
            r = SequenceMatcher(a=a, b=b, autojunk=False).ratio()
            if r >= sim_threshold:
                pairs.append((r, i, j))

    pairs.sort(reverse=True)
    used_del: set[int] = set()
    used_ins: set[int] = set()
    moved_pairs: dict[int, int] = {}  # delete idx → insert idx
    for r, i, j in pairs:
        if i in used_del or j in used_ins:
            continue
        used_del.add(i)
        used_ins.add(j)
        moved_pairs[i] = j

    if not moved_pairs:
        return clusters

    # 重建 clusters：被配对的 delete 升级为 'moved' 并合并 insert 范围；对应的 insert 删除
    new_clusters = []
    skip_ins: set[int] = set(moved_pairs.values())
    for idx, c in enumerate(clusters):
        if idx in moved_pairs:
            # 这是位移 from 端：保留 orig 范围，scan 范围用配对 insert 的
            ins = clusters[moved_pairs[idx]]
            new_clusters.append(("moved", c[1], c[2], ins[3], ins[4]))
        elif idx in skip_ins:
            continue
        else:
            new_clusters.append(c)
    return new_clusters


def _split_replaces(opcodes):
    """把每个 replace 拆成相邻的 delete + insert。

    例如 replace a[i1:i2] b[j1:j2] →
        delete  a[i1:i2] (b 部分 bj1=bj2=j1)
        insert  (a 部分 ai1=ai2=i2) b[j1:j2]

    拆开后 move detection 才能在重复内容里逐个匹配；
    后续 _merge_adjacent_delete_insert 会把未匹配的相邻对合并回 replace。
    """
    out = []
    for op in opcodes:
        kind, ai1, ai2, bj1, bj2 = op
        if kind == "replace":
            if ai2 > ai1:
                out.append(("delete", ai1, ai2, bj1, bj1))
            if bj2 > bj1:
                out.append(("insert", ai2, ai2, bj1, bj2))
        else:
            out.append(op)
    return out


def _merge_adjacent_delete_insert(clusters):
    """把紧邻的 (delete, insert) 或 (insert, delete) 合并回 replace。

    "紧邻" 定义：两者的字符流区间相接（_split_replaces 拆出来的就是这种关系）。
    move detection 已经把能配对的标为 moved 了，剩下未配对的相邻 d+i 才会被合回 replace。
    """
    out = []
    i = 0
    while i < len(clusters):
        c = clusters[i]
        if i + 1 < len(clusters):
            n = clusters[i + 1]
            d, ins = None, None
            if c[0] == "delete" and n[0] == "insert":
                d, ins = c, n
            elif c[0] == "insert" and n[0] == "delete":
                ins, d = c, n
            if d and ins:
                # 紧邻判定：原件范围相接 且 扫描件范围相接
                if d[2] == ins[1] and d[3] == ins[3]:
                    out.append(("replace", d[1], d[2], ins[3], ins[4]))
                    i += 2
                    continue
        out.append(c)
        i += 1
    return out


def _cluster_opcodes(opcodes, gap: int = 1):
    """把相邻的非 equal opcode 合并成簇。

    合并规则：
    - 只合并**同类型**相邻的 opcode（delete-delete、insert-insert、replace-replace）
    - 短 equal（≤ gap）允许出现在簇内不打断
    - 当簇内同时含 delete 和 insert 时**拆开输出**——这样 move detection 才能逐个匹配
    - replace 保持原样（SequenceMatcher 已识别为对位替换）
    """
    out: list[tuple[str, int, int, int, int]] = []
    buf: list[tuple[str, int, int, int, int]] = []

    def flush():
        if not buf:
            return
        kinds = {x[0] for x in buf if x[0] != "equal"}
        # 同类型簇：合并为一个
        if len(kinds) == 1:
            ai1 = buf[0][1]
            ai2 = buf[-1][2]
            bj1 = buf[0][3]
            bj2 = buf[-1][4]
            out.append((kinds.pop(), ai1, ai2, bj1, bj2))
        else:
            # 异类型（delete+insert 共存）：保持原 opcode 独立输出
            for x in buf:
                if x[0] != "equal":
                    out.append(x)
        buf.clear()

    for op in opcodes:
        kind, ai1, ai2, bj1, bj2 = op
        if kind == "equal":
            if buf and (ai2 - ai1) <= gap:
                buf.append(("equal", ai1, ai2, bj1, bj2))
            else:
                flush()
        else:
            buf.append(op)
    flush()
    return out


_HANDWRITTEN_CONTEXT_KEYWORDS = (
    "合同编号", "签订日期", "法定代表人", "法人代表", "委托代理人",
    "电话", "传真", "账号", "税号", "开户行", "通讯地址", "盖章", "签字", "日期",
)


def _looks_handwritten(s_chars: list[Char], o_chars: list[Char]) -> bool:
    """收紧版手写填空判定：

    必须同时满足：
    1. 纯 insert（原件无对应内容）
    2. 文本短（≤ 8 个字符，过滤 OCR 切碎的正文片段）
    3. 出现在已知填空字段的同一行（context 里有填空关键词）

    其他 insert 一律按普通 'insert' 处理（绿色但不标"手写"）。
    """
    if o_chars or not s_chars:
        return False
    text = "".join(c.ch for c in s_chars).strip()
    if not text or len(text) > 8:
        return False
    if any(c.is_footer for c in s_chars):
        return False
    # 看所在行的 context 是否含填空关键词
    line_text = s_chars[0].line_text or ""
    return any(k in line_text for k in _HANDWRITTEN_CONTEXT_KEYWORDS)


# ─────────────────────────── 文档级 diff ───────────────────────────

def _slice_chars_doc(ds: DocStream, ni1: int, ni2: int) -> list[Char]:
    if ni2 <= ni1 or ni1 >= len(ds.norm_to_orig):
        return []
    start = ds.norm_to_orig[ni1]
    end_norm = min(ni2 - 1, len(ds.norm_to_orig) - 1)
    end = ds.norm_to_orig[end_norm] + 1
    return ds.chars[start:end]


def _group_by_page_line(chars_slice: list[Char]) -> list[tuple[int, int, tuple, list[Char]]]:
    """按 (page, line_id) 分组。返回 [(page, line_id, bbox_union, chars), ...]，保持顺序。"""
    if not chars_slice:
        return []
    groups: list[tuple[int, int, tuple, list[Char]]] = []
    cur_key: tuple | None = None
    cur: list[Char] = []
    for c in chars_slice:
        key = (c.page, c.line_id)
        if key != cur_key:
            if cur:
                groups.append((cur_key[0], cur_key[1], _bbox_union(cur), cur))
            cur = [c]
            cur_key = key
        else:
            cur.append(c)
    if cur:
        groups.append((cur_key[0], cur_key[1], _bbox_union(cur), cur))
    return groups


def _detect_moves_doc(clusters, orig_doc: DocStream, scan_doc: DocStream,
                      min_len: int = 1, sim_threshold: float = 0.75):
    """文档级块位移识别（强化版）。

    匹配策略：
    - 短串（≤ 3 字）：必须**完全相等**才配对（避免短串误匹配）
    - 长串：相似度 ≥ sim_threshold
    - 候选对按 (相似度↓, 位置距离↑) 排序——位置就近优先，解决重复内容歧义
    """
    delete_idxs = [i for i, c in enumerate(clusters) if c[0] == "delete"]
    insert_idxs = [i for i, c in enumerate(clusters) if c[0] == "insert"]
    if not delete_idxs or not insert_idxs:
        return clusters

    def _seg(side, c):
        _, ai1, ai2, bj1, bj2 = c
        return orig_doc.norm_text[ai1:ai2] if side == "a" else scan_doc.norm_text[bj1:bj2]

    del_texts = {i: _seg("a", clusters[i]) for i in delete_idxs}
    ins_texts = {j: _seg("b", clusters[j]) for j in insert_idxs}

    total_len = max(len(orig_doc.norm_text), len(scan_doc.norm_text), 1)

    pairs: list[tuple[float, float, int, int]] = []
    for i in delete_idxs:
        a = del_texts[i]
        if len(a) < min_len:
            continue
        ai1 = clusters[i][1]
        for j in insert_idxs:
            b = ins_texts[j]
            if len(b) < min_len:
                continue
            # 短串：必须完全相等
            if len(a) <= 3 or len(b) <= 3:
                if a != b:
                    continue
                score = 1.0
            else:
                if max(len(a), len(b)) / min(len(a), len(b)) > 3:
                    continue
                score = SequenceMatcher(a=a, b=b, autojunk=False).ratio()
                if score < sim_threshold:
                    continue
            # 位置就近：用规范化位置距离
            bj1 = clusters[j][3]
            pos_dist = abs(ai1 - bj1) / total_len
            pairs.append((score, pos_dist, i, j))

    # 排序：相似度高优先；相同相似度时位置近优先
    pairs.sort(key=lambda x: (-x[0], x[1]))

    used_del: set[int] = set()
    used_ins: set[int] = set()
    moved: dict[int, int] = {}
    for score, dist, i, j in pairs:
        if i in used_del or j in used_ins:
            continue
        used_del.add(i)
        used_ins.add(j)
        moved[i] = j

    if not moved:
        return clusters

    new_clusters = []
    skip_ins = set(moved.values())
    for idx, c in enumerate(clusters):
        if idx in moved:
            ins = clusters[moved[idx]]
            new_clusters.append(("moved", c[1], c[2], ins[3], ins[4]))
        elif idx in skip_ins:
            continue
        else:
            new_clusters.append(c)
    return new_clusters


def diff_documents(orig_doc: DocStream, scan_doc: DocStream,
                   *,
                   stamp_regions_per_page: dict[int, list[tuple]] | None = None) -> list[DiffItem]:
    """文档级字符流 diff。跨页对齐，每个 diff 项已带页号路由。

    v11：在字符流 diff 之前先跑「关键字段抽取与比对」，把合同编号、金额、账号、
    电话、税号、法人等结构化差异作为高置信度 DiffItem 置顶（severity=critical）。
    """
    items: list[DiffItem] = []

    # —— v11：关键字段差异（置顶 + critical）——
    items.extend(_field_level_diffs(orig_doc, scan_doc))

    a = orig_doc.norm_text
    b = scan_doc.norm_text
    if not a and not b:
        return items
    if a == b:
        return items

    sm = SequenceMatcher(a=a, b=b, autojunk=False)
    opcodes = sm.get_opcodes()
    # 1) 把所有 replace 拆成 delete + insert，让 move detection 能逐个匹配重复内容
    opcodes = _split_replaces(opcodes)
    # 2) 只保留非 equal opcodes（SequenceMatcher 输出已规范化，不需要 cluster 合并）
    clusters = [op for op in opcodes if op[0] != "equal"]
    # 3) move 配对（"签订日期"等同名内容跨位置匹配）
    clusters = _detect_moves_doc(clusters, orig_doc, scan_doc)
    # 4) 把未匹配且紧邻的 delete+insert 合并回 replace（保留 "仟→任" 等对位关系）
    clusters = _merge_adjacent_delete_insert(clusters)

    sub = 0
    stamp_regions_per_page = stamp_regions_per_page or {}
    for op_kind, ai1, ai2, bj1, bj2 in clusters:
        o_chars = _slice_chars_doc(orig_doc, ai1, ai2)
        s_chars = _slice_chars_doc(scan_doc, bj1, bj2)
        if not o_chars and not s_chars:
            continue

        o_groups = _group_by_page_line(o_chars)
        s_groups = _group_by_page_line(s_chars)

        # 上下文行（取第一个 group 的所在行文本）
        context_line = (o_groups[0][3][0].line_text if o_groups else "") or \
                       (s_groups[0][3][0].line_text if s_groups else "")
        critical = _is_critical(context_line)

        # 按"组数最大值"对齐发射，缺侧补 None
        max_g = max(len(o_groups), len(s_groups), 1)
        for gi in range(max_g):
            o_g = o_groups[gi] if gi < len(o_groups) else None
            s_g = s_groups[gi] if gi < len(s_groups) else None
            o_page = o_g[0] if o_g else -1
            s_page = s_g[0] if s_g else -1
            o_bb = o_g[2] if o_g else None
            s_bb = s_g[2] if s_g else None
            o_text = "".join(c.ch for c in o_g[3]) if o_g else ""
            s_text = "".join(c.ch for c in s_g[3]) if s_g else ""

            is_footer = (
                (o_g and o_g[3][0].is_footer) or (s_g and s_g[3][0].is_footer)
            )

            # 章遮挡判定（按扫描件的页查 stamp_regions）
            covered = False
            if s_bb is not None and s_page >= 0:
                regions = stamp_regions_per_page.get(s_page, [])
                if regions and bbox_in_any(s_bb, regions, overlap_ratio=0.2):
                    covered = True

            if op_kind == "moved":
                category = "moved"
            elif covered:
                category = "stamp_covered"
            elif op_kind == "insert":
                category = "handwritten" if _looks_handwritten(s_g[3] if s_g else [], []) else "insert"
            elif op_kind == "delete":
                category = "delete"
            else:
                category = "replace"

            # 严重度：critical / info / normal
            if critical:
                sev = "critical"
            elif is_footer:
                sev = "info"
            elif category in ("delete", "insert") and (len(o_text) + len(s_text)) <= 2:
                # ≤2 字符的 delete/insert 残留绝大多数是 OCR 配对错位的副产物，降级
                # 关键字段（critical）已优先命中，不会被降级
                sev = "info"
            else:
                sev = "normal"

            items.append(DiffItem(
                id=f"d{sub}",
                category=category,
                severity=sev,
                orig_page=o_page,
                scan_page=s_page,
                orig_text=o_text,
                scan_text=s_text,
                orig_bbox=o_bb,
                scan_bbox=s_bb,
                context=context_line,
                is_footer=bool(is_footer),
            ))
            sub += 1
    return items


# ─────────────────────── 旧的页级整页 diff（保留兼容）───────────────────────

def _whole_page_diff(ps: PageStream, *, side: str, idx_offset: int) -> list[DiffItem]:
    """整页只有一侧存在时的处理。"""
    items: list[DiffItem] = []
    # 按行聚合，每行一条
    if not ps.chars:
        return items
    line_groups: dict[int, list[Char]] = {}
    for c in ps.chars:
        line_groups.setdefault(c.line_id, []).append(c)
    for li, chars in line_groups.items():
        bb = _bbox_union(chars)
        text = "".join(c.ch for c in chars)
        if not text.strip():
            continue
        is_footer = chars[0].is_footer
        items.append(DiffItem(
            id=f"d{idx_offset}-w{li}",
            category="insert" if side == "scan" else "delete",
            severity="info" if is_footer else "normal",
            orig_page=ps.page if side == "orig" else -1,
            scan_page=ps.page if side == "scan" else -1,
            orig_text=text if side == "orig" else "",
            scan_text=text if side == "scan" else "",
            orig_bbox=bb if side == "orig" else None,
            scan_bbox=bb if side == "scan" else None,
            context=text,
            is_footer=is_footer,
        ))
    return items


# ─────────────────────── v11：关键字段差异层 ───────────────────────


def _field_level_diffs(orig_doc: DocStream, scan_doc: DocStream) -> list[DiffItem]:
    """跑关键字段比对，转成 DiffItem 列表（全部 critical 置顶）。

    bbox 通过 norm_text 位置映射到 chars[i].bbox 反查。
    """
    items: list[DiffItem] = []
    field_diffs = compare_fields(orig_doc.norm_text, scan_doc.norm_text)
    for i, fd in enumerate(field_diffs):
        items.append(_field_diff_to_item(orig_doc, scan_doc, fd, i))
    return items


# 字段差异 kind → 分类
_FIELD_KIND_CATEGORY = {
    "changed": "replace",
    "missing_in_orig": "insert",    # 原件没 / 扫描件有 = 新增
    "missing_in_scan": "delete",    # 原件有 / 扫描件没 = 删除
    "added": "insert",
    "removed": "delete",
}


def _field_diff_to_item(orig_doc: DocStream, scan_doc: DocStream,
                        fd: FieldDiff, idx: int) -> DiffItem:
    """单条字段差异 → DiffItem。位置 → bbox/page 反查。"""

    def _locate(doc: DocStream, norm_pos: int, length: int) -> tuple[int, tuple | None]:
        """norm_text 位置 → (page, bbox)。"""
        if norm_pos < 0 or norm_pos >= len(doc.norm_to_orig):
            return -1, None
        start = doc.norm_to_orig[norm_pos]
        end_norm = min(norm_pos + length - 1, len(doc.norm_to_orig) - 1)
        end = doc.norm_to_orig[end_norm] + 1
        chars = doc.chars[start:end]
        if not chars:
            return -1, None
        page = chars[0].page
        xs0 = [c.bbox[0] for c in chars]
        ys0 = [c.bbox[1] for c in chars]
        xs1 = [c.bbox[2] for c in chars]
        ys1 = [c.bbox[3] for c in chars]
        bbox = (min(xs0), min(ys0), max(xs1), max(ys1))
        return page, bbox

    o_page, o_bbox = (-1, None)
    s_page, s_bbox = (-1, None)
    if fd.orig_pos >= 0:
        o_page, o_bbox = _locate(orig_doc, fd.orig_pos, len(fd.orig_value))
    if fd.scan_pos >= 0:
        s_page, s_bbox = _locate(scan_doc, fd.scan_pos, len(fd.scan_value))

    category = _FIELD_KIND_CATEGORY.get(fd.kind, "replace")
    label_prefix = {
        "changed": "已变更",
        "missing_in_orig": "原件缺失",
        "missing_in_scan": "扫描件缺失",
        "added": "新增",
        "removed": "删除",
    }.get(fd.kind, "字段差异")

    return DiffItem(
        id=f"f{idx}",
        category=category,
        severity="critical",
        orig_page=o_page,
        scan_page=s_page,
        orig_text=fd.orig_value,
        scan_text=fd.scan_value,
        orig_bbox=o_bbox,
        scan_bbox=s_bbox,
        context=f"【关键字段·{fd.label}·{label_prefix}】",
        is_footer=False,
    )
