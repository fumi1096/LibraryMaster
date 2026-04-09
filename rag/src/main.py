from fastapi import FastAPI

app = FastAPI()

# 1. 写一个最简单的测试接口
@app.get("/")
def read_root():
    return {"message": "Hello! LanceDB RAG is running."}
