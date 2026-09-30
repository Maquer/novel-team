<?php
// 任务配置
// 修改时间、命令即可，不用改 cron.php

return [
    // 每日备份
    [
        'id'      => 'daily-backup-0900',
        'time'    => '09:00',
        'title'   => '[gzh] 09:00 备份就绪',
        'body'    => '今日 workspace 备份任务待执行',
        'command' => 'bash /var/minis/shared/workspace-backup.sh',
    ],

    // 每日 L2 汇总
    [
        'id'      => 'daily-l2-rollup-2200',
        'time'    => '22:00',
        'title'   => '[gzh] 22:00 L2 汇总',
        'body'    => '今日 L2 周报待生成',
        'command' => 'python3 /var/minis/shared/memory-l2-rollup.py',
    ],

    // 每日公众号检查
    [
        'id'      => 'daily-gzh-1400',
        'time'    => '14:00',
        'title'   => '[gzh] 14:00 公众号检查',
        'body'    => '公众号稿件审核待处理',
        'command' => 'python3 /var/minis/shared/gzh-team/gate-check.py --pending',
    ],

    // 测试任务（可删除）
    [
        'id'      => 'test-echo',
        'time'    => '23:59',
        'title'   => '[测试] 唤起测试',
        'body'    => '完整链路测试，tap 通知打开 Minis',
        'command' => 'echo "链路测试成功 ✅"',
    ],
];
