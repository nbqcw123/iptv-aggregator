#!/bin/bash
# ============================================================
# IPTV 聚合器 - 群晖 NAS 部署脚本
# 在群晖终端中执行: bash /volume1/docker/iptv-aggregator/deploy.sh
# ============================================================

set -e

PROJECT_DIR="/volume1/docker/iptv-aggregator"
DATA_DIR="${PROJECT_DIR}/data"
COMPOSE_FILE="${PROJECT_DIR}/compose.yaml"

echo "============================================"
echo "  IPTV 聚合器 - 群晖部署"
echo "============================================"

# 1. 检查 Docker
if ! command -v docker &> /dev/null; then
    # 尝试群晖 Container Manager 路径
    DOCKER="/var/packages/ContainerManager/target/usr/bin/docker"
    if [ ! -f "$DOCKER" ]; then
        echo "❌ 未找到 Docker，请确认 Container Manager 已安装"
        exit 1
    fi
else
    DOCKER="docker"
fi

echo "✅ Docker: $DOCKER"

# 2. 创建数据目录
mkdir -p "$DATA_DIR"
echo "✅ 数据目录: $DATA_DIR"

# 3. 停止旧容器（如果存在）
echo "📦 停止旧容器..."
$DOCKER stop iptv-aggregator 2>/dev/null || true
$DOCKER rm iptv-aggregator 2>/dev/null || true

# 4. 构建镜像
echo "🔨 构建镜像..."
cd "$PROJECT_DIR"
$DOCKER compose -f "$COMPOSE_FILE" build --no-cache

# 5. 启动容器
echo "🚀 启动容器..."
$DOCKER compose -f "$COMPOSE_FILE" up -d

# 6. 等待启动
echo "⏳ 等待服务启动..."
sleep 10

# 7. 检查状态
echo "📋 容器状态:"
$DOCKER ps -a --filter "name=iptv-aggregator" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 8. 健康检查
echo "🏥 健康检查..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:50086/api/health 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    echo "✅ 服务健康! (HTTP $HTTP_CODE)"
else
    echo "⚠️ 服务可能未就绪 (HTTP $HTTP_CODE)，请稍后检查日志"
fi

echo ""
echo "============================================"
echo "  部署完成!"
echo "  访问地址: http://$(hostname -I | awk '{print $1}'):50086"
echo "  数据目录: $DATA_DIR"
echo "============================================"
