import csv
import json
import argparse
from pathlib import Path
from llama_index.embeddings.dashscope import DashScopeEmbedding


def read_csv_rows(input_path):
    """读取 CSV 文件并返回行数据和字段名列表。

    参数:
        input_path (Path | str): 输入 CSV 文件路径。

    返回:
        tuple: (rows, fieldnames)，其中 rows 是包含每行字典的列表，
        fieldnames 是 CSV 表头字段名列表。
    """
    with open(input_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader]
        fieldnames = reader.fieldnames or []
    return rows, fieldnames


def write_csv_rows(output_path, fieldnames, rows):
    """将带向量结果的行写回新的 CSV 文件。

    参数:
        output_path (Path | str): 输出 CSV 文件路径。
        fieldnames (list[str]): 输出字段名列表，包含新增 embedding 列。
        rows (list[dict]): 要写入的行字典列表。
    """
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_text_for_embedding(row):
    """将一行 CSV 数据转换为用于生成嵌入的文本字符串。

    这里将每个字段值转换为字符串并拼接在一起，忽略 None 值。
    """
    return ' '.join(str(value) for value in row.values() if value is not None)


def main():
    parser = argparse.ArgumentParser(description='对 CSV 每一行进行向量化嵌入，并输出新增 embedding 列的 CSV。')
    parser.add_argument('--input', '-i', default='testtable.csv', help='输入 CSV 文件路径')
    parser.add_argument('--output', '-o', default='testtable_with_vector.csv', help='输出 CSV 文件路径')
    parser.add_argument('--column-name', default='embedding', help='新增向量列列名')
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    # 读取 CSV 数据
    rows, fieldnames = read_csv_rows(input_path)

    if not rows:
        raise SystemExit('输入文件中未找到数据行。')

    # 将每一行数据组合成文本字符串，作为 embedding 的输入
    texts = [build_text_for_embedding(row) for row in rows]

    # 初始化 DashScopeEmbedding 并批量生成文本向量
    embedder = DashScopeEmbedding(model_name='text-embedding-v2')
    embeddings = embedder.get_text_embedding_batch(texts)

    # 将生成的 embedding 以 JSON 字符串形式存回每行数据
    output_fieldnames = list(fieldnames) + [args.column_name]
    output_rows = []
    for row, embedding in zip(rows, embeddings):
        row[args.column_name] = json.dumps(embedding, ensure_ascii=False)
        output_rows.append(row)

    # 写入结果 CSV
    write_csv_rows(output_path, output_fieldnames, output_rows)
    print(f'已生成向量化 CSV：{output_path}')


if __name__ == '__main__':
    main()
