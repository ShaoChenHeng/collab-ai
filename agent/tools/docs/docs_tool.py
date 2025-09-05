# -*- coding: utf-8 -*-
import os
import re
import json
import difflib
from pathlib import Path
from typing import Tuple, Dict, Any, List, Optional
from langchain_core.tools import tool

# --------------------------
# 工作区定位：固定为“项目根目录（collab-ai）/workspace”
# --------------------------
def _project_root() -> Path:
    p = Path(__file__).resolve()
    for _ in range(8):
        if p.name == "collab-ai":
            return p
        if (p / ".git").exists():
            return p
        if p.parent == p:
            break
        p = p.parent
    return Path.cwd().resolve()

PROJECT_ROOT = _project_root()
WORKSPACE_ROOT = str((PROJECT_ROOT / "workspace").resolve())
os.makedirs(WORKSPACE_ROOT, exist_ok=True)

# --------------------------
# 基础
# --------------------------
def _resolve_safe_path(path: str) -> Tuple[str, str]:
    if not path:
        raise ValueError("path 不能为空")
    root_real = os.path.realpath(WORKSPACE_ROOT)
    base = path if os.path.isabs(path) else os.path.join(root_real, path)
    abs_path = os.path.realpath(base)

    if os.path.commonpath([abs_path, root_real]) != root_real:
        raise PermissionError(f"禁止访问工作区以外的路径: {path}")

    if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
        raise FileNotFoundError(f"文件不存在: {abs_path}")

    rel_path = os.path.relpath(abs_path, root_real)
    return abs_path, rel_path

def _normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"[^\S\n\t]", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def _read_text_best_effort(abs_path: str) -> Tuple[str, str, int]:
    size_bytes = os.path.getsize(abs_path)
    for encoding in ("utf-8-sig", "utf-8", "gbk", "latin-1"):
        try:
            with open(abs_path, "r", encoding=encoding, errors="strict") as f:
                return f.read(), encoding, size_bytes
        except Exception:
            pass
    with open(abs_path, "rb") as f:
        raw = f.read()
    try:
        return raw.decode("utf-8", errors="replace"), "utf-8(replace)", size_bytes
    except Exception:
        return raw.decode("latin-1", errors="replace"), "latin-1(replace)", size_bytes

# --------------------------
# 步骤1：读取 workspace 文件名（用于匹配）
# --------------------------
def _list_workspace_files(max_count: int = 10000) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    root = WORKSPACE_ROOT
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), root)
            base = os.path.basename(rel)
            stem = os.path.splitext(base)[0]
            out.append({"rel_path": rel, "base": base, "stem": stem})
            if len(out) >= max_count:
                return out
    return out

# --------------------------
# 步骤2：匹配（方案A）
# - 先 basename 精确匹配
# - 否则用 stem 的 difflib 相似度，直接返回最高分（不做阈值拦截）
# --------------------------
def _seq_ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()

def _find_best_match(hint: str, items: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
    if not items:
        return None

    hint_base = os.path.basename(hint)
    hint_stem = os.path.splitext(hint_base)[0]
    if not hint_base:
        return None

    # 1) basename 精确匹配
    exacts = [it for it in items if it["base"] == hint_base]
    if exacts:
        chosen = sorted(exacts, key=lambda x: x["rel_path"])[0]
        return {"path": chosen["rel_path"], "score": 1.0}

    # 2) 模糊匹配（取最高分）
    best = None
    best_score = -1.0
    for it in items:
        score = _seq_ratio(hint_stem, it["stem"])
        if score > best_score:
            best, best_score = it, score

    if best is not None:
        return {"path": best["rel_path"], "score": round(float(best_score), 4)}
    return None

# --------------------------
# 步骤3：解析器（统一输出结构）
# --------------------------
def _parse_txt(abs_path: str) -> Dict[str, Any]:
    text, encoding, size_bytes = _read_text_best_effort(abs_path)
    text = _normalize_text(text)
    return {"filetype": "txt", "encoding": encoding, "bytes": size_bytes, "content": text, "pages": None}

def _parse_pdf(abs_path: str) -> Dict[str, Any]:
    # 仅使用 with 确保资源自动释放；不做缓存/LRU
    try:
        import fitz  # PyMuPDF
    except Exception:
        return {
            "filetype": "pdf",
            "encoding": None,
            "bytes": os.path.getsize(abs_path),
            "content": "",
            "pages": None,
            "error": "未安装 PyMuPDF，无法解析 PDF。请 pip install pymupdf 后重试。",
        }

    size_bytes = os.path.getsize(abs_path)
    parts: List[str] = []
    pages_count = 0
    # with 语法确保文档句柄在离开块时关闭
    with fitz.open(abs_path) as doc:
        pages_count = len(doc)
        for i, page in enumerate(doc):
            text = page.get_text("text") or ""
            text = _normalize_text(text)
            if text:
                parts.append(f"[Page {i+1}]\n{text}")

    content = "\n\n".join(parts).strip()
    return {
        "filetype": "pdf",
        "encoding": None,
        "bytes": size_bytes,
        "content": content,
        "pages": pages_count,
    }

def _parse_by_suffix(abs_path: str) -> Dict[str, Any]:
    ext = Path(abs_path).suffix.lower()
    if ext == ".txt":
        return _parse_txt(abs_path)
    elif ext == ".pdf":
        return _parse_pdf(abs_path)
    else:
        return {
            "filetype": ext.lstrip(".") or "unknown",
            "encoding": None,
            "bytes": os.path.getsize(abs_path),
            "content": "",
            "pages": None,
            "error": f"暂不支持该文件类型: {ext}",
        }

# --------------------------
# 步骤4：对外工具（增加 offset/overlap，便于续读）
# --------------------------
@tool("docs_use")
def docs_use(path: str, max_chars: int = 4000, offset: int = 0, overlap: int = 0) -> str:
    """
    读取并解析 workspace 内的文件，并支持从指定 offset 续读。
    - path: 相对或绝对路径（必须位于 workspace 内）。若不存在，将在工作区索引中：
        1) 按 basename 精确匹配
        2) 否则用 difflib 对 stem 做相似度，返回最高分的那个
    - max_chars: 本次最多返回的字符数
    - offset: 从解析后的标准化文本的该字符位置开始读取（默认 0）
    - overlap: 在 offset 前额外保留的上下文字符数（默认 0）

    返回(JSON)：
    {
      "path": "相对路径（本次实际使用的）",
      "filetype": "txt|pdf|...",
      "bytes": 12345,
      "pages": null|number,
      "total_chars": 67890,
      "offset_used": 4000,
      "overlap_used": 100,
      "next_offset": 8000,
      "has_more": true|false,
      "content": "……",
      "resolved_from": "原始传入（若发生匹配时）",
      "match_score": 0.95       （若发生匹配时）
    }
    """
    resolved_from = None
    match_score = None

    # 1) 尝试直接按传入路径读取
    try:
        abs_path, rel_path = _resolve_safe_path(path)
    except FileNotFoundError:
        # 2) 匹配（先精确，再模糊，返回最高分）
        items = _list_workspace_files()
        fix = _find_best_match(path, items)
        if not fix:
            return json.dumps({
                "error": "not_found",
                "message": "workspace 中没有任何文件",
                "path": path
            }, ensure_ascii=False)
        fixed_rel = fix["path"]
        abs_path = os.path.join(WORKSPACE_ROOT, fixed_rel)
        rel_path = fixed_rel
        resolved_from = path
        match_score = fix.get("score")
    except Exception as e:
        return json.dumps({"error": type(e).__name__, "message": str(e)}, ensure_ascii=False)

    # 3) 解析到统一文本
    parsed = _parse_by_suffix(abs_path)
    text = parsed.get("content") or ""
    total_len = len(text)

    # 4) 计算切片区间（带 overlap）
    start = 0 if offset is None else max(0, min(int(offset), total_len))
    ov = max(0, int(overlap))
    start_with_ov = max(0, start - ov)
    end = min(total_len, start + max(0, int(max_chars)))

    content_slice = text[start_with_ov:end]
    has_more = end < total_len
    next_offset = end  # 续读时把 next_offset 作为下次 offset 传入

    # 5) 返回统一结构（给 LLM）
    out: Dict[str, Any] = {
        "path": rel_path,
        "filetype": parsed.get("filetype"),
        "bytes": parsed.get("bytes"),
        "pages": parsed.get("pages"),
        "total_chars": total_len,
        "offset_used": start,
        "overlap_used": ov if start > 0 else 0,
        "next_offset": next_offset,
        "has_more": has_more,
        "content": content_slice,
    }
    if parsed.get("error"):
        out["note"] = parsed.get("error")
    if resolved_from is not None:
        out["resolved_from"] = resolved_from
        out["match_score"] = match_score
    return json.dumps(out, ensure_ascii=False)
