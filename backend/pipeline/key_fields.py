"""关键字段抽取器（v11）。

业务动机：合同里的关键字段（合同编号 / 金额 / 账号 / 税号 / 电话 / 日期 / 法人）
原本散落在长文档中，靠字符流 diff 一一对位，遇到表格、布局微移、OCR 噪声很容易
被切成几十条难审的小条目。

本模块用 regex 主动定位这些字段，把每个字段当作"语义单元"独立比对：
  - 一方有、另一方没有  → field_missing
  - 两边都有但值不同     → field_changed
  - 同字段多值（多个电话）→ 集合差异（新增 / 删除）

返回值喂给 diff.py，作为"结构化关键差异"置顶展示，origin 字符流 diff 仍保留兜底。
"""
from __future__ import annotations
from dataclasses import dataclass, field as dc_field
import re
from typing import Iterable

# ─────────────────────────────────────────────────────────
# 字段规则定义
# ─────────────────────────────────────────────────────────


@dataclass
class FieldDef:
    key: str                       # 内部 id
    label: str                     # 中文标签
    # 提取规则：先用 anchor 锚定中文键（"合同编号："、"账号"），再用 value_re 取值
    anchors: list[str]
    value_re: str
    multi: bool = False            # 是否多值（电话 / 账号 一个合同里可能多对）
    severity: str = "critical"     # 默认全部 critical
    # 值规范化（用于比对前的标准化，去掉空格 / 全半角）
    normalize: str = "strip_ws"    # strip_ws / digits_only / keep


def _join_anchors(anchors: Iterable[str]) -> str:
    return "(?:" + "|".join(re.escape(a) for a in anchors) + ")"


# 通用值正则
_PHONE_RE = r"(?:\d{3,4}-)?\d{6,11}"                              # 025-52763388 / 18162271888
_ACCOUNT_RE = r"\d{9,30}"                                          # 长数字串（账号 / 银行账户）
_TAX_ID_RE = r"[A-Z0-9]{15,20}"                                    # 税号
# 金额：要求至少 3 位数字（过滤掉百分号附近的 3%/30% 这种小数字）
_AMOUNT_RE = r"\d{1,3}(?:,?\d{3})+(?:\.\d{1,2})?\s*元?|\d{3,}(?:\.\d{1,2})?\s*元"
_DATE_RE = r"\d{4}\s*年\s*\d{1,2}\s*月\s*\d{0,2}\s*日?"
# 合同编号：必含连字符且首段含字母
_CONTRACT_NO_RE = r"[A-Z]{1,5}[A-Z0-9]*-[A-Z0-9-]{2,30}"
# 姓名：2-4 个汉字，第一个字不能是「或/代/委/被/被/单」等关联词
_PERSON_RE = r"(?!或|代|委|被|甲|乙|本|双|该|签)[一-龥·]{2,4}"


FIELDS: list[FieldDef] = [
    FieldDef(
        key="contract_no",
        label="合同编号",
        anchors=["合同编号", "合同号"],
        value_re=_CONTRACT_NO_RE,
        normalize="strip_ws",
    ),
    FieldDef(
        key="total_amount_num",
        label="合同金额（数字）",
        anchors=["合同总价", "合同总金额", "合同金额", "总金额", "总额", "总价"],
        value_re=_AMOUNT_RE,
        normalize="digits_only",
        multi=True,
    ),
    FieldDef(
        key="total_amount_cn",
        label="合同金额（大写）",
        anchors=["金额大写", "大写人民币", "大写"],
        value_re=r"[壹贰叁肆伍陆柒捌玖拾佰仟萬亿万元整角分零\s]{4,30}",
        normalize="strip_ws",
        multi=True,
    ),
    FieldDef(
        key="bank_account",
        label="银行账号",
        anchors=["账号", "帐号", "银行账号"],
        value_re=_ACCOUNT_RE,
        multi=True,
        normalize="digits_only",
    ),
    FieldDef(
        key="tax_id",
        label="税号",
        anchors=["税号", "纳税人识别号", "统一社会信用代码"],
        value_re=_TAX_ID_RE,
        multi=True,
        normalize="strip_ws",
    ),
    FieldDef(
        key="phone",
        label="联系电话",
        anchors=["电话", "联系电话", "手机", "Tel"],
        value_re=_PHONE_RE,
        multi=True,
        normalize="digits_only",
    ),
    FieldDef(
        key="fax",
        label="传真",
        anchors=["传真", "Fax"],
        value_re=_PHONE_RE,
        multi=True,
        normalize="digits_only",
    ),
    FieldDef(
        key="sign_date",
        label="签订日期",
        anchors=["签订日期", "签署日期", "签订时间"],
        value_re=_DATE_RE,
        normalize="strip_ws",
    ),
    FieldDef(
        key="legal_rep",
        label="法定代表人",
        anchors=["法定代表人", "法人代表"],
        value_re=_PERSON_RE,
        normalize="strip_ws",
        multi=True,
    ),
    FieldDef(
        key="bank_name",
        label="开户行",
        anchors=["开户行", "开户银行"],
        value_re=r"[一-龥]{4,30}(?:支行|分行|银行)",
        multi=True,
        normalize="strip_ws",
    ),
]


# ─────────────────────────────────────────────────────────
# 抽取
# ─────────────────────────────────────────────────────────


@dataclass
class FieldHit:
    key: str
    label: str
    value: str                     # 原始命中文本
    norm_value: str                # 规范化后用于比对
    pos: int                       # 在 doc.norm_text 中的位置（用于反查 bbox）


def _normalize_value(v: str, mode: str) -> str:
    v = v.strip()
    if mode == "digits_only":
        return re.sub(r"[^\d]", "", v)
    if mode == "strip_ws":
        return re.sub(r"\s+", "", v)
    return v


# 预清理：去掉页脚 / 页码 / 多余空白，让 anchor 与 value 之间没有噪声
_PAGE_FOOTER_RE = re.compile(r"共\s*\d+\s*页\s*第\s*\d+\s*页")


def _preclean(text: str) -> str:
    text = _PAGE_FOOTER_RE.sub("", text)
    return text


# 字段值的天然边界（lookahead）：值后必须是空白 / 标点 / 行末
_VALUE_BOUNDARY = r"(?=[\s:：，。、,.;；\n\r\(\)（）]|$)"


def extract_fields(text: str) -> dict[str, list[FieldHit]]:
    """在长文本中扫描所有字段，返回 {field_key: [FieldHit, ...]}。

    严格规则（v11.1）：
    - 预清理去页脚
    - anchor 后**必须有冒号**（中英），缺冒号视为非字段位置
    - value 后必须遇到边界（空白/标点/换行/行末），防止跨段贪婪取多余字
    - anchor 不能后接「或和与」等连接词，防止「法人代表或授权委托人」误命中
    """
    text = _preclean(text)
    out: dict[str, list[FieldHit]] = {}

    for fd in FIELDS:
        anchors = _join_anchors(fd.anchors)
        # 金额可能在描述句里（"乙方提供…总额人民币594000.00 元"），允许跨多字符
        # 其他字段（人名/编号/电话）紧跟 anchor，**不允许跨行**
        if fd.key in ("total_amount_num", "total_amount_cn"):
            gap_pat = r"[\s\S]{0,25}?"
        else:
            gap_pat = r"[ \t]{0,4}"
        pattern = re.compile(
            rf"{anchors}(?![或和与])[ \t]*[:：][ \t]*{gap_pat}({fd.value_re}){_VALUE_BOUNDARY}",
            re.MULTILINE,
        )
        hits: list[FieldHit] = []
        seen_pos: set[int] = set()
        for m in pattern.finditer(text):
            raw = m.group(1)
            norm = _normalize_value(raw, fd.normalize)
            if not norm:
                continue
            if m.start(1) in seen_pos:
                continue
            seen_pos.add(m.start(1))
            hits.append(FieldHit(
                key=fd.key, label=fd.label,
                value=raw.strip(), norm_value=norm,
                pos=m.start(1),
            ))
        if hits:
            out[fd.key] = hits
    return out


# ─────────────────────────────────────────────────────────
# 字段差异比对
# ─────────────────────────────────────────────────────────


@dataclass
class FieldDiff:
    key: str
    label: str
    kind: str                      # missing_in_orig / missing_in_scan / changed / added / removed
    orig_value: str = ""
    scan_value: str = ""
    orig_pos: int = -1
    scan_pos: int = -1


def compare_fields(orig_text: str, scan_text: str) -> list[FieldDiff]:
    """两份文本的字段集合比对。

    规则：
    - 单值字段：两侧都有但值不同 → changed；一侧有一侧无 → missing_in_*
    - 多值字段：用规范化值做集合差，返回 added（仅 scan 有）/ removed（仅 orig 有）
    """
    o_fields = extract_fields(orig_text)
    s_fields = extract_fields(scan_text)
    diffs: list[FieldDiff] = []

    for fd in FIELDS:
        o_hits = o_fields.get(fd.key, [])
        s_hits = s_fields.get(fd.key, [])

        if not fd.multi:
            o_val = o_hits[0].norm_value if o_hits else ""
            s_val = s_hits[0].norm_value if s_hits else ""
            o_raw = o_hits[0].value if o_hits else ""
            s_raw = s_hits[0].value if s_hits else ""
            o_pos = o_hits[0].pos if o_hits else -1
            s_pos = s_hits[0].pos if s_hits else -1

            if not o_val and not s_val:
                continue
            if o_val and not s_val:
                diffs.append(FieldDiff(fd.key, fd.label, "missing_in_scan", o_raw, "", o_pos, -1))
            elif s_val and not o_val:
                diffs.append(FieldDiff(fd.key, fd.label, "missing_in_orig", "", s_raw, -1, s_pos))
            elif o_val != s_val:
                diffs.append(FieldDiff(fd.key, fd.label, "changed", o_raw, s_raw, o_pos, s_pos))
        else:
            # 多值集合差
            o_set = {h.norm_value: h for h in o_hits}
            s_set = {h.norm_value: h for h in s_hits}
            removed = set(o_set) - set(s_set)
            added = set(s_set) - set(o_set)
            for v in removed:
                h = o_set[v]
                diffs.append(FieldDiff(fd.key, fd.label, "removed", h.value, "", h.pos, -1))
            for v in added:
                h = s_set[v]
                diffs.append(FieldDiff(fd.key, fd.label, "added", "", h.value, -1, h.pos))

    return diffs


# ─────────────────────────────────────────────────────────
# 测试用：从两份文档抽取并打印
# ─────────────────────────────────────────────────────────


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        with open(sys.argv[1]) as f:
            a = f.read()
        with open(sys.argv[2]) as f:
            b = f.read()
        for d in compare_fields(a, b):
            print(f"[{d.kind:18s}] {d.label}: {d.orig_value!r}  →  {d.scan_value!r}")
