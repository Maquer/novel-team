#!/usr/bin/env python3
"""
batch-replace-v2.py — 批量改词工具（带备份功能）

改进点：
  1. 自动备份原文件（带时间戳）
  2. 支持预览模式（显示替换前后对比）
  3. 支持YAML/JSON文件跳过
  4. 统一数据格式输出
"""

import sys
import json
import re
import argparse
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime


class BackupManager:
    """备份管理器"""
    
    def __init__(self, backup_dir: str = ".backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, file_path: Path) -> Optional[Path]:
        """创建文件备份"""
        if not file_path.exists():
            return None
        
        # 生成备份文件名
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_name = f"{file_path.stem}_backup_{timestamp}{file_path.suffix}"
        backup_path = self.backup_dir / backup_name
        
        # 复制文件
        shutil.copy2(file_path, backup_path)
        
        return backup_path
    
    def list_backups(self, file_pattern: str = "*.txt") -> List[Dict]:
        """列出备份文件"""
        backups = []
        for backup_file in self.backup_dir.glob(file_pattern):
            stat = backup_file.stat()
            backups.append({
                "path": str(backup_file),
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        return sorted(backups, key=lambda x: x["created_at"], reverse=True)
    
    def cleanup_old_backups(self, keep_count: int = 10):
        """清理旧备份，只保留最近N个"""
        backups = self.list_backups()
        if len(backups) > keep_count:
            for backup in backups[keep_count:]:
                Path(backup["path"]).unlink()
            return len(backups) - keep_count
        return 0


class BatchReplace:
    """批量改词工具"""
    
    # 需要跳过的文件扩展名
    SKIP_EXTENSIONS = {".json", ".yaml", ".yml", ".md", ".py", ".sh"}
    
    def __init__(self, 
                 find: str, 
                 replace: str, 
                 case_sensitive: bool = False,
                 whole_word: bool = False,
                 regex: bool = False):
        self.find = find
        self.replace = replace
        self.case_sensitive = case_sensitive
        self.whole_word = whole_word
        self.regex = regex
        self.backup_manager = BackupManager()
        
        # 编译正则
        flags = 0 if case_sensitive else re.IGNORECASE
        if regex:
            self.pattern = re.compile(find, flags)
        else:
            if whole_word:
                self.pattern = re.compile(r'\b' + re.escape(find) + r'\b', flags)
            else:
                self.pattern = re.compile(re.escape(find), flags)
    
    def replace_in_text(self, text: str) -> Tuple[str, int]:
        """在文本中替换，返回（新文本，替换次数）"""
        new_text, count = self.pattern.subn(self.replace, text)
        return new_text, count
    
    def process_file(self, file_path: Path, preview: bool = False, 
                     backup: bool = True) -> Dict:
        """处理单个文件"""
        result = {
            "file": str(file_path),
            "status": "success",
            "replacements": 0,
            "backup_path": None,
            "preview": [],
            "errors": [],
        }
        
        try:
            # 检查是否需要跳过
            if file_path.suffix.lower() in self.SKIP_EXTENSIONS:
                result["status"] = "skipped"
                result["reason"] = f"跳过{file_path.suffix}文件"
                return result
            
            # 读取文件
            content = file_path.read_text(encoding='utf-8')
            
            # 创建备份
            if backup:
                backup_path = self.backup_manager.create_backup(file_path)
                result["backup_path"] = str(backup_path)
            
            # 执行替换
            new_content, count = self.replace_in_text(content)
            result["replacements"] = count
            
            # 预览模式
            if preview and count > 0:
                # 找到替换位置
                for match in self.pattern.finditer(content):
                    start = max(0, match.start() - 30)
                    end = min(len(content), match.end() + 30)
                    context = content[start:end]
                    result["preview"].append({
                        "position": match.start(),
                        "before": f"...{context}...",
                        "after": context.replace(self.find, self.replace),
                    })
                    if len(result["preview"]) >= 5:  # 最多显示5处
                        break
            
            # 写入文件（非预览模式）
            if not preview and count > 0:
                file_path.write_text(new_content, encoding='utf-8')
            
            return result
            
        except Exception as e:
            result["status"] = "error"
            result["errors"].append(str(e))
            return result
    
    def process_directory(self, dir_path: Path, preview: bool = False,
                          backup: bool = True, recursive: bool = True) -> List[Dict]:
        """处理整个目录"""
        results = []
        
        # 收集文件
        pattern = "**/*.txt" if recursive else "*.txt"
        files = list(dir_path.glob(pattern))
        
        print(f"📂 找到 {len(files)} 个TXT文件")
        
        for file_path in files:
            result = self.process_file(file_path, preview, backup)
            results.append(result)
            
            # 显示进度
            if result["replacements"] > 0:
                icon = "👁️" if preview else "✅"
                print(f"  {icon} {file_path.name}: {result['replacements']}处替换")
            elif result["status"] == "skipped":
                print(f"  ⏭️  {file_path.name}: 跳过")
            elif result["status"] == "error":
                print(f"  ❌  {file_path.name}: {result['errors']}")
            else:
                print(f"  ⬜  {file_path.name}: 无更改")
        
        return results
    
    def get_summary(self, results: List[Dict]) -> Dict:
        """获取汇总信息"""
        total_replacements = sum(r["replacements"] for r in results)
        success_count = sum(1 for r in results if r["status"] == "success" and r["replacements"] > 0)
        skip_count = sum(1 for r in results if r["status"] == "skipped")
        error_count = sum(1 for r in results if r["status"] == "error")
        
        return {
            "total_files": len(results),
            "modified_files": success_count,
            "skipped_files": skip_count,
            "error_files": error_count,
            "total_replacements": total_replacements,
            "backup_count": sum(1 for r in results if r["backup_path"]),
        }


def main():
    parser = argparse.ArgumentParser(
        description="批量改词工具（带备份）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 简单替换
  python batch-replace-v2.py --find 青云门 --replace 天剑宗 --dir chapters/
  
  # 预览模式
  python batch-replace-v2.py --find 青云门 --replace 天剑宗 --dir chapters/ --preview
  
  # 区分大小写
  python batch-replace-v2.py --find ABC --replace XYZ --case
  
  # 整词匹配
  python batch-replace-v2.py --find the --replace a --whole
  
  # 正则匹配
  python batch-replace-v2.py --find "\\b\\d+\\b" --replace "NUM" --regex
        """
    )
    
    parser.add_argument("--find", "-f", required=True, help="查找内容")
    parser.add_argument("--replace", "-r", required=True, help="替换内容")
    parser.add_argument("--dir", "-d", required=True, help="目标目录")
    parser.add_argument("--preview", "-p", action="store_true", help="预览模式（不修改文件）")
    parser.add_argument("--no-backup", action="store_true", help="不创建备份")
    parser.add_argument("--case", "-c", action="store_true", help="区分大小写")
    parser.add_argument("--whole", "-w", action="store_true", help="整词匹配")
    parser.add_argument("--regex", action="store_true", help="正则表达式")
    parser.add_argument("--json", "-j", action="store_true", help="JSON格式输出")
    parser.add_argument("--output", "-o", help="输出文件")
    
    args = parser.parse_args()
    
    # 创建替换器
    replace = BatchReplace(
        find=args.find,
        replace=args.replace,
        case_sensitive=args.case,
        whole_word=args.whole,
        regex=args.regex,
    )
    
    # 处理目录
    dir_path = Path(args.dir)
    if not dir_path.exists():
        print(f"❌ 目录不存在: {args.dir}")
        sys.exit(1)
    
    print(f"🔄 批量改词工具")
    print(f"   查找: {args.find}")
    print(f"   替换: {args.replace}")
    print(f"   目录: {args.dir}")
    print(f"   模式: {'预览' if args.preview else '执行'}")
    print()
    
    results = replace.process_directory(
        dir_path,
        preview=args.preview,
        backup=not args.no_backup,
    )
    
    # 获取汇总
    summary = replace.get_summary(results)
    
    # 输出结果
    output = {
        "success": summary["error_files"] == 0,
        "summary": summary,
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }
    
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print()
        print("=" * 60)
        print("📊 处理结果")
        print("=" * 60)
        print(f"  总文件数: {summary['total_files']}")
        print(f"  修改文件: {summary['modified_files']}")
        print(f"  跳过文件: {summary['skipped_files']}")
        print(f"  错误文件: {summary['error_files']}")
        print(f"  总替换数: {summary['total_replacements']}")
        print(f"  备份文件: {summary['backup_count']}")
        print()
        
        if summary['error_files'] > 0:
            print("⚠️  警告：有文件处理失败，请检查错误日志")
        
        if not args.preview and summary['backup_count'] > 0:
            print(f"💾 备份位置: .backups/")
    
    # 保存输出
    if args.output:
        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2))
        print(f"📄 结果已保存: {args.output}")
    
    # 返回退出码
    sys.exit(0 if summary['error_files'] == 0 else 1)


if __name__ == "__main__":
    main()
