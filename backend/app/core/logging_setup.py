"""日志初始化配置。"""

from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


def setup_resume_context_logger(repo_root: Path) -> Path:
    """初始化简历上下文专用日志记录器，并返回日志文件路径。"""
    log_dir = repo_root / "backend" / "logs" / "interview_resume_context"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "resume_context.log"

    logger = logging.getLogger("app.resume_context")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in logger.handlers:
        if isinstance(handler, TimedRotatingFileHandler) and Path(handler.baseFilename) == log_file:
            return log_file

    file_handler = TimedRotatingFileHandler(
        filename=str(log_file),
        when="midnight",
        interval=1,
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(file_handler)
    return log_file

