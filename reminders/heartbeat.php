<?php
// Minis 心跳接收端
// Minis 侧每 1 分钟上报一次
// ⚠️ 所有时间戳使用北京时间（Asia/Shanghai）

date_default_timezone_set('Asia/Shanghai');

$source = $_GET['source'] ?? 'minis-ios';
$nowTs  = time();

// 写心跳时间戳
file_put_contents(__DIR__ . "/heartbeat-{$source}.txt", $nowTs);

echo json_encode([
    'ok'      => true,
    'source'  => $source,
    'ts'      => date('c'),
    'uptime'  => $nowTs,
]);
