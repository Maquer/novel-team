#!/bin/bash
# Version: 0.1.0
# model-switch.sh — 按需切换 minis-model-use 的 agentLoopGroups 池
#
# 背景：minis-model-use 只读 defaults.agentLoopGroups，
#      其他分组里的模型（如"审计模组"91 个）从这里不可见。
# 用途：审计/临时任务需要切池 → 跑任务 → 自动还原。
#
# 用法：
#   source /var/minis/shared/model-switch.sh         # 加载函数
#   model-switch current                              # 看当前池
#   model-switch default                              # 切回默认组
#   model-switch audit                                # 切到审计模组
#   model-switch both                                 # 两组都挂（池 6→97）
#   model-switch run --mode audit -- cmd args...     # 切池→执行→自动还原
#   model-switch restore                              # 从最近备份还原

set -u

DEFAULT_GROUP_ID="57BACC25-7402-4B97-B082-B8ACC80AFA99"   # Default Models
AUDIT_GROUP_ID="5BA71FD4-A696-4105-A41F-14D76D67C3F0"     # 审计模组
BACKUP_DIR="${MODEL_SWITCH_BACKUP_DIR:-/tmp/model-groups-backup}"
mkdir -p "$BACKUP_DIR"

_ms_get_current() {
    # 返回 agentLoopGroups 的 JSON 数组（已解码）
    minis-config get defaults.agentLoopGroups --compact 2>/dev/null \
      | python3 -c "
import json,sys
d=json.loads(sys.stdin.read())
v=d.get('value','[]')
if isinstance(v,str):
    v=json.loads(v)
print(json.dumps(v))
"
}

_ms_set_groups() {
    local json_str="$1"
    local f
    f=$(mktemp)
    echo "$json_str" > "$f"
    minis-config set defaults.agentLoopGroups --file "$f" --compact 2>/dev/null
    local rc=$?
    rm -f "$f"
    return $rc
}

_ms_backup() {
    local tag="${1:-auto}"
    local ts
    ts=$(date +%Y%m%d-%H%M%S)
    local f="$BACKUP_DIR/${tag}-${ts}.json"
    _ms_get_current > "$f"
    echo "$f"
}

_ms_restore_from() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo "[model-switch] 备份文件不存在: $file" >&2
        return 1
    fi
    local content
    content=$(cat "$file")
    _ms_set_groups "$content"
}

_ms_describe() {
    local cur
    cur=$(_ms_get_current)
    python3 -c "
import json
groups=json.loads('''$cur''')
names={'57BACC25-7402-4B97-B082-B8ACC80AFA99':'Default Models',
       '5BA71FD4-A696-4105-A41F-14D76D67C3F0':'审计模组'}
for i in groups:
    print(f'  - {i}  [{names.get(i, \"?\")}]')
"
}

_ms_switch() {
    # 子命令：default / audit / both
    local mode="$1"
    local cur target
    cur=$(_ms_get_current)

    case "$mode" in
        default)
            target='["'"$DEFAULT_GROUP_ID"'"]'
            ;;
        audit)
            target='["'"$AUDIT_GROUP_ID"'"]'
            ;;
        both)
            target='["'"$DEFAULT_GROUP_ID"', "'"$AUDIT_GROUP_ID"'"]'
            ;;
        *)
            echo "[model-switch] 未知模式: $mode" >&2
            return 2
            ;;
    esac

    # 幂等：目标已在池里且一致，跳过
    if [[ "$cur" == "$target" ]]; then
        echo "[model-switch] 已在 $mode 组，无需切换"
        return 0
    fi

    local bfile
    bfile=$(_ms_backup "before-$mode")
    if ! _ms_set_groups "$target"; then
        echo "[model-switch] 切换失败（可能触发审批）" >&2
        echo "[model-switch] 原池备份: $bfile" >&2
        return 1
    fi
    echo "[model-switch] 已切到 $mode 组"
    echo "[model-switch] 原池备份: $bfile"
}

_ms_restore() {
    local file="${1:-}"
    if [[ -z "$file" ]]; then
        file=$(ls -t "$BACKUP_DIR"/*.json 2>/dev/null | head -1)
    fi
    if [[ -z "$file" || ! -f "$file" ]]; then
        echo "[model-switch] 无备份可还原" >&2
        return 1
    fi
    if _ms_restore_from "$file"; then
        echo "[model-switch] 已还原到 $file"
    else
        echo "[model-switch] 还原失败" >&2
        return 1
    fi
}

_ms_run() {
    # 用法: model-switch run --mode audit -- cmd args...
    local mode=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --mode)
                mode="$2"; shift 2 ;;
            --)
                shift; break ;;
            *)
                shift ;;
        esac
    done

    if [[ -z "$mode" ]]; then
        echo "[model-switch] 用法: model-switch run --mode <default|audit|both> -- <cmd>" >&2
        return 2
    fi
    if [[ $# -eq 0 ]]; then
        echo "[model-switch] 缺少要执行的命令" >&2
        return 2
    fi

    # 记录当前状态供 trap 还原
    local cur_before
    cur_before=$(_ms_get_current)

    _ms_switch "$mode" >/dev/null
    if [[ $? -ne 0 ]]; then
        echo "[model-switch] 切池失败，不执行命令" >&2
        return 1
    fi

    # trap EXIT 还原（注意 set -e 场景下要确保 trap 生效）
    _MS_RESTORE_BEFORE="$cur_before"
    trap '_ms_run_restore; trap - EXIT' EXIT

    "${@}"
    local rc=$?

    _ms_run_restore
    trap - EXIT
    return $rc
}

_ms_run_restore() {
    if [[ -n "${_MS_RESTORE_BEFORE:-}" ]]; then
        echo "[model-switch] 执行完毕，还原池" >&2
        local tmpf
        tmpf=$(mktemp)
        echo "$_MS_RESTORE_BEFORE" > "$tmpf"
        _ms_restore_from "$tmpf" >/dev/null
        rm -f "$tmpf"
        unset _MS_RESTORE_BEFORE
    fi
}

# 对外命令包装器
model-switch() {
    local sub="${1:-current}"
    shift 2>/dev/null || true
    case "$sub" in
        current|status) _ms_describe ;;
        default|audit|both) _ms_switch "$sub" ;;
        restore) _ms_restore "${1:-}" ;;
        run) _ms_run "$@" ;;
        backup-list) ls -lt "$BACKUP_DIR"/*.json 2>/dev/null | head -10 ;;
        *)
            cat <<HELP
用法: model-switch <subcommand> [args]

子命令:
  current            显示当前 agentLoopGroups
  default            切到 Default Models 组
  audit              切到 审计模组 组
  both               两组都挂（池 6→97）
  restore [file]     从备份还原（默认最新）
  backup-list        列出所有备份文件
  run --mode X -- cmd args...
                     切池 → 执行命令 → 自动还原

备份目录: $BACKUP_DIR
HELP
            return 1
            ;;
    esac
}

# 如果直接执行脚本（非 source），把参数当命令
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    model-switch "$@"
fi
