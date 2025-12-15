import os
import re
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
import pypinyin

PDF_PATH = "origin/events.pdf"
OUTPUT_DIR = "content/event"
TEMP_IMG_DIR = "temp_events_img"

def slugify(text):
    # Transliterate Chinese to Pinyin
    py = pypinyin.lazy_pinyin(text)
    text = '-'.join(py)
    # Remove non-alphanumeric
    text = re.sub(r'[^a-zA-Z0-9\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text).strip('-').lower()
    return text

def get_image_page_map(pdf_path):
    # Run pdfimages -list to get page numbers
    cmd = ["pdfimages", "-list", pdf_path]
    result = subprocess.run(cmd, capture_output=True, text=True)
    lines = result.stdout.splitlines()
    
    # Skip header (2 lines)
    # page num type ...
    # ----------------...
    
    image_map = {} # {page_num: [image_index]}
    
    # pdfimages extracts as prefix-000.jpg, prefix-001.jpg
    # The list output corresponds to these indices sequentially
    
    img_idx = 0
    for line in lines[2:]:
        parts = line.split()
        if not parts: continue
        if parts[0] == 'page': continue # Header repeat?
        
        try:
            page_num = int(parts[0])
            if page_num not in image_map:
                image_map[page_num] = []
            image_map[page_num].append(img_idx)
            img_idx += 1
        except ValueError:
            continue
            
    return image_map

def extract_images(pdf_path, out_dir):
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    
    # Extract images
    # -j for jpeg, but some might be png/ppm if not jpeg. 
    # pdfimages -all is better but might not be available in old versions.
    # Let's try -j first, if it fails for some, we might miss them.
    # The list output showed 'jpeg' for most.
    subprocess.run(["pdfimages", "-j", pdf_path, os.path.join(out_dir, "img")])

def parse_pdf_text(pdf_path):
    # Extract text with layout and form feeds
    cmd = ["pdftotext", "-layout", pdf_path, "-"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    full_text = result.stdout
    
    pages = full_text.split('\f')
    
    events = []
    current_event = None
    
    # Regex for "1. Title"
    title_re = re.compile(r'^\s*(\d+)\.\s+(.*)')
    
    for page_idx, page_text in enumerate(pages):
        page_num = page_idx + 1
        lines = page_text.splitlines()
        
        for line in lines:
            match = title_re.match(line)
            if match:
                # New event found
                if current_event:
                    events.append(current_event)
                
                event_id = match.group(1)
                title = match.group(2).strip()
                current_event = {
                    "id": event_id,
                    "title": title,
                    "content": [],
                    "pages": {page_num},
                    "date": None
                }
            else:
                if current_event:
                    current_event["content"].append(line)
                    current_event["pages"].add(page_num)
                    
                    # Try to find date if not found
                    if not current_event["date"]:
                        # Look for 20xx
                        date_match = re.search(r'(20\d{2})\s*年\s*(\d{1,2})\s*月', line)
                        if date_match:
                            y, m = date_match.groups()
                            current_event["date"] = f"{y}-{int(m):02d}-01" # Default to 1st
                        else:
                            # Try English date format roughly
                            date_match_en = re.search(r'(20\d{2})', line)
                            if date_match_en:
                                # Weak match, but better than nothing
                                # current_event["date"] = f"{date_match_en.group(1)}-01-01"
                                pass

    if current_event:
        events.append(current_event)
        
    return events

def main():
    print("Extracting images...")
    extract_images(PDF_PATH, TEMP_IMG_DIR)
    img_page_map = get_image_page_map(PDF_PATH)
    
    print("Parsing text...")
    events = parse_pdf_text(PDF_PATH)
    
    print(f"Found {len(events)} events.")
    
    for evt in events:
        title = evt["title"]
        # Clean title
        title = re.sub(r'\s+', ' ', title)
        
        # Generate slug
        slug_title = slugify(title)
        if len(slug_title) > 50:
            slug_title = slug_title[:50]
            
        date_str = evt["date"] if evt["date"] else "2025-01-01"
        
        # Create directory
        folder_name = f"{slug_title}"
        # If date exists, maybe prepend year? User didn't specify, but standard is usually just slug or date-slug.
        # Let's use slug.
        
        target_dir = os.path.join(OUTPUT_DIR, folder_name)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        # Move images
        # Get images for the pages this event covers
        evt_images = []
        for p in evt["pages"]:
            if p in img_page_map:
                for img_idx in img_page_map[p]:
                    # Source file: img-000.jpg
                    src_name = f"img-{img_idx:03d}.jpg"
                    src_path = os.path.join(TEMP_IMG_DIR, src_name)
                    
                    if os.path.exists(src_path):
                        dst_name = f"image-{img_idx}.jpg"
                        dst_path = os.path.join(target_dir, dst_name)
                        shutil.copy(src_path, dst_path)
                        evt_images.append(dst_name)
        
        # Create index.md
        content_text = "\n".join(evt["content"]).strip()
        
        # Try to extract a better summary/abstract
        # First paragraph is often English title or Date
        # Let's just dump the text for now.
        
        md_content = f"""---
title: "{title}"
date: {date_str}
summary: ""
abstract: |
  {content_text.replace('"', '\\"')}
image:
  caption: ""
  focal_point: ""
---

## 会议照片

{{{{< gallery >}}}}
"""
        for img in evt_images:
            md_content += f'{{{{< figure src="{img}" >}}}}\n'
            
        # Also set featured image
        if evt_images:
            # Copy first image to featured.jpg
            first_img = os.path.join(target_dir, evt_images[0])
            featured_path = os.path.join(target_dir, "featured.jpg")
            shutil.copy(first_img, featured_path)

        with open(os.path.join(target_dir, "index.md"), "w", encoding="utf-8") as f:
            f.write(md_content)
            
        print(f"Created event: {title} -> {target_dir}")

    # Cleanup
    # shutil.rmtree(TEMP_IMG_DIR)

if __name__ == "__main__":
    main()
