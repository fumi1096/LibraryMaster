# RAG 向量检索服务

基于 LanceDB + SGLang Embedding 的图书向量检索，支持输入自然语言文本自动向量化并检索相似图书。

## 架构

```
用户文本 → SGLang 向量化(宿主机:30000) → LanceDB 向量检索 → 返回相似图书
```

- **嵌入服务**：SGLang 运行在宿主机 `:30000`，模型 `Qwen3-Embedding-0.6B`，输出 1024 维向量
- **向量数据库**：LanceDB，数据目录 `./data/lancedb`
- **API 框架**：FastAPI + Uvicorn

## 快速开始

```bash
# 1. 确保宿主机 SGLang 嵌入服务已启动
bash ../Embedding/start_embedding.sh

# 2. 导入数据到 LanceDB（首次使用）
python3 src/input.py

# 3. 启动 RAG API
docker compose up -d --build
```

## API 端点

| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/rag/` | 健康检查 |
| POST | `/rag/search` | 文本搜索（自动向量化+检索） |
| POST | `/rag/query` | 直接传入向量检索 |
| GET | `/rag/tables` | 列出数据表 |
| GET | `/rag/table_info` | 表结构信息 |

### 文本搜索示例

```bash
# HTTP 调用
curl -X POST http://localhost:9014/rag/search \
  -H "Content-Type: application/json" \
  -d '{"text": "人工智能", "count": 5}'

# Python 调用
import requests
resp = requests.post("http://localhost:9014/rag/search",
                     json={"text": "深度学习", "count": 3})
print(resp.json())
```

## 环境变量

通过 `docker-compose.yml` 注入，可按需修改：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `EMBEDDING_URL` | `http://host.docker.internal:30000/v1` | 嵌入服务地址 |
| `EMBEDDING_MODEL` | `Qwen3-Embedding-0.6B` | 嵌入模型 |
| `EMBEDDING_DIM` | `1024` | 向量维度 |
| `DB_PATH` | `/data/lancedb` | LanceDB 路径 |
| `TABLE_NAME` | `books` | 数据表名 |

## 测试

```bash
# 容器外测试（仅 HTTP，需 requests）
python3 test_vector_query.py

# 容器内测试（含本地直连）
docker exec lancedb-server python test_vector_query.py
```

## 文件说明

```
rag/
├── docker-compose.yml      # Docker 编排
├── dockerfile              # 镜像构建
├── src/
│   ├── input.py            # 从 CSV 导入数据到 LanceDB
│   ├── vector_query.py     # 向量化 + 检索核心模块
│   ├── rag_api.py          # FastAPI 接口定义
│   └── main.py             # 服务入口
├── test_vector_query.py    # 测试脚本
├── data/                   # LanceDB 数据（挂载到容器 /data）
└── docs/接口文档.md         # 详细接口文档
```