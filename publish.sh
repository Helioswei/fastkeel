#!/bin/bash
set -e

cleanup() {
    echo ""
    echo "已取消"
    exit 0
}
trap cleanup SIGINT

# === 更新版本号 ===
OLD=$(grep '^version = ' pyproject.toml | sed 's/.*"\(.*\)"/\1/')
echo "当前版本: $OLD"
echo -n "新版本号 (回车跳过): "
read -r NEW </dev/tty

if [ -n "$NEW" ] && [ "$NEW" != "$OLD" ]; then
    sed -i '' "s/version = \"$OLD\"/version = \"$NEW\"/" pyproject.toml
    sed -i '' "s/v$OLD/v$NEW/g" CLAUDE.md
    sed -i '' "s/Current: \*\*$OLD\*\*/Current: **$NEW**/" CLAUDE.md
    sed -i '' "s/v$OLD/v$NEW/" README.md
    echo "✅ 版本已更新: $OLD → $NEW"
else
    echo "跳过版本更新，保持 $OLD"
fi

# === 构建 ===
echo ""
echo "=== 构建 ==="
uv run python -m build

# === 上传 ===
echo ""
echo "=== 上传到 PyPI ==="

if [ -z "$PYPI_TOKEN" ]; then
    echo -n "请输入 PyPI API token: "
    read -r TOKEN </dev/tty
    PYPI_TOKEN="$TOKEN"
    echo ""
fi

uv run twine upload --username __token__ --password "$PYPI_TOKEN" dist/*
