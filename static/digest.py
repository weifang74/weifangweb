#!/usr/bin/env python3
"""
论文摘要生成脚本
使用 Gemini REST API 分析 PDF 论文并生成 Hugo 格式的 markdown 文件
避免使用 google-generativeai SDK 的依赖冲突
"""

import os
import re
import json
import base64
import requests
from pathlib import Path
import time

# 配置 Gemini API
GEMINI_API_KEY = ""  # 请替换为您的API密钥

# Gemini API 端点
GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"

# 文件路径配置
PAPERS_DIR = "/mnt/e/weifangweb/static/papers"
PUBLICATION_DIR = "/mnt/e/weifangweb/content/publication"

# PDF文件名到文件夹的映射
PDF_TO_FOLDER = {
    "2021 西部人居环境学刊  基于PCA-ESDA的成渝城市群经济发展空间差异研究.pdf": "2021-xbrjhj-chengyu-esda",
    "2022  land A Multi-Objective Optimization of Physical Activity Spaces.pdf": "2022-land-physical-activity",
    "2022 Land The Effect of Flood Risk on Residential Land Prices.pdf": "2022-land-flood-risk",
    "2022 sustainability Contributions of Natural Carbon Sink Capacity and Carbon Neutrality in the Context of Net-Zero Carbon Cities.pdf": "2022-sustainability-carbon-neutrality",
    "2022 建筑与文化 建成环境与体力活动关系的研究及应用.pdf": "2022-jzywh-built-environment",
    "2022 西部人居环境学刊 城市体力活动空间供需均衡与空间优化研究.pdf": "2022-xbrjhj-physical-activity-optimization",
    "2023 Environmental Science and Policy  A review of ES knowledge use in spatial planning.pdf": "2023-esp-es-spatial-planning",
    "2023 Sustainability Commercial Culture as a Key Impetus in Shaping and Transforming Urban Structure.pdf": "2023-sustainability-commercial-culture",
    "2024 Journal of Cleaner Production. Impact of territorial spatial landscape pattern on PM2.5 and O3   concentrations in the Yangtze River delta urban agglomeration.pdf": "2024-jcp-pm25-o3",
    "2024 sustainability.  Evaluation of Urban Land Suitability under Multiple Sea Level Rise Scenarios.pdf": "2024-sustainability-sea-level-rise",
    "2025 Air Quality, Atmosphere  Health. Influence of urban forest size and form on PM2.5 and O3 concentrations- A perspective of size threshold.pdf": "2025-aqah-forest-pm25-o3",
    "2025 Atmospheric Pollution Research. Reducing PM2.5 and O3 through optimizing urban ecological land form.pdf": "2025-apr-ecological-land",
    "2025 Building and Environment Combined effects of urban morphology on land surface temperature.pdf": "2025-be-urban-morphology-lst",
    "2025 农业资源与环境学报 基于SD PLUS耦合模型的杭州市土地利用多情景模拟.pdf": "2025-nyzyyhjxb-sd-plus",
}


def read_pdf_as_base64(pdf_path):
    """读取PDF文件并转换为base64"""
    with open(pdf_path, 'rb') as f:
        return base64.standard_b64encode(f.read()).decode('utf-8')


def generate_paper_summary(pdf_path):
    """使用Gemini REST API生成论文摘要"""
    
    print(f"读取文件: {pdf_path}")
    pdf_base64 = read_pdf_as_base64(pdf_path)
    
    prompt = """
请仔细阅读这篇学术论文PDF，提取以下信息并以JSON格式返回（只返回JSON，不要其他文字）：

{
  "title": "论文标题（原文）",
  "title_cn": "论文标题（中文翻译，如果原文是中文则相同）",
  "authors": ["作者1", "作者2", "作者3"],
  "publication": "期刊名称",
  "publication_short": "期刊缩写",
  "date": "YYYY-MM-DD",
  "doi": "DOI号（如果有，没有则留空）",
  "abstract": "英文摘要（100-200词）",
  "abstract_cn": "中文摘要（100-200字）",
  "tags": ["关键词1", "关键词2", "关键词3"],
  "categories": ["学科分类1", "学科分类2"]
}

请确保：
1. 日期格式为 YYYY-MM-DD（如果只有年份，使用 YYYY-01-01）
2. 摘要要准确简洁，突出研究目的、方法和主要发现
3. 标签应该是具体的研究主题关键词
4. 分类应该是更广泛的学科领域
"""
    
    # 构建请求体
    payload = {
        "contents": [{
            "parts": [
                {
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": pdf_base64
                    }
                },
                {
                    "text": prompt
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 2048
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print("正在调用 Gemini API...")
    response = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=120)
    
    if response.status_code != 200:
        print(f"API错误: {response.status_code}")
        print(response.text)
        return None
    
    result = response.json()
    
    try:
        text = result['candidates'][0]['content']['parts'][0]['text']
        return text
    except (KeyError, IndexError) as e:
        print(f"解析响应失败: {e}")
        print(f"响应内容: {result}")
        return None


def create_markdown_file(folder_name, paper_info, pdf_filename):
    """创建Hugo格式的markdown文件"""
    
    # 清理JSON格式
    json_text = paper_info.strip()
    if json_text.startswith("```json"):
        json_text = json_text[7:]
    if json_text.startswith("```"):
        json_text = json_text[3:]
    if json_text.endswith("```"):
        json_text = json_text[:-3]
    json_text = json_text.strip()
    
    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print(f"JSON解析错误: {e}")
        print(f"原始内容: {json_text}")
        return False
    
    # 处理作者列表
    authors_yaml = "\n".join([f"- {author}" for author in data.get('authors', [])])
    tags_yaml = "\n".join([f"- {tag}" for tag in data.get('tags', [])])
    
    # 转义引号
    title = data.get('title', '').replace('"', '\\"')
    abstract = data.get('abstract', '').replace('"', '\\"')
    abstract_cn = data.get('abstract_cn', '').replace('"', '\\"')
    
    # 构建markdown内容
    markdown_content = f'''---
title: "{title}"
authors:
{authors_yaml}
date: "{data.get('date', '')}"
doi: "{data.get('doi', '')}"

publishDate: "{data.get('date', '')}"

publication_types: ["article-journal"]

publication: "{data.get('publication', '')}"
publication_short: "{data.get('publication_short', '')}"

abstract: "{abstract}"

summary: "{abstract_cn}"

tags:
{tags_yaml}

featured: true

url_pdf: '/papers/{pdf_filename}'
url_code: ''
url_dataset: ''
url_poster: ''
url_project: ''
url_slides: ''
url_source: ''
url_video: ''

image:
  caption: ''
  focal_point: ''
  preview_only: false

projects: []

slides: ""
---

## 摘要

{data.get('abstract_cn', '')}

## Abstract

{data.get('abstract', '')}

## 引用格式

```bibtex
@article{{{folder_name.replace('-', '_')},
  title={{{data.get('title', '')}}},
  author={{{' and '.join(data.get('authors', []))}}},
  journal={{{data.get('publication', '')}}},
  year={{{data.get('date', '')[:4] if data.get('date') else ''}}},
  doi={{{data.get('doi', '')}}}
}}
```
'''
    
    # 创建文件夹并保存
    folder_path = Path(PUBLICATION_DIR) / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    
    output_file = folder_path / "index.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(markdown_content)
    
    print(f"✓ 已创建: {output_file}")
    return True


def process_single_paper(pdf_filename, folder_name):
    """处理单篇论文"""
    pdf_path = Path(PAPERS_DIR) / pdf_filename
    
    if not pdf_path.exists():
        print(f"✗ 文件不存在: {pdf_path}")
        return False
    
    print(f"\n{'='*60}")
    print(f"处理: {pdf_filename}")
    print(f"目标文件夹: {folder_name}")
    
    try:
        # 生成摘要
        paper_info = generate_paper_summary(str(pdf_path))
        
        if paper_info is None:
            return False
        
        # 创建markdown文件
        success = create_markdown_file(folder_name, paper_info, pdf_filename)
        
        # 避免API限流
        time.sleep(5)
        
        return success
        
    except Exception as e:
        print(f"✗ 处理失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("论文摘要生成脚本 (REST API 版本)")
    print("=" * 60)
    
    # 检查API密钥
    if GEMINI_API_KEY == "YOUR_GEMINI_API_KEY":
        print("错误: 请先设置您的 Gemini API 密钥")
        print("在脚本中修改 GEMINI_API_KEY 变量")
        print("获取密钥: https://makersuite.google.com/app/apikey")
        return
    
    success_count = 0
    fail_count = 0
    
    # 处理每个PDF文件
    for pdf_filename, folder_name in PDF_TO_FOLDER.items():
        if process_single_paper(pdf_filename, folder_name):
            success_count += 1
        else:
            fail_count += 1
    
    print("\n" + "=" * 60)
    print(f"处理完成！成功: {success_count}, 失败: {fail_count}")
    print("=" * 60)


if __name__ == "__main__":
    main()
