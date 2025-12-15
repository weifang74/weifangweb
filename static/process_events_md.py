#!/usr/bin/env python3
"""
从 origin/events/events.md 提取会议信息并生成 Hugo event 页面
"""
import os
import re
import shutil
from pathlib import Path

# 配置路径
SOURCE_MD = Path("/mnt/e/weifangweb/origin/events/events.md")
SOURCE_MEDIA = Path("/mnt/e/weifangweb/origin/events/media")
OUTPUT_DIR = Path("/mnt/e/weifangweb/content/event")

# 会议数据：手动整理的标题、slug、日期映射
# 从 markdown 文件中识别出的会议
EVENTS_DATA = [
    {
        "title": "中国—加拿大—非洲可持续城市化国际研讨会（ICCCASU）",
        "slug": "2015-ICCCASU",
        "date": "2015-10-24",
        "images": ["image1.jpeg", "image2.jpeg"],
    },
    {
        "title": "中国驻加拿大大使馆教育处晚宴",
        "slug": "2015-embassy-dinner",
        "date": "2015-10-25",
        "images": ["image3.jpeg", "image4.jpeg"],
    },
    {
        "title": "与中国西藏历史与文化专家代表团专题交流会",
        "slug": "2015-tibet-exchange",
        "date": "2015-11-17",
        "images": ["image5.jpg"],
    },
    {
        "title": "中国驻加拿大使馆春节招待会",
        "slug": "2017-spring-festival",
        "date": "2017-01-25",
        "images": ["image6.jpg", "image7.jpeg"],
    },
    {
        "title": "顾朝林教授与曹沪华教授浙大讲座",
        "slug": "2017-gu-cao-lecture",
        "date": "2017-05-17",
        "images": ["image8.jpg", "image9.jpeg", "image10.jpg", "image11.jpg", "image12.jpeg", "image13.jpeg"],
    },
    {
        "title": "德国国家科学与工程院院士Dr.Bernhard Mueller报告会",
        "slug": "2017-mueller-report",
        "date": "2017-11-01",
        "images": ["image14.jpeg", "image15.jpeg", "image16.jpeg"],
    },
    {
        "title": "中国自然资源学会国土空间规划青年学术论坛",
        "slug": "2021-spatial-planning-forum",
        "date": "2021-05-01",
        "images": ["image17.jpeg", "image18.jpeg"],
    },
    {
        "title": "全球南方城市挑战——以非洲与中国为例 专题讲座",
        "slug": "2022-global-south-lecture",
        "date": "2022-10-20",
        "images": [],
    },
    {
        "title": "同济大学朱若霖教授来访讲座",
        "slug": "2021-zhu-ruolin-lecture",
        "date": "2021-06-16",
        "images": ["image19.jpeg"],
    },
    {
        "title": "北京林业大学园林讲堂——国土空间规划专题系列讲座",
        "slug": "2022-bjfu-lecture",
        "date": "2022-06-23",
        "images": ["image20.jpeg"],
    },
    {
        "title": "第五届中国—加拿大—非洲可持续城市化国际研讨会（ICCCASU5）",
        "slug": "2023-ICCCASU5",
        "date": "2023-12-10",
        "images": [],
    },
    {
        "title": "城市总规划师模式发展论坛——规划、建设、治理融合发展大会",
        "slug": "2025-chief-planner-forum",
        "date": "2025-03-01",
        "images": ["image21.png", "image22.jpeg", "image23.jpeg", "image24.jpeg", "image25.jpeg"],
    },
    {
        "title": "中国自然资源学会2025年国土空间规划学术年会",
        "slug": "2025-spatial-planning-annual",
        "date": "2025-11-15",
        "images": ["image26.jpeg", "image27.jpeg"],
    },
    {
        "title": "滨海城市生态韧性与规划设计论坛",
        "slug": "2025-coastal-resilience-forum",
        "date": "2025-11-28",
        "images": ["image28.jpeg", "image29.jpeg"],
    },
]

# 从 markdown 文件解析各会议的正文内容
def parse_events_content(md_path):
    """解析 markdown 文件，提取每个会议的正文"""
    content = md_path.read_text(encoding="utf-8")
    
    # 用正则找所有标题（===下划线形式）
    # 模式: 标题行\n===+
    pattern = r'^(.+)\n={3,}'
    
    # 找到所有标题及其位置
    matches = list(re.finditer(pattern, content, re.MULTILINE))
    
    events_content = {}
    
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        title = re.sub(r'\*+', '', title).strip()  # 移除加粗标记
        
        # 内容从标题结束到下一个标题开始
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(content)
        
        body = content[start:end].strip()
        
        # 移除图片引用（包括各种格式）
        body_no_images = re.sub(r'!\[.*?\]\(.*?\)(\{[^}]*\})?', '', body)
        # 移除残留的图片尺寸标记 {width="..." height="..."}
        body_no_images = re.sub(r'\{width="[^"]*"[^}]*\}', '', body_no_images)
        # 移除 Image 标记
        body_no_images = re.sub(r'\[Image\]', '', body_no_images)
        # 移除表格语法
        body_no_images = re.sub(r'\+[-=]+\+[-=]+\+', '', body_no_images)
        body_no_images = re.sub(r'\|.*?\|', '', body_no_images)
        # 移除 blockquote 标记
        body_no_images = re.sub(r'^>\s*', '', body_no_images, flags=re.MULTILINE)
        # 移除链接但保留文字
        body_no_images = re.sub(r'<https?://[^>]+>', '', body_no_images)
        # 移除 http 链接（非尖括号形式）
        body_no_images = re.sub(r'https?://\S+', '', body_no_images)
        # 移除表格分隔线
        body_no_images = re.sub(r'-{20,}', '', body_no_images)
        # 清理多余空行和空格
        body_no_images = re.sub(r'\n{3,}', '\n\n', body_no_images)
        body_no_images = re.sub(r'[ \t]+', ' ', body_no_images)
        body_no_images = body_no_images.strip()
        
        events_content[title] = body_no_images
        
    return events_content

def find_content_for_event(event_title, events_content):
    """为事件找到匹配的正文内容"""
    # 清理事件标题用于匹配
    clean_event = re.sub(r'[—\-\s""*]', '', event_title)
    
    for title, content in events_content.items():
        # 清理解析到的标题
        clean_title = re.sub(r'[—\-\s""*]', '', title)
        
        # 检查是否有足够的重叠
        if clean_event[:15] in clean_title or clean_title[:15] in clean_event:
            return content
    
    # 尝试关键词匹配
    keywords = ["ICCCASU", "大使馆", "西藏", "春节", "顾朝林", "Mueller", "青年学术", 
                "全球南方", "朱若霖", "北京林业", "总规划师", "2025", "滨海"]
    for kw in keywords:
        if kw in event_title:
            for title, content in events_content.items():
                if kw in title:
                    return content
    
    return ""

def create_event_page(event, events_content):
    """创建单个会议页面"""
    slug = event["slug"]
    target_dir = OUTPUT_DIR / slug
    
    # 创建目录
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # 复制图片
    for i, img_name in enumerate(event["images"]):
        src = SOURCE_MEDIA / img_name
        if src.exists():
            # 第一张作为 featured
            if i == 0:
                dst = target_dir / "featured.jpg"
            else:
                dst = target_dir / img_name
            shutil.copy(src, dst)
    
    # 获取正文内容
    body_content = find_content_for_event(event["title"], events_content)
    
    # 提取摘要（第一段或前200字）
    paragraphs = [p.strip() for p in body_content.split('\n\n') if p.strip()]
    summary = paragraphs[0][:200] if paragraphs else ""
    
    # 生成 index.md
    # 处理 abstract 中的特殊字符
    abstract_escaped = body_content.replace('"', '\\"')
    
    md_content = f'''---
title: "{event["title"]}"
date: "{event["date"]}"
all_day: true

summary: "{summary[:100]}..."

abstract: |
  {body_content}

authors: []
tags: []

featured: false

image:
  caption: ""
  focal_point: ""

url_code: ""
url_pdf: ""
url_slides: ""
url_video: ""
---

'''
    
    # 添加图片展示
    if len(event["images"]) > 1:
        md_content += "## 会议照片\n\n"
        for img_name in event["images"][1:]:  # 跳过 featured
            md_content += f'![{img_name}]({img_name})\n\n'
    
    index_path = target_dir / "index.md"
    index_path.write_text(md_content, encoding="utf-8")
    
    print(f"✓ 创建: {slug}")
    print(f"  - 标题: {event['title']}")
    print(f"  - 图片: {len(event['images'])} 张")

def main():
    print("=" * 60)
    print("从 events.md 提取会议信息")
    print("=" * 60)
    
    # 解析 markdown 内容
    events_content = parse_events_content(SOURCE_MD)
    print(f"解析到 {len(events_content)} 个章节")
    
    # 创建输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 处理每个会议
    for event in EVENTS_DATA:
        create_event_page(event, events_content)
    
    print("=" * 60)
    print(f"完成！共创建 {len(EVENTS_DATA)} 个会议页面")
    print("=" * 60)

if __name__ == "__main__":
    main()
