#!/usr/bin/env python3
"""
chapter-lock.py — 章节锁管理工具

功能：
  1. 获取当前待创作章节号
  2. 锁定章节（防止多窗口并行写入同一章）
  3. 解锁章节（创作完成后）
  4. 检查锁定状态

使用：
  # 获取当前待创作章节
  python3 tools/chapter-lock.py get --project helper-creator

  # 锁定第 N 章
  python3 tools/chapter-lock.py lock --project helper-creator --chapter 8

  # 解锁第 N 章
  python3 tools/chapter-lock.py unlock --project helper-creator --chapter 8

  # 查看锁定状态
  python3 tools/chapter-lock.py status --project helper-creator
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional


BASE_DIR = Path("/var/minis/shared/novel-team")


def get_project_path(project_id: str) -> Path:
    """获取项目路径"""
    paths = [
        BASE_DIR / "novel-team" / "projects" / project_id / "current",
        BASE_DIR / "projects" / project_id / "current",
    ]
    for p in paths:
        if p.exists():
            return p
    print(f"❌ 项目 '{project_id}' 不存在", file=sys.stderr)
    sys.exit(1)


def load_manifest(project_path: Path) -> Dict:
    """加载 manifest.json"""
    manifest_path = project_path / "manifest.json"
    if not manifest_path.exists():
        return {
            "project_id": project_path.name,
            "current_chapter": 0,
            "total_chapters": 0,
            "word_count": 0,
            "lock": {"active": False, "chapter": None, "session": None, "updated_at": None}
        }
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def save_manifest(project_path: Path, manifest: Dict):
    """保存 manifest.json"""
    manifest_path = project_path / "manifest.json"
    manifest["last_update"] = datetime.now().strftime("%Y-%m-%d")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def cmd_get(args):
    """获取当前待创作章节"""
    project_path = get_project_path(args.project)
    manifest = load_manifest(project_path)
    
    current = manifest.get("current_chapter", 0)
    total = manifest.get("total_chapters", 0)
    word_count = manifest.get("word_count", 0)
    lock = manifest.get("lock", {})
    
    # 计算下一章
    next_chapter = current + 1 if current > 0 else 1
    
    print("=" * 60)
    print(f"📖 项目状态：{args.project}")
    print("=" * 60)
    print()
    print(f"【进度】")
    print(f"  已完成：{total} 章")
    print(f"  已写字数：{word_count:,} 字")
    print(f"  下一章：Ch{next_chapter:03d}")
    print()
    print(f"【锁定状态】")
    if lock.get("active"):
        print(f"  ⚠️  第 {lock.get('chapter')} 章被锁定")
        print(f"     锁定者：{lock.get('session', 'Unknown')}")
        print(f"     锁定时间：{lock.get('updated_at', 'Unknown')}")
        print()
        print("  💡 建议：等待当前会话完成后再创作下一章")
    else:
        print(f"  ✅ 无锁定，可以创作 Ch{next_chapter:03d}")
    print()
    
    # 返回 JSON 格式供脚本调用
    result = {
        "next_chapter": next_chapter,
        "total_chapters": total,
        "word_count": word_count,
        "locked": lock.get("active", False),
        "lock_info": lock if lock.get("active") else None
    }
    
    print(json.dumps(result, ensure_ascii=False))


def cmd_lock(args):
    """锁定章节"""
    project_path = get_project_path(args.project)
    manifest = load_manifest(project_path)
    
    chapter = args.chapter
    session = args.session or f"session-{datetime.now().strftime('%H%M%S')}"
    
    # 检查章节是否存在
    ch_file = project_path / "chapters" / f"ch{chapter:03d}.md"
    if not ch_file.exists():
        print(f"⚠️  第 {chapter} 章尚未创建，确认要锁定吗？(y/N)", end=" ")
        try:
            confirm = input().strip().lower()
            if confirm != "y":
                print("已取消。")
                return
        except:
            pass
    
    # 更新锁定状态
    manifest["lock"] = {
        "active": True,
        "chapter": chapter,
        "session": session,
        "updated_at": datetime.now().isoformat()
    }
    
    save_manifest(project_path, manifest)
    
    print(f"✅ 第 {chapter} 章已锁定")
    print(f"   锁定者：{session}")
    print(f"   时间：{manifest['lock']['updated_at']}")


def cmd_unlock(args):
    """解锁章节"""
    project_path = get_project_path(args.project)
    manifest = load_manifest(project_path)
    
    chapter = args.chapter
    lock = manifest.get("lock", {})
    
    if not lock.get("active") or lock.get("chapter") != chapter:
        print(f"⚠️  第 {chapter} 章未被锁定")
        return
    
    # 如果启用 auto-gate-check，自动运行门禁检验
    auto_check = getattr(args, 'auto', False)
    if auto_check:
        print(f"🔍 自动运行 gate-check...")
        chapter_file = project_path / "chapters" / f"ch{chapter:03d}.md"
        if chapter_file.exists():
            import subprocess
            result = subprocess.run(
                ["python3", "/var/minis/shared/novel-team/tools/gate-check.py",
                 "check", "--chapter", str(chapter),
                 "--file", str(chapter_file),
                 "--novel-id", args.project,
                 "--no-cache"],
                capture_output=True,
                text=True
            )
            try:
                output = json.loads(result.stdout)
                if output.get("passed"):
                    print(f"✅ gate-check 通过")
                else:
                    print(f"❌ gate-check 未通过，禁止解锁！")
                    print(f"   P0 阻断: {output.get('p0_failures', [])}")
                    print(f"   请先修复问题后再解锁")
                    sys.exit(1)
            except:
                print(f"⚠️  gate-check 解析失败，继续解锁")
        else:
            print(f"⚠️  章节文件不存在: {chapter_file}")
    
    # 清除锁定
    manifest["lock"] = {
        "active": False,
        "chapter": None,
        "session": None,
        "updated_at": None
    }
    
    save_manifest(project_path, manifest)
    
    print(f"✅ 第 {chapter} 章已解锁")


def cmd_status(args):
    """查看锁定状态"""
    project_path = get_project_path(args.project)
    manifest = load_manifest(project_path)
    lock = manifest.get("lock", {})
    
    print("=" * 60)
    print(f"🔒 章节锁定状态：{args.project}")
    print("=" * 60)
    print()
    
    if lock.get("active"):
        print(f"⚠️  当前锁定：第 {lock.get('chapter')} 章")
        print(f"   锁定者：{lock.get('session', 'Unknown')}")
        print(f"   时间：{lock.get('updated_at', 'Unknown')}")
    else:
        print("✅ 无锁定")
    
    print()
    print(f"【项目进度】")
    print(f"  已完成：{manifest.get('total_chapters', 0)} 章")
    print(f"  字数：{manifest.get('word_count', 0):,} 字")


def main():
    parser = argparse.ArgumentParser(
        description="章节锁管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  # 获取当前待创作章节
  python3 tools/chapter-lock.py get --project helper-creator
  
  # 锁定第 8 章
  python3 tools/chapter-lock.py lock --project helper-creator --chapter 8
  
  # 解锁第 8 章
  python3 tools/chapter-lock.py unlock --project helper-creator --chapter 8
  
  # 查看锁定状态
  python3 tools/chapter-lock.py status --project helper-creator
        """
    )
    
    sub = parser.add_subparsers(dest="command", help="子命令")
    
    p_get = sub.add_parser("get", help="获取当前待创作章节")
    p_get.add_argument("--project", "-p", required=True, help="项目 ID")
    
    p_lock = sub.add_parser("lock", help="锁定章节")
    p_lock.add_argument("--project", "-p", required=True, help="项目 ID")
    p_lock.add_argument("--chapter", "-c", type=int, required=True, help="章节号")
    p_lock.add_argument("--session", "-s", help="会话标识（默认自动生成）")
    
    p_unlock = sub.add_parser("unlock", help="解锁章节（可选自动门禁检验）")
    p_unlock.add_argument("--project", "-p", required=True, help="项目 ID")
    p_unlock.add_argument("--chapter", "-c", type=int, required=True, help="章节号")
    p_unlock.add_argument("--auto", action="store_true", help="自动运行 gate-check，未通过则拒绝解锁")
    
    p_status = sub.add_parser("status", help="查看锁定状态")
    p_status.add_argument("--project", "-p", required=True, help="项目 ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    if args.command == "get":
        cmd_get(args)
    elif args.command == "lock":
        cmd_lock(args)
    elif args.command == "unlock":
        cmd_unlock(args)
    elif args.command == "status":
        cmd_status(args)


if __name__ == "__main__":
    main()
