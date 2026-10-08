#!/usr/bin/env python3
"""test-outline-c9.py — C9 清账回归测试（TEAM.md v0.59）

覆盖四组缺陷，全部必须是「修前静默通过、修后明确失败」的反向断言：
  C9a ID 序列式且唯一
  C9b 重复 ID 拒绝（修前：静默覆盖，两次都报成功）
  C9c 父子层级真实落盘（修前：children 非字段，tree 恒为空）
  C9d 前置校验（父节点/伏笔/重复回收）

用法：python3 test-outline-c9.py
退出：全过 exit 0；任一失败 exit 1
"""
import json, os, shutil, subprocess, sys, tempfile

TOOLS = os.path.dirname(os.path.abspath(__file__))
BUILDER = os.path.join(TOOLS, "outline-builder.py")

fails = []


def run(proj, *args, expect=0):
    """运行子命令，返回 (exit_code, stdout, stderr)。expect 非 0 时自动断言。"""
    r = subprocess.run([sys.executable, BUILDER, "--project", proj, *args],
                       capture_output=True, text=True)
    if expect and r.returncode != expect:
        fails.append(f"[{args[0]}] 期望 exit={expect}，实际 exit={r.returncode}")
    if expect:
        assert "ERROR:" in r.stderr, f"[{args[0]}] stderr 缺 ERROR: 前缀\n  {r.stderr}"
    return r.returncode, r.stdout, r.stderr


def section(title):
    print(f"\n{title}")


def ok(msg):
    print(f"  ✅ {msg}")


def main():
    proj = tempfile.mkdtemp(prefix="ob-c9-")
    try:
        # ---- 正常链路 ----
        section("1. 正常链路 + 层级树（C9c）")
        rc, out, _ = run(proj, "add-work", "-t", "天命")
        assert "work-0001" in out, f"work ID 应为序列式 work-0001，实际 {out!r}"
        ok("work-0001 序列式 ID")

        run(proj, "add-volume", "-w", "work-0001", "-n", "1", "-t", "少年篇")
        run(proj, "add-chapter", "-v", "vol-001", "-n", "1", "-t", "开篇")
        run(proj, "add-chapter", "-v", "vol-001", "-n", "2", "-t", "大比")
        rc, out, _ = run(proj, "add-foreshadow", "-c", "ch-0001", "-C", "剑来历")
        assert "foil-0001" in out, f"foreshadow ID 应为 foil-0001，实际 {out!r}"
        ok("foil-0001 序列式 ID")

        rc, out, _ = run(proj, "tree")
        tree = json.loads(out)
        assert len(tree) == 1, f"tree 根节点应为 1，实际 {len(tree)}"
        vol = tree[0]["children"]
        assert len(vol) == 1 and vol[0]["id"] == "vol-001", f"卷未挂到作品下：{tree[0].get('children')}"
        chapters = vol[0]["children"]
        assert len(chapters) == 2, f"章节未挂到卷下，实际 {len(chapters)} 个"
        assert [c["depth"] for c in chapters] == [2, 2]
        ok("三层树 work→vol→ch 真实落盘")

        # ---- C9b 重复 ID ----
        section("2. 重复 ID 拒绝（C9b，修前静默覆盖）")
        run(proj, "add-volume", "-w", "work-0001", "-n", "1", "-t", "重复卷", expect=1)
        run(proj, "add-chapter", "-v", "vol-001", "-n", "1", "-t", "重复章", expect=1)
        ok("重复卷/章均 exit 1 + ERROR:")

        # 关键：确认第一次的节点未被第二次覆盖
        with open(os.path.join(proj, "outline", "outline.json"), encoding="utf-8") as f:
            data = json.load(f)
        assert data["nodes"]["vol-001"]["title"] == "少年篇", "卷标题被覆盖，去重守卫失效"
        assert data["nodes"]["ch-0001"]["title"] == "开篇", "章节标题被覆盖，去重守卫失效"
        ok("既有节点未被覆盖（标题保持'少年篇'/'开篇'）")

        # ---- C9d 前置校验 ----
        section("3. 前置校验（C9d）")
        run(proj, "add-volume", "-w", "work-999", "-n", "2", "-t", "孤儿卷", expect=1)
        run(proj, "add-chapter", "-v", "vol-999", "-n", "9", "-t", "孤儿章", expect=1)
        run(proj, "add-foreshadow", "-c", "ch-9999", "-C", "孤儿伏笔", expect=1)
        ok("孤儿父节点（卷/章/伏笔）均 exit 1")

        run(proj, "pay-off", "-f", "foil-0001", "-c", "ch-0001")
        run(proj, "pay-off", "-f", "foil-0001", "-c", "ch-0001", expect=1)
        ok("重复回收 exit 1")

        # ---- 真实数据回归 ----
        section("4. 真实项目数据不崩（C9d 清账后）")
        real = os.path.abspath(resolve("helper-creator").root_dir if "resolve" in dir() else Path(TOOLS).parent / "projects" / "helper-creator" / "current")
        if os.path.isdir(real):
            r = subprocess.run([sys.executable, BUILDER, "--project", real, "tree"],
                               capture_output=True, text=True)
            assert r.returncode == 0, f"真实项目 tree 崩溃: {r.stderr}"
            real_tree = json.loads(r.stdout)
            assert len(real_tree) >= 1, "真实项目 tree 为空"
            ok(f"真实项目 tree 渲染 {len(real_tree)} 个作品")
        else:
            print(f"  ⏭️ 跳过（无 {real}）")

    finally:
        shutil.rmtree(proj, ignore_errors=True)

    print(f"\n{'='*52}")
    if fails:
        for f in fails:
            print(f"  ❌ {f}")
        print(f"{len(fails)} 项失败")
        sys.exit(1)
    print("  ✅ 全部通过")


if __name__ == "__main__":
    main()
