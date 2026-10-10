# config/ 说明

## novelkit.json（统一阈值/开关）

评审决策（2026-10-01）：字数下限升级 2000，新增 hard_min=1500。
（2026-09-30 曾取严 1500，不保留 1350/1500 双轨；10-01 再次上调。）

字段说明：
- word_count.target: 写作目标（2500），非门禁，仅用于提示
- word_count.hard_min: 硬下限（1500），低于此为 P0 阻断
- word_count.soft_min: 软下限（2000），低于此为 fail（standalone）/ P1（门禁内）
- word_count.warn_above: 超长警告线（5500），高于此为 warning（与 v1 行为一致）
- ai_tone.threshold: humanizer 默认阈值（15.0）
- ai_tone.block_at: tier_1a 阻断线（16.0，P0）：tier_1a >= 16 → fail
- ai_tone.warn_at: 接近阈值预警线（13）：13 <= tier_1a <= 15 → warning

注意：此文件必须是合法 JSON（不支持注释）。`novelkit/core/config.py`
的 code review 红线：任何新增阈值必须进这个文件，不允许散落在检查代码里。
