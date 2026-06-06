"""材料解析函数边界测试。"""

from __future__ import annotations

import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def load_normalize_module():
    """按文件路径加载 normalize_materials，避免依赖当前工作目录。"""
    repo_root = Path(__file__).resolve().parents[2]
    script_root = repo_root / "backend" / "assets" / "scripts" / "data"
    if str(script_root) not in sys.path:
        sys.path.insert(0, str(script_root))
    spec = spec_from_file_location("normalize_materials_edge_test", script_root / "normalize_materials.py")
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    sys.modules["normalize_materials_edge_test"] = module
    spec.loader.exec_module(module)
    return module


def test_split_question_segments_accepts_java_and_web_heading_levels() -> None:
    """题库解析应兼容 Java/Web 现有二级、三级题号标题。"""
    normalize_materials = load_normalize_module()
    content = """
## 第 1 题：Java 基础

### 题干

解释 JVM。

### 第 2 题：Web 基础

#### 题干

解释事件循环。
""".strip()

    segments = normalize_materials.split_question_segments(content)

    assert [segment.order for segment in segments] == [1, 2]
    assert [segment.title for segment in segments] == ["Java 基础", "Web 基础"]


def test_normalize_question_file_uses_title_when_stem_missing() -> None:
    """缺失题干小节时应退回题目标题，避免导入空题干。"""
    normalize_materials = load_normalize_module()
    repo_root = Path(__file__).resolve().parents[2]
    source_path = repo_root / "backend" / "assets" / "material" / "web" / "interview.md"
    content = """
### 第 3 题：浏览器缓存

#### 类别

场景

#### 解析

从强缓存和协商缓存说明。
""".strip()

    rows = normalize_materials.normalize_question_file("web", source_path, content)

    assert len(rows) == 1
    assert rows[0]["question"] == "浏览器缓存"
    assert rows[0]["category"] == "scenario"
