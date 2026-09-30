#!/bin/sh
# Version: 0.1.0
# workspace-backup.sh — 工作区自动备份到 shared/
# 用法: bash workspace-backup.sh [--restore] [--dry-run] [--list-excludes]
# 策略: 保留 shared/workspace-backup/ 下最新的 N 份快照
#
# 脱敏白名单: 任何真实 token/key 一律不落盘备份，敏感路径/文件后缀走 EXCLUDE 数组
#   - 环境变量文件:    .env / .env.* / env.*
#   - 私钥/证书:       *.key / *.pem / *.p12 / *.pfx / *.jks / id_rsa*
#   - 凭证目录:        auths/ / data/ / .credentials* / .aws/ / .kube/
#   - 数据库/日志大文件: *.sqlite* / *.db / *.log
#   - 通用配置（可能含凭据）: config.json / secrets.json / .netrc / .pgpass
#   - IDE/AI 私有配置:  .claude/ / .cursor/ / .github/ 下的个人凭据
#
# 违反脱敏边界时: 备份前 WARN 但不阻断; 备份后 CHECK 二次告警

MAX_SNAPSHOTS=3

BACKUP_DIR="/var/minis/shared/workspace-backup"
WORKSPACE_DIR="/var/minis/workspace"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
SNAPSHOT_NAME="snapshot_${TIMESTAMP}"

# 脱敏白名单（find 用 -name 匹配的文件/后缀模式，POSIX sh 兼容）
EXCLUDE_PATTERNS="
.env .env.* env.*
*.key *.pem *.p12 *.pfx *.jks id_rsa*
auths .credentials* .aws .kube
*.sqlite *.sqlite3 *.db *.log *.sqlite-wal *.sqlite-shm
config.json secrets.json .netrc .pgpass
"

# 子目录整树跳过（不匹配单个文件，匹配目录本身，命中就整棵不备份）
EXCLUDE_DIRS="auths data .aws .kube .credentials .git"

dry_run=false
list_excludes=false
case "${1:-}" in
    --restore)         mode=restore ;;
    --dry-run)         dry_run=true ;;
    --list-excludes)   list_excludes=true ;;
    "")                mode=backup ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

# --list-excludes: 只打印脱敏白名单，不做事
if [ "$list_excludes" = true ]; then
    echo "脱敏白名单 — 这些文件/目录不会被备份:"
    echo "  文件模式:"
    echo "$EXCLUDE_PATTERNS" | tr ' ' '\n' | sed '/^$/d' | sed 's/^/    /'
    echo "  整树跳过:"
    echo "$EXCLUDE_DIRS" | tr ' ' '\n' | sed '/^$/d' | sed 's/^/    /'
    exit 0
fi

# 备份模式
if [ "$mode" != "restore" ]; then
    # 检查 workspace
    if [ ! -d "$WORKSPACE_DIR" ] || [ -z "$(ls -A "$WORKSPACE_DIR" 2>/dev/null)" ]; then
        echo "⚠️  工作区为空，跳过备份。"
        exit 0
    fi

    # 预扫: 命中脱敏白名单的文件 → WARN（不阻断，只是让用户知情）
    SENSITIVE_COUNT=0
    for pat in $EXCLUDE_PATTERNS; do
        # -name 匹配基名，$pat 里已含通配符
        while IFS= read -r f; do
            [ -n "$f" ] || continue
            SENSITIVE_COUNT=$((SENSITIVE_COUNT+1))
        done <<EOF
$(cd "$WORKSPACE_DIR" 2>/dev/null && find . -type f -name "$pat" 2>/dev/null | head -20)
EOF
    done
    # 整树目录命中
    for d in $EXCLUDE_DIRS; do
        if [ -d "$WORKSPACE_DIR/$d" ]; then
            SENSITIVE_COUNT=$((SENSITIVE_COUNT + $(find "$WORKSPACE_DIR/$d" -type f 2>/dev/null | wc -l)))
        fi
    done
    if [ "$SENSITIVE_COUNT" -gt 0 ]; then
        echo "🔒 检测到 $SENSITIVE_COUNT 个敏感文件，已跳过（脱敏白名单生效）"
        echo "   完整白名单: bash $0 --list-excludes"
    fi

    # 创建快照目录
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$BACKUP_DIR/$SNAPSHOT_NAME"

    if [ "$dry_run" = true ]; then
        echo "🧪 [dry-run] 将备份到 $BACKUP_DIR/$SNAPSHOT_NAME"
        exit 0
    fi

    # 复制文件: 排除大文件 >10MB + 排除敏感文件模式 + 排除整树敏感目录
    echo "📦 备份工作区到 $BACKUP_DIR/$SNAPSHOT_NAME"

    # 备份策略: cp -a 整个 workspace 快照 → 再清理敏感文件和大文件
    # 优点: 保留完整目录结构，无静默失败; 缺点: 拷贝多一点点，可接受
    rm -rf "$BACKUP_DIR/$SNAPSHOT_NAME"
    mkdir -p "$BACKUP_DIR/$SNAPSHOT_NAME"
    cp -a "$WORKSPACE_DIR"/. "$BACKUP_DIR/$SNAPSHOT_NAME"/ 2>/dev/null

    # 清理脱敏白名单命中项（cp -a 会全部搬过来，这里必须删）
    find "$BACKUP_DIR/$SNAPSHOT_NAME" -type f \
        \( -name '.env' -o -name '.env.*' -o -name 'env.*' \
           -o -name '*.key' -o -name '*.pem' -o -name '*.p12' -o -name '*.pfx' -o -name '*.jks' \
           -o -name 'id_rsa*' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' -o -name '*.log' \
           -o -name 'config.json' -o -name 'secrets.json' -o -name '.netrc' -o -name '.pgpass' \) \
        -delete 2>/dev/null

    # 清理整树跳过目录
    for d in auths data .aws .kube .credentials .git; do
        rm -rf "$BACKUP_DIR/$SNAPSHOT_NAME/$d" 2>/dev/null
    done

    # 清理超 10MB 大文件
    find "$BACKUP_DIR/$SNAPSHOT_NAME" -type f -size +10M -delete 2>/dev/null

    # 清理空目录
    find "$BACKUP_DIR/$SNAPSHOT_NAME" -type d -empty -delete 2>/dev/null

    # 统计
    COUNT=$(find "$BACKUP_DIR/$SNAPSHOT_NAME" -type f 2>/dev/null | wc -l)
    SIZE=$(du -sh "$BACKUP_DIR/$SNAPSHOT_NAME" 2>/dev/null | cut -f1)
    echo "  ✅ 已备份 $COUNT 个文件 ($SIZE)"

    # 备份后 CHECK: 二次扫描已备份文件，若仍有敏感文件漏网 → 报警并清理
    # ⚠️ 括号 \( \) 保护 -type f 语义，避免 -o 优先级让目录/符号链接混入 LEAKED_LIST
    LEAKED_LIST=$(find "$BACKUP_DIR/$SNAPSHOT_NAME" \
        -type f \( -name '.env' -o -name '.env.*' -o -name 'env.*' \
                   -o -name '*.key' -o -name '*.pem' -o -name '*.p12' -o -name '*.pfx' -o -name '*.jks' \
                   -o -name 'id_rsa*' -o -name '*.sqlite' -o -name '*.sqlite3' -o -name '*.db' -o -name '*.log' \
                   -o -name 'config.json' -o -name 'secrets.json' -o -name '.netrc' -o -name '.pgpass' \) \
        2>/dev/null)
    LEAKED=0
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        LEAKED=$((LEAKED+1))
        echo "  🚨 脱敏漏网: $f"
    done <<EOF
$LEAKED_LIST
EOF
    if [ "$LEAKED" -gt 0 ]; then
        echo "  ❌ 有 $LEAKED 个敏感文件漏网，已强制清理"
        # 用 xargs 安全处理含空格/特殊字符的路径
        printf '%s\n' "$LEAKED_LIST" | xargs -r rm -f 2>/dev/null
    fi

    # 清理旧快照
    SNAPSHOTS=$(ls -1d "$BACKUP_DIR"/snapshot_* 2>/dev/null | sort)
    TOTAL=$(echo "$SNAPSHOTS" | wc -l)
    if [ "$TOTAL" -gt "$MAX_SNAPSHOTS" ]; then
        REMOVE=$((TOTAL - MAX_SNAPSHOTS))
        echo "$SNAPSHOTS" | head -n "$REMOVE" | while read old; do
            echo "  🗑️  清理旧快照: $(basename "$old")"
            rm -rf "$old"
        done
    fi
fi

# restore 模式
if [ "${1:-}" = "--restore" ]; then
    LATEST=$(ls -1d "$BACKUP_DIR"/snapshot_* 2>/dev/null | sort | tail -1)
    if [ -n "$LATEST" ]; then
        rm -rf "$WORKSPACE_DIR"
        mkdir -p "$WORKSPACE_DIR"
        cp -r "$LATEST"/* "$WORKSPACE_DIR"/
        echo "🔄 已从 $(basename "$LATEST") 恢复工作区"
    else
        echo "❌ 没有可用快照"
    fi
fi
