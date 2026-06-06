#!/bin/bash
# 加密凭据管理 - 绑定本机硬件指纹，AES-256-CBC 加密
# 用法: source secrets.sh && secrets_set <key> <value>

SECRETS_FILE="${SECRETS_FILE:-$HOME/.hermes/secrets.enc}"
mkdir -p "$(dirname "$SECRETS_FILE")"

_derive_key() {
    local mid=""
    [ -f /etc/machine-id ] && mid=$(cat /etc/machine-id)
    [ -z "$mid" ] && mid=$(hostname)
    echo -n "${mid}:hermes-v1" | sha256sum | cut -d' ' -f1
}

secrets_set() {
    local k="$1" v="$2"
    [ -z "$k" ] || [ -z "$v" ] && echo "用法: secrets_set <key> <value>" && return 1
    local key=$(_derive_key)
    local enc_v=$(echo -n "$v" | openssl enc -aes-256-cbc -a -pbkdf2 -pass "pass:${key}" 2>/dev/null)
    [ -z "$enc_v" ] && echo "❌ 加密失败" && return 1
    local tmp=$(mktemp)
    secrets_load_all > "$tmp" 2>/dev/null || true
    grep -v "^${k}=" "$tmp" > "${tmp}.2" 2>/dev/null || true
    echo "${k}=${enc_v}" >> "${tmp}.2"
    echo "$(cat "${tmp}.2")" | openssl enc -aes-256-cbc -a -pbkdf2 -pass "pass:${key}" -out "$SECRETS_FILE" 2>/dev/null
    chmod 600 "$SECRETS_FILE"
    rm -f "$tmp" "${tmp}.2"
    echo "✅ 已加密存储: $k"
}

secrets_get() {
    local k="$1"
    [ -z "$k" ] && echo "用法: secrets_get <key>" && return 1
    local key=$(_derive_key)
    local enc_v=$(openssl enc -aes-256-cbc -d -a -pbkdf2 -pass "pass:${key}" -in "$SECRETS_FILE" 2>/dev/null | grep "^${k}=" | tail -1 | cut -d= -f2-)
    [ -z "$enc_v" ] && echo "❌ 未找到: $k" && return 1
    echo "$enc_v" | openssl enc -aes-256-cbc -d -a -pbkdf2 -pass "pass:${key}" 2>/dev/null
}

secrets_load_all() {
    [ -f "$SECRETS_FILE" ] || return
    local key=$(_derive_key)
    openssl enc -aes-256-cbc -d -a -pbkdf2 -pass "pass:${key}" -in "$SECRETS_FILE" 2>/dev/null
}

secrets_list() {
    local data=$(secrets_load_all)
    [ -z "$data" ] && echo "（空）" && return
    echo "$data" | while IFS='=' read -r k _; do [ -n "$k" ] && echo "  $k"; done
}

secrets_del() {
    local k="$1"
    [ -z "$k" ] && return 1
    local key=$(_derive_key)
    local tmp=$(mktemp)
    secrets_load_all > "$tmp" 2>/dev/null || true
    grep -v "^${k}=" "$tmp" > "${tmp}.2"
    echo "$(cat "${tmp}.2")" | openssl enc -aes-256-cbc -a -pbkdf2 -pass "pass:${key}" -out "$SECRETS_FILE" 2>/dev/null
    chmod 600 "$SECRETS_FILE"
    rm -f "$tmp" "${tmp}.2"
    echo "✅ 已删除: $k"
}
