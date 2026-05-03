from fastapi import FastAPI
from rag_api import app as rag_app

# 创建主应用
app = FastAPI(title="LibraryMaster RAG API", description="RAG API for LibraryMaster System")

# 将RAG API集成到主应用中
app.mount("/rag", rag_app)

# 根路径
@app.get("/")
def read_root():
    return {
        "message": "Hello! LibraryMaster RAG API is running.",
        "endpoints": {
            "rag_query": "/rag/query",
            "rag_tables": "/rag/tables",
            "rag_table_info": "/rag/table_info"
        }
    }

# 健康检查端点
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "LibraryMaster RAG API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9014)
