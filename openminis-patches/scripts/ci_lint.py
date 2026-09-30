#!/usr/bin/env python3
"""OpenMinis CI lint — static checks that don't need Xcode/NDK.
Runs on every push/PR. ~30 seconds. Exits 1 on any failure.

Checks:
  1. JSON / YAML / XML-plist / TOML parse validity
  2. Python py_compile on all .py
  3. Shell bash -n on all .sh
  4. Markdown relative link integrity
  5. No merge conflict markers
"""
import os, sys, json, subprocess, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root
os.chdir(ROOT)
errors = []
checked = 0

def rel(p):
    return os.path.relpath(p, ROOT)

def walk(skip_git=True, skip_vendor_c=True):
    for dp, dn, fn in os.walk(ROOT):
        if skip_git and ".git" in dp.split(os.sep):
            continue
        if skip_vendor_c and ("deps/lame-3.100" in dp or "Vendor/cppjieba" in dp or "cpp/cppjieba" in dp):
            continue
        for f in fn:
            yield os.path.join(dp, f)

# --- 1a. JSON ---
import xml.etree.ElementTree as ET
for p in walk():
    if p.endswith(".json") or p.endswith(".xcstrings"):
        checked += 1
        try:
            json.load(open(p, encoding="utf-8"))
        except Exception as e:
            errors.append(f"JSON  {rel(p)}: {e}")

# --- 1b. YAML ---
try:
    import yaml
    for p in walk():
        if p.endswith((".yml", ".yaml")):
            checked += 1
            try:
                list(yaml.safe_load_all(open(p)))
            except Exception as e:
                errors.append(f"YAML  {rel(p)}: {e}")
except ImportError:
    errors.append("pyyaml not installed — run: pip install pyyaml")

# --- 1c. XML / plist / entitlements ---
for p in walk():
    if p.endswith((".xml", ".plist", ".entitlements", ".storyboard", ".xib")):
        checked += 1
        try:
            ET.parse(p)
        except Exception as e:
            errors.append(f"XML  {rel(p)}: {e}")

# --- 1d. TOML ---
try:
    import tomllib
    for p in walk():
        if p.endswith(".toml"):
            checked += 1
            try:
                with open(p, "rb") as fh:
                    tomllib.load(fh)
            except Exception as e:
                errors.append(f"TOML  {rel(p)}: {e}")
except ImportError:
    pass  # Python < 3.11

# --- 2. Python syntax ---
for p in walk():
    if p.endswith(".py"):
        checked += 1
        r = subprocess.run([sys.executable, "-m", "py_compile", p],
                           capture_output=True, text=True)
        if r.returncode != 0:
            err = r.stderr.strip().splitlines()[-1] if r.stderr.strip() else "unknown"
            errors.append(f"PY   {rel(p)}: {err}")

# --- 3. Shell syntax ---
for p in walk():
    if p.endswith(".sh"):
        checked += 1
        r = subprocess.run(["bash", "-n", p], capture_output=True, text=True)
        if r.returncode != 0:
            errors.append(f"SH   {rel(p)}: {r.stderr.strip()[:120]}")

# --- 4. Markdown relative links ---
MD_LINK = re.compile(r"\[[^\]]*\]\((?!https?://|mailto:|minis:|#)([^)#\s]+)")
for p in walk():
    if p.endswith(".md"):
        checked += 1
        try:
            text = open(p, encoding="utf-8").read()
        except Exception:
            continue
        base = os.path.dirname(p)
        for m in MD_LINK.finditer(text):
            tgt = m.group(1).strip("<>")
            if tgt.startswith("/") or tgt.startswith("{"):
                continue
            tp = os.path.normpath(os.path.join(base, tgt))
            if not os.path.exists(tp):
                errors.append(f"MD   {rel(p)}: broken link → {tgt}")

# --- 5. Merge conflict markers (line-start only; skips binary .pyc) ---
import re as _re
CONFLICT = _re.compile(rb'(^|\n)(<<<<<<< |>>>>>>> )', _re.MULTILINE)
for p in walk():
    if p.endswith((".pyc", ".pyo", ".so", ".o", ".lo", ".png", ".ttf", ".zip", ".aar", ".dex")):
        continue
    try:
        with open(p, "rb") as fh:
            d = fh.read()
    except Exception:
        continue
    if CONFLICT.search(d):
        errors.append(f"MERGE {rel(p)}: conflict markers present")

# --- Summary ---
print(f"\n{'='*60}")
print(f"OpenMinis CI Lint — {checked} files checked, {len(errors)} errors")
print(f"{'='*60}")
for e in errors:
    print(f"  ✗ {e}")
if errors:
    print(f"\nFAILED: {len(errors)} error(s)")
    sys.exit(1)
print("\nPASSED ✓")
