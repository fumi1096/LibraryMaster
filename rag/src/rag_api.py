from fastapi import FastAPI, HTTPException, APIRouter
from pydantic import BaseModel
import lancedb
import pandas as pd
from typing import List, Dict, Any, Optional

router = APIRouter(tags=["RAG"])
# 保留 app 实例以兼容直接运行: python rag_api.py
app = FastAPI(title="RAG Query API", description="Simple RAG query interface for vector search")

# 数据库配置
db_path = "/data/lancedb"
db = lancedb.connect(db_path)

# 请求模型
class VectorQuery(BaseModel):
    vector: List[float]  # 查询向量
    count: int = 5      # 返回结果数量，默认为5

class TextQuery(BaseModel):
    text: str            # 查询文本
    count: int = 5       # 返回结果数量，默认为5

class TextQueryResponse(BaseModel):
    query: str
    vector_preview: List[float]
    vector_dim: int
    results: List[Dict[str, Any]]
    total: int

# 响应模型
class SearchResult(BaseModel):
    书名: str
    作者: str
    出版社: str
    关键词: str
    摘要: str
    中国图书分类号: str
    出版年月: str
    similarity: float

@router.get("/")
def read_root():
    return {"message": "RAG Query API is running. Use /query endpoint for vector search."}

@router.post("/query", response_model=List[SearchResult])
def query_vector(query: VectorQuery):
    """
    执行向量搜索查询
    
    Args:
        query: 包含查询向量和结果数量的请求
        
    Returns:
        搜索结果列表，按相似度排序
    """
    try:
        # 验证向量维度
        if len(query.vector) != 1024:
            raise HTTPException(
                status_code=400, 
                detail=f"Vector dimension must be 1024, got {len(query.vector)}"
            )
        
        # 验证结果数量
        if query.count <= 0:
            raise HTTPException(
                status_code=400,
                detail="Count must be greater than 0"
            )
        
        # 执行搜索
        table = db.open_table("books")
        results = table.search(query.vector).limit(query.count).to_pandas()
        
        # 转换结果为SearchResult格式
        search_results = []
        for _, row in results.iterrows():
            search_result = SearchResult(
                书名=row.get("书名", ""),
                作者=row.get("作者", ""),
                出版社=row.get("出版社", ""),
                关键词=row.get("关键词", ""),
                摘要=row.get("摘要", ""),
                中国图书分类号=row.get("中国图书分类号", ""),
                出版年月=row.get("出版年月", ""),
                similarity=row.get("_distance", 0.0)
            )
            search_results.append(search_result)
        
        return search_results
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Query failed: {str(e)}"
        )


@router.post("/search", response_model=TextQueryResponse)
def search_by_text(query: TextQuery):
    """
    一站式文本搜索：输入文本 → 自动向量化 → 向量检索

    Args:
        query: 包含查询文本和结果数量的请求

    Returns:
        包含查询文本、向量预览和搜索结果的响应
    """
    try:
        from vector_query import VectorQuery

        vq = VectorQuery()
        result = vq.search_by_text(query.text, count=query.count)
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/tables")
def list_tables():
    """列出数据库中的所有表"""
    try:
        tables = db.list_tables()
        return {"tables": tables}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tables: {str(e)}"
        )

@router.get("/table_info")
def get_table_info():
    """获取books表的基本信息"""
    try:
        table = db.open_table("books")
        
        # 获取schema信息
        schema_info = []
        for i, field in enumerate(table.schema):
            schema_info.append({
                "name": field.name,
                "type": str(field.type),
                "index": i
            })
        
        # 获取前几行数据来了解实际的数据结构
        try:
            # 使用正确的LanceDB API获取样本数据
            sample_df = table.to_pandas().head(1)
            sample_columns = list(sample_df.columns)
            data_types = {col: str(dtype) for col, dtype in sample_df.dtypes.items()}
        except Exception as sample_error:
            # 如果获取样本数据失败，使用基本信息
            sample_columns = []
            data_types = {}
        
        info = {
            "table_name": table.name,
            "row_count": len(table),
            "schema": schema_info,
            "vector_column": "vector",
            "sample_columns": sample_columns,
            "data_types": data_types
        }
        return info
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get table info: {str(e)}"
        )

# 让 app 也注册所有路由（兼容直接 python rag_api.py 运行）
app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9014)