#!/bin/bash

# RAG API 启动脚本

echo "=== RAG API 启动脚本 ==="

# 检查是否在正确的目录
if [ ! -f "docker-compose.yml" ]; then
    echo "错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "错误: Docker未安装，请先安装Docker"
    exit 1
fi

# 检查Docker Compose是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "错误: Docker Compose未安装，请先安装Docker Compose"
    exit 1
fi

# 构建并启动服务
echo "正在构建Docker镜像..."
docker-compose build

echo "正在启动RAG API服务..."
docker-compose up -d

echo "等待服务启动..."
sleep 5

# 检查服务状态
echo "检查服务状态..."
docker-compose ps

# 测试API连接
echo "测试API连接..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:9014/)

if [ "$response" == "200" ]; then
    echo "✅ RAG API启动成功!"
    echo "📖 API文档: http://localhost:9014/"
    echo "🔍 测试查询: http://localhost:9014/rag/query"
    echo "📋 表信息: http://localhost:9014/rag/table_info"
    echo "🛑 停止服务: docker-compose down"
else
    echo "❌ RAG API启动失败，请检查日志: docker-compose logs"
fi