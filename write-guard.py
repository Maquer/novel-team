#!/usr/bin/env python3
# Version: 0.1.0
# -*- coding: utf-8 -*-
"""write-guard.py — file_write 落盘校验 + 可靠写入通道

背景（来自 2026-09-17 / 09-18 实测记录）：
  file_write 在 iSH 上间歇性被「占位符劫持」——工具自报
  "Wrote to X (N bytes)"，但磁盘上只有 ~147-165 字节的
  CONTEXT OFFLOADED 指针文本。工具自报字节数不可信，
  必须落盘后独立复核。本工具关闭这个静默成功缺口。

命令：
  verify --path X --bytes N [--marker S]...   校验已写文件
  write  --path X [--append]                  stdin 读入→写盘→自校验
  selftest                                    黄金测试

退出码：0=OK  1=参数错  2=stub  3=size mismatch  4=marker missing  5=not found
"""
import sys
import os
import argparse

# 已实测的占位符签名（取自 09-17 02:51 记录的真实 stub 文本）
STUB_SIGS = [
    "CONTEXT OFFLOADED",
    "CONTEXT OFFLOAD",
    "Use file_read tool to retrieve if needed",
    "saved to: /var/minis/offloads/",
    "was too large to inline",
    "has been truncated",
    "file_write call was interrupted",
    "file content was truncated",
]

STUB_SIZE_CAP = 400    # 真实 stub 实测 147-165 字节；正常文件极少 <400
STUB_STRUCT_CAP = 2048  # 结构规则上限（见 detect_stub 假设）


def detect_stub(data):
    """判定是否被占位符劫持。返回 (is_stub, hits)。

    核心假设：stub 用指针文本**替换全部内容**，因此它不可能比那段
    指针文本本身大多少。两条规则都加大小上界，避免把「源码/文档
    引用了签名词」的长文件误判为劫持——误判代价高于漏判。

      1) 文件 < 400 字节 且含任一签名              → stub
      2) 文件 < 2048 字节 且含 >=3 个互不重叠签名   → stub
      3) 长文件仅正文/代码提及签名词                → 非 stub
    """
    text = data.decode("utf-8", errors="replace")
    hits = [s for s in STUB_SIGS if s in text]
    if not hits:
        return False, hits

    if len(data) < STUB_SIZE_CAP:
        return True, hits

    if len(data) < STUB_STRUCT_CAP:
        distinct = set(hits) - {"CONTEXT OFFLOAD"}  # 被 OFFLOADED 覆盖的短串
        if len(distinct) >= 3:
            return True, hits

    return False, hits


def cmd_verify(a):
    p = a.path
    if not os.path.exists(p):
        print("FAIL not_found: %s" % p, file=sys.stderr)
        return 5

    with open(p, "rb") as f:
        data = f.read()
    actual = len(data)

    # 1. stub 检测（优先级最高：stub 时字节数也必然不符）
    is_stub, hits = detect_stub(data)
    if is_stub:
        print("FAIL stub: %s" % p, file=sys.stderr)
        print("  actual_bytes=%d (reported=%s)" % (actual, a.bytes), file=sys.stderr)
        print("  signatures=%s" % hits, file=sys.stderr)
        return 2

    # 2. 过小保护：无报告字节数时用绝对下限兜底
    if actual < STUB_SIZE_CAP and a.bytes is None and not a.quiet:
        print("WARN tiny: %s actual=%d (<%d)，建议传 --bytes 复核" %
              (p, actual, STUB_SIZE_CAP), file=sys.stderr)

    # 3. 字节数比对（工具自报值）
    if a.bytes is not None and actual != a.bytes:
        print("FAIL size_mismatch: %s" % p, file=sys.stderr)
        print("  actual_bytes=%d reported_bytes=%s delta=%+d" %
              (actual, a.bytes, actual - a.bytes), file=sys.stderr)
        return 3

    # 4. 标记比对（首尾完整性）
    text = data.decode("utf-8", errors="replace")
    missing = [m for m in (a.marker or []) if m not in text]
    if missing:
        print("FAIL marker_missing: %s" % p, file=sys.stderr)
        print("  missing=%s" % missing, file=sys.stderr)
        return 4

    if not a.quiet:
        print("OK %s bytes=%d markers=%d" %
              (p, actual, len(a.marker or [])))
    return 0


def write_and_check(path, data, append=False):
    """写盘并自校验（纯函数，可测试）。返回退出码。"""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "ab" if append else "wb") as f:
        f.write(data)
    with open(path, "rb") as f:
        back = f.read()

    is_stub, hits = detect_stub(back)
    if is_stub:
        print("FAIL stub_on_disk: %s sigs=%s" % (path, hits), file=sys.stderr)
        return 2
    if not append and len(back) != len(data):
        print("FAIL size_mismatch: wrote=%d disk=%d" %
              (len(data), len(back)), file=sys.stderr)
        return 3
    return 0


def cmd_write(a):
    """stdin → 写盘 → 自校验。shell 侧写入通道，绕开 file_write 劫持。"""
    if hasattr(sys.stdin, "buffer"):
        data = sys.stdin.buffer.read()
    else:
        data = sys.stdin.read().encode("utf-8")
    if not data:
        print("FAIL empty_stdin: 未读到内容", file=sys.stderr)
        return 1

    rc = write_and_check(a.path, data, append=a.append)
    if rc == 0:
        print("OK %s bytes=%d mode=%s" %
              (a.path, os.path.getsize(a.path), "append" if a.append else "new"))
    return rc


def cmd_selftest():
    """黄金测试：stub 必拦，正常必过，正文提及签名不误杀。"""
    import tempfile
    import shutil

    d = tempfile.mkdtemp()
    cases = []

    # C1 真实 stub 形态（取自 09-17 记录）
    stub = b"<!-- CONTEXT OFFLOADED -->\n" \
           b"file_write call was interrupted due to context overflow\n" \
           b"Original content (~6.2 KB) was too large to inline\n" \
           b"The file /tmp/x.py has been written with truncated content\n" \
           b"Please regenerate content in smaller chunks and retry.\n"
    cases.append(("stub_detected", stub, 2, "x_stub.txt", None, []))

    # C2 正常文本（含中文/长句）
    ok = ("这是正常内容。" * 40).encode("utf-8")
    cases.append(("normal_pass", ok, 0, "x_ok.txt", None, []))

    # C3 正文提及 stub 签名词但非劫持（长文，不应误杀）
    mention = ("讨论 CONTEXT OFFLOADED 这个现象本身是正常的文章正文，"
               "这里在讲工具链的静默成功问题以及独立复核的必要性。"
               "正文继续。" * 8).encode("utf-8")
    cases.append(("mention_not_stub", mention, 0, "x_mention.txt", None, []))

    # C4 字节数不符
    cases.append(("size_mismatch", ok, 3, "x_ok.txt", 999, []))

    # C5 标记缺失
    cases.append(("marker_missing", ok, 4, "x_ok.txt", None, ["MARKER-NOPE"]))

    # C6 标记齐全
    marked = b"MARKER-A-1\n" + ok + b"\nMARKER-B-2\n"
    cases.append(("marker_ok", marked, 0, "x_marked.txt", None,
                  ["MARKER-A-1", "MARKER-B-2"]))

    npass = 0
    for name, payload, want, fname, n_bytes, markers in cases:
        p = os.path.join(d, fname)
        with open(p, "wb") as f:
            f.write(payload)
        a = argparse.Namespace(path=p, bytes=n_bytes, marker=markers,
                               quiet=True)  # 自测时静默，只看 PASS/FAIL 行
        got = cmd_verify(a)
        flag = "PASS" if got == want else "FAIL"
        if got == want:
            npass += 1
        print("[%s] %s want=%d got=%d" % (flag, name, want, got))

    # C7 write 通道往返一致（直测纯函数，stdin 适配层另测）
    src = ("round-trip content 往返内容 " * 30).encode("utf-8")
    tmp = os.path.join(d, "rt.txt")
    got = write_and_check(tmp, src, append=False)
    disk = open(tmp, "rb").read()
    ok7 = (got == 0 and disk == src)
    npass += ok7
    print("[%s] write_roundtrip want=0 got=%d len=%d" %
          ("PASS" if ok7 else "FAIL", got, len(disk)))

    # C8 append 模式：两段拼接，字节数累加
    seg2 = ("第二段内容 appended " * 20).encode("utf-8")
    got = write_and_check(tmp, seg2, append=True)
    disk = open(tmp, "rb").read()
    ok8 = (got == 0 and disk == src + seg2)
    npass += ok8
    print("[%s] write_append want=0 got=%d len=%d" %
          ("PASS" if ok8 else "FAIL", got, len(disk)))

    # C9 stdin 适配层（真实 CLI 路径）
    import io
    old_in, old_err = sys.stdin, sys.stderr
    payload = b"stdin adapter test payload " * 20
    sys.stdin = io.TextIOWrapper(io.BytesIO(payload))
    got = cmd_write(argparse.Namespace(path=tmp, append=False))
    disk = open(tmp, "rb").read()
    sys.stdin, sys.stderr = old_in, io.StringIO()
    ok9 = (got == 0 and disk == payload)
    npass += ok9
    print("[%s] stdin_adapter want=0 got=%d len=%d" %
          ("PASS" if ok9 else "FAIL", got, len(disk)))

    shutil.rmtree(d)
    total = len(cases) + 3
    print("\nSELFTEST %d/%d PASS" % (npass, total))
    return 0 if npass == total else 1


def main():
    ap = argparse.ArgumentParser(description="file_write 落盘校验 + 可靠写入通道")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("verify", help="校验已写文件")
    v.add_argument("--path", required=True)
    v.add_argument("--bytes", type=int, help="工具自报字节数")
    v.add_argument("--marker", action="append", help="必须出现的标记，可重复")
    v.add_argument("--quiet", action="store_true",
                   help="成功时静默，只在失败时输出（适合脚本/管道）")

    w = sub.add_parser("write", help="stdin→写盘→自校验")
    w.add_argument("--path", required=True)
    w.add_argument("--append", action="store_true")

    sub.add_parser("selftest", help="黄金测试")

    a = ap.parse_args()
    if a.cmd == "verify":
        return cmd_verify(a)
    if a.cmd == "write":
        return cmd_write(a)
    return cmd_selftest()


if __name__ == "__main__":
    sys.exit(main())
