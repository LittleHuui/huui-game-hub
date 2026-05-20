#!/bin/sh
set -e

# SQLite 数据目录（compose 挂载 ./data:/app/data）
mkdir -p /app/data

exec "$@"
