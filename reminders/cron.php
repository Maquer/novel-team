<?php
// my-place cron 入口
// 每 1 分钟由 cPanel cron 调用
// 触发任务前检查心跳，分流 Bark 通知类型
// ⚠️ 所有时间戳使用北京时间（Asia/Shanghai）

date_default_timezone_set('Asia/Shanghai');

$config = require __DIR__ . '/config.php';
$barkKey = 'Av8DkzMpStcsmsW3KfqEMc';
$now = date('H:i');

$fired = 0;
foreach ($config as $task) {
    if ($task['time'] !== $now) continue;

    // ★ 检查任务前 2 分钟内是否有心跳（心跳在 T-1 分钟发送，窗口 120 秒留缓冲）
    $lastBeat = (int) @file_get_contents(__DIR__ . '/heartbeat-minis-ios.txt');
    $stale = ($lastBeat === 0) || (time() - $lastBeat) > 120;

    $title = $task['title'];
    $cmd = $task['command'];

    if ($stale) {
        // ❌ Minis 被杀：Bark 通知带 minis:// URL，用户 tap 唤起
        $body = $task['body'] . '（Minis 未在线，tap 唤起执行）';
        $url_encoded = 'minis://open_terminal%3Finit_command=' . urlencode($cmd);
        $barkUrl = sprintf(
            'https://api.day.app/%s/%s/%s?isArchive=1&autoCopy=1&copy=optional&url=%s',
            $barkKey,
            urlencode($title),
            urlencode($body),
            $url_encoded
        );
        $state = 'stale';
    } else {
        // ✅ Minis 活着：Bark 通知不带 URL，普通提醒
        $body = $task['body'] . '（Minis 在线，任务已就绪）';
        $barkUrl = sprintf(
            'https://api.day.app/%s/%s/%s?isArchive=1&autoCopy=1&copy=optional',
            $barkKey,
            urlencode($title),
            urlencode($body)
        );
        $state = 'alive';
    }

    $resp = file_get_contents($barkUrl);

    // 写日志
    file_put_contents(__DIR__ . '/log.jsonl', json_encode([
        'ts'        => date('c'),
        'id'        => $task['id'],
        'time'      => $task['time'],
        'state'     => $state,
        'last_beat' => $lastBeat > 0 ? date('c', $lastBeat) : 'never',
        'resp'      => $resp,
    ], JSON_UNESCAPED_UNICODE) . "\n", FILE_APPEND | LOCK_EX);

    $fired++;
}

if ($fired > 0) {
    echo "[$now] fired $fired task(s)\n";
}
