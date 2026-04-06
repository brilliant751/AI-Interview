"""管理端数据导入接口。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter, Depends

from app.core.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])
REPO_ROOT = Path(__file__).resolve().parents[4]


@router.post("/imports/materials")
async def import_materials(_: str = Depends(require_admin)) -> dict:
    """触发材料导入流水线。"""
    cmds = [
        ["python", "assets/scripts/data/validate_materials.py", "--strict"],
        ["python", "assets/scripts/data/normalize_materials.py"],
        ["python", "assets/scripts/data/build_question_bank.py"],
        ["python", "assets/scripts/data/build_knowledge_vectorstore.py"],
    ]
    for cmd in cmds:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
        if result.returncode != 0:
            return {
                "status": "FAILED",
                "failed_command": " ".join(cmd),
                "stderr": result.stderr[-500:],
            }
    return {"status": "SUCCESS"}
