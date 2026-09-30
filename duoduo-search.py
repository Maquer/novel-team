#!/usr/bin/env python3
# Version: 0.1.0
"""多多视频批量素材搜索 — 链式执行，自动等待"""
import subprocess, json, time

SCRIPTS = "/var/minis/skills/airtap/scripts"

SEARCHES = [
    ("桌面增高架推荐", ["桌面置物架", "桌面增高架神器", "宿舍桌面收纳"]),
    ("宿舍床帘推荐", ["宿舍床帘", "床帘凉席套装"]),
    ("挂脖风扇测评", ["挂脖风扇推荐", "无叶挂脖风扇"]),
    ("磁吸酷毙灯推荐", ["磁吸灯", "宿舍磁吸灯", "酷毙灯推荐"]),
    ("冰丝凉感坐垫推荐", ["冰丝坐垫", "凉感坐垫推荐", "夏天坐垫"]),
    ("保温杯推荐学生", ["大容量保温杯", "保温杯推荐", "保温杯测评"]),
    ("折叠床上书桌推荐", ["宿舍床上桌", "床上书桌推荐"]),
    ("宿舍收纳神器推荐", ["宿舍收纳", "桌面收纳", "宿舍神器推荐"]),
]

def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout

def get_active_task_id():
    out = run(f"cd {SCRIPTS} && python3 airtap.py task get-list 2>/dev/null")
    try:
        data = json.loads(out)
        tasks = data.get("tasks", data.get("data", []))
        for t in tasks:
            if t.get("taskState") == "EXECUTING":
                return t.get("taskId")
    except:
        pass
    return None

def wait_for_idle(timeout=300):
    """等待云手机空闲"""
    start = time.time()
    while time.time() - start < timeout:
        tid = get_active_task_id()
        if tid is None:
            return True
        time.sleep(20)
    return False

results = []

for i, (primary, fallbacks) in enumerate(SEARCHES):
    print(f"\n[{i+1}/{len(SEARCHES)}] {primary}")

    if not wait_for_idle(120):
        print("  ⚠️  等待超时")
        continue

    fb_list = "、".join([f"'{f}'" for f in fallbacks])
    msg = f"打开抖音App，搜索'{primary}'，找到3个热门带货视频（点赞量高、有商品链接的），记录每个视频的标题、点赞数、评论数、视频链接。如果搜索不到，依次尝试{fb_list}"

    out = run(f'cd {SCRIPTS} && python3 airtap.py task create --receiver-id cloud --model-id airtap-1.0-flash --message "{msg}" 2>/dev/null')
    try:
        data = json.loads(out)
        task_id = data.get("taskId", "unknown")
        print(f"  ✅ {task_id}")
        results.append((primary, task_id))
    except:
        print(f"  ❌ 失败")

# 输出 JSON 文件供后续使用
with open("/var/minis/shared/duoduo-search-results.json", "w") as f:
    json.dump({"tasks": [{"keyword": k, "taskId": t} for k, t in results], "timestamp": time.time()}, f, ensure_ascii=False)

print(f"\n📊 完成 {len(results)}/{len(SEARCHES)} 个搜索任务")
print("📋 结果已保存到 /var/minis/shared/duoduo-search-results.json")