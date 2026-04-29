import lancedb
import pandas as pd
import pyarrow as pa
import ast

input_file = "/data/out.csv"
chunk_size = 10
db_path = "/data/lancedb"
embedding_size = 1024
db = lancedb.connect(db_path)

schema = pa.schema([
    pa.field("书名", pa.string()),
    pa.field("作者", pa.string()),
    pa.field("出版社", pa.string()),
    pa.field("关键词", pa.string()),
    pa.field("摘要", pa.string()),
    pa.field("中国图书分类号", pa.string()),
    pa.field("出版年月", pa.date32()),
    pa.field("vector", pa.list_(pa.float32(), list_size=embedding_size)),
])
#tbl = db.create_table("empty_table", schema=schema)

print(f"开始分块读取 {input_file} ...")

col_types = {
    '书名': str,
    '作者': str,
    '出版社': str,
    '关键词': str,
    '摘要': str,
    '中国图书分类号': str,
    '出版年月': str,
    'embedding': str,  # 先读取为字符串，后续转换为列表
}

# 3. 分块读取循环
# pd.read_csv 返回一个 TextFileReader 对象，可以迭代
reader = pd.read_csv(input_file, chunksize=chunk_size, dtype=col_types)

for i, chunk in enumerate(reader):
    print(f"正在处理第 {i+1} 块数据 (包含 {len(chunk)} 行)...")

    # --- 核心处理：转换向量格式 ---
    # 将 embedding 列从字符串 "[0.1, 0.2...]" 转换为列表 [0.1, 0.2...]
    # 注意：如果数据量极大，ast.literal_eval 可能会稍慢，但最安全
    try:
        chunk['embedding'] = chunk['embedding'].apply(ast.literal_eval)
    except Exception as e:
        print(f"转换向量出错: {e}")
        break

    # --- 写入数据库 ---
    if i == 0:
        # 第一块数据：创建表 (mode="overwrite" 会覆盖旧表，"create" 会报错如果表存在)
        # 如果你想在旧表后面追加，且表已经存在，请确保用 mode="append"
        tbl = db.create_table("books", data=chunk, mode="overwrite")
        print("表已创建并写入第一批数据。")
    else:
        # 后续块：追加模式
        tbl.add(chunk)
        print(f"第 {i+1} 块数据已追加。")

print("所有数据处理完成！")
