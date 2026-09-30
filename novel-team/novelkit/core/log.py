"""日志约定（输出契约的一部分，设计文档 §7）。

stdout 只属于最终数据（纯 JSON）；一切日志、警告、进度走 stderr。
替代原来各工具混打 stdout 的做法（问题 #4）。
"""

import sys


def info(msg: str) -> None:
    print(msg, file=sys.stderr)


def warn(msg: str) -> None:
    print(f"⚠️ {msg}", file=sys.stderr)


def error(msg: str) -> None:
    print(f"❌ {msg}", file=sys.stderr)
