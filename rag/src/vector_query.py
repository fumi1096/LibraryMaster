"""
向量查询模块 - 封装文本向量化(embedding) + 向量搜索功能

使用方式:
    from vector_query import VectorQuery

    vq = VectorQuery()
    results = vq.search_by_text("今天天气真不错", count=5)
"""

from openai import OpenAI
import lancedb
import os
from typing import List, Dict, Any, Optional

# 嵌入服务默认配置（可通过环境变量覆盖）
DEFAULT_EMBEDDING_URL = os.getenv("EMBEDDING_URL", "http://127.0.0.1:30000/v1")
DEFAULT_EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "Qwen3-Embedding-0.6B")
DEFAULT_EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1024"))
DEFAULT_DB_PATH = os.getenv("DB_PATH", "/data/lancedb")
DEFAULT_TABLE_NAME = os.getenv("TABLE_NAME", "books")


class VectorQuery:
    """向量查询器：将文本通过 SGLang 向量化后，在 LanceDB 中检索相似图书"""

    def __init__(
        self,
        embedding_url: Optional[str] = None,
        embedding_model: Optional[str] = None,
        embedding_dim: Optional[int] = None,
        db_path: Optional[str] = None,
        table_name: Optional[str] = None,
    ):
        """
        初始化向量查询器

        Args:
            embedding_url: SGLang 嵌入服务的地址 (默认从 EMBEDDING_URL 环境变量读取)
            embedding_model: 使用的嵌入模型名称 (默认从 EMBEDDING_MODEL 环境变量读取)
            embedding_dim: 向量维度 (默认从 EMBEDDING_DIM 环境变量读取)
            db_path: LanceDB 数据库路径 (默认从 DB_PATH 环境变量读取)
            table_name: 数据表名 (默认从 TABLE_NAME 环境变量读取)
        """
        self.embedding_dim = embedding_dim if embedding_dim is not None else DEFAULT_EMBEDDING_DIM
        self.table_name = table_name if table_name is not None else DEFAULT_TABLE_NAME

        # 初始化 SGLang 客户端
        url = embedding_url if embedding_url is not None else DEFAULT_EMBEDDING_URL
        self.client = OpenAI(base_url=url, api_key="EMPTY")
        self.embedding_model = embedding_model if embedding_model is not None else DEFAULT_EMBEDDING_MODEL

        # 连接 LanceDB
        db = db_path if db_path is not None else DEFAULT_DB_PATH
        self.db = lancedb.connect(db)

    def embed_text(self, text: str) -> List[float]:
        """
        将文本转换为向量

        Args:
            text: 输入文本

        Returns:
            向量列表 (长度 = embedding_dim)
        """
        # SGLang 维度控制前缀（虽然 dimensions 参数可能不生效，保留以备后用）
        input_text = f"<|dim:{self.embedding_dim}|>{text}"

        response = self.client.embeddings.create(
            model=self.embedding_model,
            input=input_text,
        )

        vector = response.data[0].embedding
        return vector

    def search(self, vector: List[float], count: int = 5) -> List[Dict[str, Any]]:
        """
        用向量在 LanceDB 中检索相似图书

        Args:
            vector: 查询向量
            count: 返回结果数量

        Returns:
            搜索结果列表，每项包含图书信息和相似度
        """
        if len(vector) != self.embedding_dim:
            raise ValueError(
                f"向量维度不匹配: 期望 {self.embedding_dim}, 实际 {len(vector)}"
            )

        table = self.db.open_table(self.table_name)
        results_df = table.search(vector).limit(count).to_pandas()

        results = []
        for _, row in results_df.iterrows():
            results.append({
                "书名": row.get("书名", ""),
                "作者": row.get("作者", ""),
                "出版社": row.get("出版社", ""),
                "关键词": row.get("关键词", ""),
                "摘要": row.get("摘要", ""),
                "中国图书分类号": row.get("中国图书分类号", ""),
                "出版年月": str(row.get("出版年月", "")),
                "similarity": float(row.get("_distance", 0.0)),
            })

        return results

    def search_by_text(self, text: str, count: int = 5) -> Dict[str, Any]:
        """
        一站式文本搜索：文本 → 向量化 → 向量检索

        Args:
            text: 查询文本
            count: 返回结果数量

        Returns:
            {
                "query": 原始查询文本,
                "vector": 生成的向量 (前5个元素),
                "vector_dim": 向量维度,
                "results": [搜索结果列表],
                "total": 结果数量
            }
        """
        # 1. 向量化
        vector = self.embed_text(text)

        # 2. 向量检索
        results = self.search(vector, count=count)

        return {
            "query": text,
            "vector_preview": vector[:5],
            "vector_dim": len(vector),
            "results": results,
            "total": len(results),
        }


    def keyword_search(self, keyword: str, count: int = 20) -> Dict[str, Any]:
        """
        按书名关键字查询

        Args:
            keyword: 书名关键字（支持模糊匹配）
            count: 返回结果数量上限，默认 20

        Returns:
            {
                "keyword": 查询关键字,
                "results": [搜索结果列表],
                "total": 结果数量
            }
        """
        table = self.db.open_table(self.table_name)
        df = table.to_pandas()

        # 空关键字直接返回空结果
        if not keyword or not keyword.strip():
            return {
                "keyword": keyword,
                "results": [],
                "total": 0,
            }

        # 模糊匹配书名中含有该关键字的记录
        mask = df["书名"].str.contains(keyword, na=False, case=False)
        matched = df[mask].head(count)

        results = []
        for _, row in matched.iterrows():
            results.append({
                "书名": row.get("书名", ""),
                "作者": row.get("作者", ""),
                "出版社": row.get("出版社", ""),
                "关键词": row.get("关键词", ""),
                "摘要": row.get("摘要", ""),
                "中国图书分类号": row.get("中国图书分类号", ""),
                "出版年月": str(row.get("出版年月", "")),
            })

        return {
            "keyword": keyword,
            "results": results,
            "total": len(results),
        }


# ==================== 便捷函数 ====================

# 全局单例（懒加载）
_default_vq: Optional[VectorQuery] = None


def get_default_vq() -> VectorQuery:
    """获取默认的 VectorQuery 单例"""
    global _default_vq
    if _default_vq is None:
        _default_vq = VectorQuery()
    return _default_vq


def embed_text(text: str) -> List[float]:
    """便捷函数：文本向量化"""
    return get_default_vq().embed_text(text)


def search_by_text(text: str, count: int = 5) -> Dict[str, Any]:
    """便捷函数：文本搜索"""
    return get_default_vq().search_by_text(text, count=count)


def keyword_search(keyword: str, count: int = 20) -> Dict[str, Any]:
    """便捷函数：书名关键字查询"""
    return get_default_vq().keyword_search(keyword, count=count)


# ==================== 命令行入口 ====================

if __name__ == "__main__":
    import sys

    query_text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "人工智能与机器学习"

    print(f"查询文本: {query_text}")
    print("=" * 60)

    vq = VectorQuery()

    # 1. 向量化
    print("正在向量化...")
    vec = vq.embed_text(query_text)
    print(f"向量维度: {len(vec)}")
    print(f"向量前5位: {vec[:5]}")

    # 2. 检索
    print("\n正在检索...")
    result = vq.search_by_text(query_text, count=5)

    print(f"\n共找到 {result['total']} 条结果:\n")
    for i, item in enumerate(result["results"], 1):
        print(f"--- 结果 {i} ---")
        print(f"  书名: {item['书名']}")
        print(f"  作者: {item['作者']}")
        print(f"  出版社: {item['出版社']}")
        print(f"  相似度: {item['similarity']:.4f}")
        print(f"  摘要: {item['摘要'][:80]}...")
        print()
