"""novelkit.checks — 检查插件包。

导入本包即注册全部 13 个门禁检查插件（见 base.register）。
插件执行顺序与 v1 gate-check.check() 一致。
"""

from novelkit.checks.base import (  # noqa: F401
    Check,
    Context,
    all_checks,
    get_check,
    register,
    skipped_result,
)

# v1 gate-check.check() 的执行顺序（行为保真：顺序即优先级呈现顺序）
CHECK_ORDER = [
    "protocol",
    "reference",
    "word_count",
    "forbidden_words",
    "fact_consistency",
    "description_consistency",
    "blueprint",
    "ai_tone",
    "hook",
    "logic_review",
    "darkthread",
    "cliche",
    "disciplines",
]

from novelkit.checks import (  # noqa: F401,E402
    protocol,
    reference,
    word_count,
    forbidden_words,
    fact_consistency,
    description_consistency,
    blueprint,
    ai_tone,
    hook,
    logic_review,
    darkthread,
    cliche,
    disciplines,
)
