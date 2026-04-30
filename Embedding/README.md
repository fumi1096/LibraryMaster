可以使用嵌入模型的api
您已开通百炼服务并获得API-KEY， 请参考获取API Key。

已导入 API-KEY，请参考配置API Key到环境变量。

安装 LlamaIndex 核心组件、DashScopeEmbedding 以及相关依赖。



pip install llama-index-core
pip install llama-index-embeddings-dashscope
pip install llama-index-readers-file
pip install docx2txt



这里使用本地部署嵌的入模型Qwen3_embedding-0.6b  1024维度 使用sglang运行
模型在huggingface下载放在model文件夹里

pip install --upgrade pip
pip install uv
uv pip install "sglang[all]>=0.5.3rc0"
sudo apt update
sudo apt install libnuma-dev
建议安装在虚拟环境或docker里


