import requests

# 默认端口通常是 8080
url = "http://localhost:8080/v1/embeddings" 

data = {
    "content": "ththd trd"
}

response = requests.post(url, json=data)

if response.status_code == 200:
    result = response.json()
    #print(result)
    # llama.cpp 返回的结构通常在 'embedding' 字段里
    embedding_vector = result[0]['embedding'][0]
    print(f"向量维度: {len(embedding_vector)}")
    print(f"前10个数值: {embedding_vector[:10]}")
else:
    print("出错了:", response.text)
