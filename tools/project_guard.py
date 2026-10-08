#!/usr/bin/env python3
"""
project_guard.py — 代际项目守卫（单一真相源）

职责：
1. 所有工具的唯一路径入口（33 行硬编码 → 1 个 resolver）
2. 代际状态机：current（可写）/ archived（只读）
3. 4 个代际操作：archive / new / rollback / reset

设计原则：
- 线性代际（单一项目进程）：同一时刻只有一个 current
- 代际是目录，不是状态字段：gen-001/ gen-002/ ... current/
- manifest.json 是唯一真相源：记录 current 代际号 + 历史
- fail-closed：archived 代际写入直接抛异常（B1-B10 同型）

用法：
    from project_guard import resolve
    root = resolve("my-project")         # 当前 current
    root.chapters()                      # → current/chapters/
    
    root = resolve("my-project", 2)      # 历史代际
    root.chapters()                      # → gen-002/chapters/（只读）

命令：
    python3 project_guard.py archive --project my-project --reason "failed 09-27"
    python3 project_guard.py new --project my-novel
    python3 project_guard.py rollback --project my-novel --to 2
    python3 project_guard.py reset --project my-novel
    python3 project_guard.py list --project my-novel
"""

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


# ============================================================
# 常量
# ============================================================

# FIX 2026-09-30: BASE_DIR 支持环境变量 NOVEL_TEAM_ROOT 覆盖，便于异机 / 测试环境
# 指向自定义根目录。openminis（iOS 17）下默认值 /var/minis/shared/novel-team
# 即平台规范路径（minis:// 映射），无需设置即可工作。
BASE_DIR = Path(os.environ.get("NOVEL_TEAM_ROOT", "/var/minis/shared/novel-team"))
PROJECTS_DIR = BASE_DIR / "projects"

# 项目根目录下的子目录列表（25 个顶层目录归位到这里）
PROJECT_SUBDIRS = [
    "chapters", "outline", "ledger", "events", "foreshadow",
    "flow", "tags", "timeline", "world-packs", "tracking",
    "trace", "pipeline", "modifiers", "pending-world",
    "fact-snapshots", "butterfly", "contract-tree", "triggers",
    "continuous", "explain", "hfsman", "md-sync", "map-unlocker",
    "preference-memory", "reports",
]


# ============================================================
# 核心：ProjectRoot 命名空间
# ============================================================

class ProjectRoot:
    """项目代际根目录的命名空间对象。
    
    所有工具通过它访问项目数据，不直接拼接路径。
    archived 代际自动只读（fail-closed）。
    """
    
    def __init__(self, project_id: str, generation_id: int, root_dir: Path, frozen: bool):
        self.project_id = project_id
        self.generation_id = generation_id
        self.root_dir = root_dir
        self.frozen = frozen
    
    def _assert_writable(self):
        """写入前检查：archived 代际直接抛异常。"""
        if self.frozen:
            raise PermissionError(
                f"Cannot write to archived generation gen-{self.generation_id:03d} "
                f"(project: {self.project_id}). Frozen generations are read-only."
            )
    
    def _subdir(self, name: str, writable: bool = True) -> Path:
        """返回子目录路径，可选检查写权限。"""
        if writable:
            self._assert_writable()
        return self.root_dir / name
    
    # --- 可写访问器（current 代际） ---
    
    def chapters(self, writable: bool = True) -> Path:
        return self._subdir("chapters", writable)
    
    def outline(self, writable: bool = True) -> Path:
        return self._subdir("outline", writable)
    
    def ledger(self, writable: bool = True) -> Path:
        return self._subdir("ledger", writable)
    
    def events(self, writable: bool = True) -> Path:
        return self._subdir("events", writable)
    
    # --- 其他子目录 ---
    
    def foreshadow(self, writable: bool = True) -> Path:
        return self._subdir("foreshadow", writable)
    
    def flow(self, writable: bool = True) -> Path:
        return self._subdir("flow", writable)
    
    def tags(self, writable: bool = True) -> Path:
        return self._subdir("tags", writable)
    
    def timeline(self, writable: bool = True) -> Path:
        return self._subdir("timeline", writable)
    
    def world_packs(self, writable: bool = True) -> Path:
        return self._subdir("world-packs", writable)
    
    def tracking(self, writable: bool = True) -> Path:
        return self._subdir("tracking", writable)
    
    def trace(self, writable: bool = True) -> Path:
        return self._subdir("trace", writable)
    
    def pipeline(self, writable: bool = True) -> Path:
        return self._subdir("pipeline", writable)
    
    def modifiers(self, writable: bool = True) -> Path:
        return self._subdir("modifiers", writable)
    
    def pending_world(self, writable: bool = True) -> Path:
        return self._subdir("pending-world", writable)
    
    def fact_snapshots(self, writable: bool = True) -> Path:
        return self._subdir("fact-snapshots", writable)
    
    def butterfly(self, writable: bool = True) -> Path:
        return self._subdir("butterfly", writable)
    
    def contract_tree(self, writable: bool = True) -> Path:
        return self._subdir("contract-tree", writable)
    
    def triggers(self, writable: bool = True) -> Path:
        return self._subdir("triggers", writable)
    
    def continuous(self, writable: bool = True) -> Path:
        return self._subdir("continuous", writable)
    
    def explain(self, writable: bool = True) -> Path:
        return self._subdir("explain", writable)
    
    def hfsman(self, writable: bool = True) -> Path:
        return self._subdir("hfsman", writable)
    
    def md_sync(self, writable: bool = True) -> Path:
        return self._subdir("md-sync", writable)
    
    def map_unlocker(self, writable: bool = True) -> Path:
        return self._subdir("map-unlocker", writable)
    
    def preference_memory(self, writable: bool = True) -> Path:
        return self._subdir("preference-memory", writable)
    
    def reports(self, writable: bool = True) -> Path:
        return self._subdir("reports", writable)
    
    def __repr__(self):
        status = "FROZEN" if self.frozen else "ACTIVE"
        return f"ProjectRoot({self.project_id}, gen-{self.generation_id:03d}, {status})"


# ============================================================
# Manifest 管理
# ============================================================

def _manifest_path(project_id: str) -> Path:
    return PROJECTS_DIR / project_id / "manifest.json"


def _load_manifest(project_id: str) -> dict:
    """加载 manifest，不存在则初始化（同时创建 current 目录）。"""
    path = _manifest_path(project_id)
    if not path.exists():
        # 初始化 manifest + 创建 current 目录
        _create_gen_dir(project_id, 1, is_current=True)
        manifest = {
            "id": project_id,
            "current": 1,
            "generations": [
                {
                    "id": 1,
                    "state": "active",
                    "reason": "initial",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }
        _save_manifest(project_id, manifest)
        return manifest
    with open(path) as f:
        return json.load(f)


def _save_manifest(project_id: str, manifest: dict):
    """保存 manifest。"""
    path = _manifest_path(project_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def _gen_dir(project_id: str, generation_id: int) -> Path:
    """返回代际目录路径。"""
    if generation_id == _load_manifest(project_id)["current"]:
        return PROJECTS_DIR / project_id / "current"
    return PROJECTS_DIR / project_id / f"gen-{generation_id:03d}"


def _create_gen_dir(project_id: str, generation_id: int, is_current: bool = True) -> Path:
    """创建代际目录结构。
    
    Args:
        project_id: 项目 ID
        generation_id: 代际号
        is_current: 是否为当前代际（决定目录名是 current/ 还是 gen-00N/）
    """
    if is_current:
        gen_dir = PROJECTS_DIR / project_id / "current"
    else:
        gen_dir = PROJECTS_DIR / project_id / f"gen-{generation_id:03d}"
    
    gen_dir.mkdir(parents=True, exist_ok=True)
    for subdir in PROJECT_SUBDIRS:
        (gen_dir / subdir).mkdir(exist_ok=True)
    return gen_dir


# ============================================================
# 核心：resolve()
# ============================================================

def resolve(project_id: str, generation: str | int = "current") -> ProjectRoot:
    """解析项目代际根目录。
    
    Args:
        project_id: 项目 ID（如 "my-novel"）
        generation: "current" 或代际号（如 2）
    
    Returns:
        ProjectRoot 对象（可写或只读）
    
    Note:
        不检查目录是否存在——目录创建在写入时进行（惰性创建）。
        但检查代际号是否在 manifest 里声明。

    FIX 2026-09-30 说明：project_id 不做格式强校验（宽松接受），保留现有行为；
    本次仅引入 NOVEL_TEAM_ROOT 环境变量覆盖 BASE_DIR。
    """
    manifest = _load_manifest(project_id)
    
    if generation == "current":
        gen_id = manifest["current"]
        frozen = False
    else:
        gen_id = int(generation)
        # 检查代际是否在 manifest 里声明
        if not any(g["id"] == gen_id for g in manifest["generations"]):
            raise FileNotFoundError(
                f"Generation {gen_id} not declared in manifest for project {project_id}. "
                f"Available: {[g['id'] for g in manifest['generations']]}"
            )
        # current 代际可写，其他只读
        frozen = (gen_id != manifest["current"])
    
    root_dir = _gen_dir(project_id, gen_id)
    return ProjectRoot(project_id, gen_id, root_dir, frozen)


# ============================================================
# 代际操作：4 个命令
# ============================================================

def cmd_archive(project_id: str, reason: str = "") -> bool:
    """将 current 归档为 gen-00N（只读）。"""
    manifest = _load_manifest(project_id)
    current_id = manifest["current"]
    
    # 检查 current 目录是否存在
    current_dir = PROJECTS_DIR / project_id / "current"
    if not current_dir.exists():
        print(f"ERROR: current directory not found for {project_id}. Create it first with 'new' or write some data.", file=sys.stderr)
        return False
    
    # 移动目录：current → gen-00N
    archived_dir = PROJECTS_DIR / project_id / f"gen-{current_id:03d}"
    if archived_dir.exists():
        print(f"ERROR: gen-{current_id:03d} already exists", file=sys.stderr)
        return False
    
    shutil.move(str(current_dir), str(archived_dir))
    
    # 更新 manifest
    for gen in manifest["generations"]:
        if gen["id"] == current_id:
            gen["state"] = "archived"
            gen["reason"] = reason or "archived"
            gen["timestamp"] = datetime.now().isoformat()
            break
    
    _save_manifest(project_id, manifest)
    print(f"✅ Archived gen-{current_id:03d} (reason: {reason or 'archived'})")
    return True


def cmd_new(project_id: str, reason: str = "") -> bool:
    """创建新的 current 代际（gen-00N+1）。
    
    步骤：
    1. 如果旧 current 存在，归档它（current/ → gen-00N/）
    2. 创建新 current 目录（gen-00N+1）
    3. 更新 manifest
    """
    manifest = _load_manifest(project_id)
    old_current_id = manifest["current"]
    new_id = old_current_id + 1
    
    # 步骤 1: 归档旧 current（如果存在）
    current_dir = PROJECTS_DIR / project_id / "current"
    if current_dir.exists():
        archived_dir = PROJECTS_DIR / project_id / f"gen-{old_current_id:03d}"
        if archived_dir.exists():
            print(f"ERROR: gen-{old_current_id:03d} already exists", file=sys.stderr)
            return False
        shutil.move(str(current_dir), str(archived_dir))
    
    # 步骤 2: 创建新 current 目录
    _create_gen_dir(project_id, new_id, is_current=True)
    
    # 步骤 3: 更新 manifest
    # 旧 current 标记为 archived
    for gen in manifest["generations"]:
        if gen["id"] == old_current_id:
            gen["state"] = "archived"
            gen["reason"] = gen.get("reason", "previous generation")
            gen["timestamp"] = datetime.now().isoformat()
            break
    
    # 新 current 添加为 active
    manifest["current"] = new_id
    manifest["generations"].append({
        "id": new_id,
        "state": "active",
        "reason": reason or "new generation",
        "timestamp": datetime.now().isoformat(),
    })
    
    _save_manifest(project_id, manifest)
    print(f"✅ Created gen-{new_id:03d} (reason: {reason or 'new generation'})")
    print(f"   Archived gen-{old_current_id:03d} (previous current)")
    return True


def cmd_rollback(project_id: str, to_gen: int) -> bool:
    """回滚到指定代际：将 gen-00N 目录重命名为 current/。
    
    语义：回滚后 gen-00N 变成 ACTIVE 状态（目录重命名为 current/），
    原 current 归档为 gen-00N+1。
    """
    manifest = _load_manifest(project_id)
    
    # 检查目标代际存在且已归档
    target_gen = next((g for g in manifest["generations"] if g["id"] == to_gen), None)
    if not target_gen:
        print(f"ERROR: generation {to_gen} not found", file=sys.stderr)
        return False
    if target_gen["state"] != "archived":
        print(f"ERROR: generation {to_gen} is not archived (state: {target_gen['state']})", file=sys.stderr)
        return False
    
    # 如果当前 current 存在，先归档它
    current_dir = PROJECTS_DIR / project_id / "current"
    if current_dir.exists():
        current_id = manifest["current"]
        temp_archive = PROJECTS_DIR / project_id / f"gen-{current_id + 1:03d}"
        if temp_archive.exists():
            print(f"ERROR: gen-{current_id + 1:03d} already exists", file=sys.stderr)
            return False
        shutil.move(str(current_dir), str(temp_archive))
        # 更新 manifest：重编号并标记为 archived
        for gen in manifest["generations"]:
            if gen["id"] == current_id:
                gen["id"] = current_id + 1
                gen["state"] = "archived"
                gen["reason"] = "auto-archived by rollback"
                gen["timestamp"] = datetime.now().isoformat()
    
    # 将目标代际目录重命名为 current/
    target_dir = PROJECTS_DIR / project_id / f"gen-{to_gen:03d}"
    shutil.move(str(target_dir), str(current_dir))
    
    # 更新 manifest：目标代际设为 ACTIVE
    manifest["current"] = to_gen
    for gen in manifest["generations"]:
        if gen["id"] == to_gen:
            gen["state"] = "active"
            gen["reason"] = gen.get("reason", "") + " (rolled back)"
            gen["timestamp"] = datetime.now().isoformat()
    
    _save_manifest(project_id, manifest)
    print(f"✅ Rolled back to gen-{to_gen:03d} (now ACTIVE)")
    return True


def cmd_reset(project_id: str, dry_run: bool = False, confirm: bool = False) -> bool:
    """重置 current：清空目录，保留 manifest。

    FIX 2026-09-30: 原先经 subprocess 调用 `rm -rf`（P1 安全风险：路径解析若被污染
    可能误删，且依赖外部 rm 二进制）。现改走 shutil.rmtree（标准库安全 API）。
    新增 dry_run（仅打印将删除的目录，不执行）与 confirm（删除前二次确认）参数；
    默认保留原行为（直接清空），调用方可按需加固。
    """
    current_dir = PROJECTS_DIR / project_id / "current"
    if not current_dir.exists():
        print(f"ERROR: current directory not found for {project_id}", file=sys.stderr)
        return False

    targets = [current_dir / subdir for subdir in PROJECT_SUBDIRS
               if (current_dir / subdir).exists() or (current_dir / subdir).is_symlink()]

    if dry_run:
        print(f"[dry-run] 将清空 {project_id}/current 下 {len(targets)} 个子目录（保留 manifest）：")
        for t in targets:
            print(f"  - {t}")
        return True

    if confirm:
        try:
            ans = input(f"确认清空 {project_id}/current 下 {len(targets)} 个子目录？[y/N] ").strip().lower()
        except EOFError:
            ans = "n"
        if ans not in ("y", "yes"):
            print("已取消 reset。")
            return False

    # FIX 2026-09-30: shutil.rmtree 替代 rm -rf；符号链接只删链接本身，不跟随删除目标
    for sub_path in targets:
        if sub_path.is_symlink():
            sub_path.unlink()
        else:
            shutil.rmtree(sub_path)
        sub_path.mkdir(exist_ok=True)
    
    # 更新 manifest reason
    manifest = _load_manifest(project_id)
    for gen in manifest["generations"]:
        if gen["id"] == manifest["current"]:
            gen["reason"] = "reset"
            gen["timestamp"] = datetime.now().isoformat()
            break
    
    _save_manifest(project_id, manifest)
    print(f"✅ Reset current (gen-{manifest['current']:03d})")
    return True


def cmd_list(project_id: str) -> bool:
    """列出项目的所有代际。"""
    manifest = _load_manifest(project_id)
    print(f"Project: {project_id}")
    print(f"Current: gen-{manifest['current']:03d}")
    print(f"\nGenerations:")
    for gen in manifest["generations"]:
        marker = "📍" if gen["id"] == manifest["current"] else "📦"
        state = gen["state"].upper()
        reason = gen.get("reason", "")
        ts = gen.get("timestamp", "")[:19]
        print(f"  {marker} gen-{gen['id']:03d}  {state:8}  {reason:20}  {ts}")
    return True


# ============================================================
# CLI 入口
# ============================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="代际项目守卫")
    parser.add_argument("command", choices=["archive", "new", "rollback", "reset", "list"])
    parser.add_argument("--project", required=True, help="项目 ID")
    parser.add_argument("--reason", default="", help="归档/新代际原因")
    parser.add_argument("--to", type=int, help="回滚目标代际号")
    # FIX 2026-09-30: reset 安全加固参数
    parser.add_argument("--dry-run", action="store_true",
                        help="仅 reset 有效：预览将清空的目录，不执行删除")
    parser.add_argument("--confirm", action="store_true",
                        help="仅 reset 有效：清空前二次确认")
    
    args = parser.parse_args()
    
    if args.command == "archive":
        ok = cmd_archive(args.project, args.reason)
    elif args.command == "new":
        ok = cmd_new(args.project, args.reason)
    elif args.command == "rollback":
        if not args.to:
            print("ERROR: --to is required for rollback", file=sys.stderr)
            sys.exit(1)
        ok = cmd_rollback(args.project, args.to)
    elif args.command == "reset":
        ok = cmd_reset(args.project, dry_run=args.dry_run, confirm=args.confirm)
    elif args.command == "list":
        ok = cmd_list(args.project)
    else:
        ok = False
    
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
