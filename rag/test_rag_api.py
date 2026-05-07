#!/usr/bin/env python3
"""
RAG API 测试脚本
用于测试向量查询接口
"""

import requests
import json
import numpy as np

# API 配置
API_BASE_URL = "http://localhost:9014/rag"

def test_api_connection():
    """测试API连接"""
    try:
        response = requests.get(f"{API_BASE_URL}/")
        print(f"API连接测试: {response.status_code}")
        print(f"响应内容: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"API连接失败: {e}")
        return False

def test_list_tables():
    """测试列出表"""
    try:
        response = requests.get(f"{API_BASE_URL}/tables")
        print(f"\n列出表测试: {response.status_code}")
        print(f"响应内容: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"列出表测试失败: {e}")
        return False

def test_table_info():
    """测试表信息"""
    try:
        response = requests.get(f"{API_BASE_URL}/table_info")
        print(f"\n表信息测试: {response.status_code}")
        print(f"响应内容: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"表信息测试失败: {e}")
        return False

def test_vector_query():
    """测试向量查询"""
    try:
        # 创建一个示例查询向量（1024维）
        query_vector = np.random.randn(1024).tolist()
        
        query_data = {
            "vector": query_vector,
            "count": 3
        }
        
        response = requests.post(
            f"{API_BASE_URL}/query",
            json=query_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"\n向量查询测试: {response.status_code}")
        if response.status_code == 200:
            results = response.json()
            print(f"查询结果数量: {len(results)}")
            for i, result in enumerate(results):
                print(f"\n结果 {i+1}:")
                print(f"  书名: {result['书名']}")
                print(f"  作者: {result['作者']}")
                print(f"  出版社: {result['出版社']}")
                print(f"  相似度: {result['similarity']}")
        else:
            print(f"错误响应: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"向量查询测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始测试RAG API...")
    
    # 检查API是否运行
    if not test_api_connection():
        print("API未运行，请先启动API服务")
        return
    
    # 执行各项测试
    tests = [
        ("列出表", test_list_tables),
        ("表信息", test_table_info),
        ("向量查询", test_vector_query)
    ]
    
    for test_name, test_func in tests:
        print(f"\n--- 测试 {test_name} ---")
        test_func()
    
    print("\n测试完成!")

if __name__ == "__main__":
    main()