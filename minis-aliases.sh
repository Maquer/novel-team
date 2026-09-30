#!/bin/sh
# Version: 0.1.0
# Minis Aliases — 加载所有快捷命令
# 用法: source /var/minis/shared/minis-aliases.sh

export PATH="/var/minis/shared:$PATH"

alias minis='/var/minis/shared/minis-cli'
alias minis-search='minis search'
alias minis-sync='minis sync'
alias minis-distill='minis distill'
alias minis-dashboard='minis dashboard'
alias minis-train='minis train'
alias minis-pulse='minis pulse'
alias minis-reg='minis registry'
alias minis-eval='minis eval'
alias minis-learn='minis auto-learn'
alias minis-rollup='minis rollup'
alias minis-backup='minis backup'
alias minis-capture='minis capture'
alias minis-audit='minis audit'
alias minis-mr='minis mr'
alias minis-duel='minis duel'
alias minis-friction='minis friction'
alias minis-commit='minis commit'
alias minis-tier='minis tiering'
alias minis-lifecycle='minis lifecycle'
alias minis-crossq='minis crossq'
alias minis-blindspot='minis blindspot'
alias minis-tag='minis tag'
alias minis-graph='minis graph'
alias minis-learn-track='minis learn'
alias minis-analytics='minis analytics'
alias minis-feedback='minis feedback'
alias minis-nuwa='minis nuwa'
alias minis-ground='minis ground'
alias minis-okf='minis okf'
alias minis-viz='minis viz'
# file_write 落盘校验：fwv <文件> <字节数> ; fwq <文件> <字节数> 静默版（适合脚本）
alias fwv='/var/minis/shared/fwv'
alias fwq='/var/minis/shared/fwv --quiet'

echo "✅ Minis CLI aliases loaded"
