from openai import OpenAI

# 1. 初始化客户端，指向本地 SGLang 服务
client = OpenAI(
    base_url="http://127.0.0.1:30000/v1",
    api_key="EMPTY"  # SGLang 本地部署通常不需要 API Key
)

raw_text = "今天天气真不错"
input_with_dim = f"<|dim:512|>{raw_text}"
# 2. 调用嵌入接口
response = client.embeddings.create(
    model="Qwen3-Embedding-0.6B",
    input=input_with_dim
    #dimensions=512  # <--- 关键：在这里直接指定你想要的维度！
                    # 你可以填 512, 768, 1024 等任意数值 (32~2560)
                    #这个功能有问题它只能输出1024维度的向量
)

# 3. 验证结果
vector = response.data[0].embedding
print(vector)
print(f"指定维度: 512")
print(f"实际返回维度: {len(vector)}")
print(f"向量前5位: {vector[:5]}")
