#!/usr/bin/env python3
"""
从 static/papers/ 的论文 PDF 中提取首页作为封面图 featured.jpg。

规则：遍历 content/publication/*/index.md，读取 front matter 的 url_pdf（形如 /papers/xxx.pdf），
找到对应的 static/papers/xxx.pdf，然后截取第一页保存到同目录下 featured.jpg。

依赖：系统需要 Poppler 的 pdftoppm（本环境已安装）。
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from urllib.parse import unquote

# 文件路径配置
ROOT_DIR = Path(__file__).resolve().parents[1]
PAPERS_DIR = ROOT_DIR / "static" / "papers"
PUBLICATION_DIR = ROOT_DIR / "content" / "publication"


FRONT_MATTER_RE = re.compile(r"(?s)^---\s*\n(.*?)\n---\s*\n")
URL_PDF_RE = re.compile(r"(?m)^url_pdf:\s*(?P<q>['\"]?)(?P<val>.+?)(?P=q)\s*$")


def _read_front_matter(text: str) -> str | None:
    match = FRONT_MATTER_RE.search(text)
    return match.group(1) if match else None


def _extract_url_pdf(front_matter: str) -> str | None:
    match = URL_PDF_RE.search(front_matter)
    if not match:
        return None
    return match.group("val").strip()


def _url_pdf_to_pdf_path(url_pdf: str) -> Path | None:
    if url_pdf.startswith("http://") or url_pdf.startswith("https://"):
        return None
    normalized = url_pdf.strip()
    normalized = normalized.strip("\"").strip("'")

    if normalized.startswith("/papers/"):
        rel = normalized[len("/papers/") :]
    elif normalized.startswith("papers/"):
        rel = normalized[len("papers/") :]
    else:
        return None

    rel = unquote(rel)
    return PAPERS_DIR / rel


def extract_first_page_as_jpg(
    pdf_path: Path,
    output_path: Path,
    *,
    dpi: int = 150,
    max_width: int = 600,
    pdftoppm_bin: str | None = None,
) -> None:
    """用 pdftoppm 抽取 PDF 首页为 JPEG。"""
    tmp_prefix = output_path.parent / "_featured_tmp"
    tmp_jpg = tmp_prefix.with_suffix(".jpg")

    if tmp_jpg.exists():
        tmp_jpg.unlink()

    if pdftoppm_bin:
        pdftoppm = pdftoppm_bin
    else:
        pdftoppm = shutil.which("pdftoppm")

    if not pdftoppm:
        for candidate in (
            "/home/lxh/anaconda3/bin/pdftoppm",
            "/opt/conda/bin/pdftoppm",
            "/usr/bin/pdftoppm",
            "/usr/local/bin/pdftoppm",
        ):
            if Path(candidate).exists():
                pdftoppm = candidate
                break

    if not pdftoppm:
        raise FileNotFoundError(
            "pdftoppm not found. Add it to PATH or pass --pdftoppm /full/path/to/pdftoppm"
        )

    cmd = [
        str(pdftoppm),
        "-f",
        "1",
        "-l",
        "1",
        "-r",
        str(dpi),
        "-jpeg",
        "-singlefile",
        "-scale-to-x",
        str(max_width),
        "-scale-to-y",
        "-1",
        str(pdf_path),
        str(tmp_prefix),
    ]

    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if not tmp_jpg.exists():
        raise RuntimeError("pdftoppm did not produce output image")

    if output_path.exists():
        output_path.unlink()
    tmp_jpg.rename(output_path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract first page from PDFs as featured.jpg for each publication")
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing featured.jpg")
    parser.add_argument("--dpi", type=int, default=150, help="render DPI (default: 150)")
    parser.add_argument("--max-width", type=int, default=600, help="output max width in pixels (default: 600)")
    parser.add_argument(
        "--pdftoppm",
        type=str,
        default=None,
        help="optional full path to pdftoppm (overrides PATH lookup)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("PDF 封面提取（按 publication/index.md 的 url_pdf 匹配）")
    print(f"PAPERS_DIR: {PAPERS_DIR}")
    print(f"PUBLICATION_DIR: {PUBLICATION_DIR}")
    print("=" * 60)

    if not PAPERS_DIR.exists():
        print(f"✗ papers 目录不存在: {PAPERS_DIR}")
        return 2
    if not PUBLICATION_DIR.exists():
        print(f"✗ publication 目录不存在: {PUBLICATION_DIR}")
        return 2

    success_count = 0
    fail_count = 0
    skip_count = 0
    no_pdf_count = 0

    index_files = sorted(
        p for p in PUBLICATION_DIR.glob("*/index.md") if p.name == "index.md"
    )

    for index_md in index_files:
        text = index_md.read_text(encoding="utf-8", errors="ignore")
        fm = _read_front_matter(text)
        if not fm:
            continue

        url_pdf = _extract_url_pdf(fm)
        if not url_pdf:
            continue

        pdf_path = _url_pdf_to_pdf_path(url_pdf)
        if not pdf_path:
            continue

        if not pdf_path.exists():
            print(f"\n✗ PDF不存在: {pdf_path}")
            print(f"  来自: {index_md}")
            no_pdf_count += 1
            continue

        out_dir = index_md.parent
        output_path = out_dir / "featured.jpg"

        if output_path.exists() and not args.overwrite:
            skip_count += 1
            continue

        print(f"\n处理: {pdf_path.name}")
        print(f"  -> {output_path}")
        try:
            extract_first_page_as_jpg(
                pdf_path,
                output_path,
                dpi=args.dpi,
                max_width=args.max_width,
                pdftoppm_bin=args.pdftoppm,
            )
            success_count += 1
        except Exception as e:
            print(f"  ✗ 失败: {e}")
            fail_count += 1

    print("\n" + "=" * 60)
    print(f"完成：成功 {success_count}，跳过 {skip_count}，失败 {fail_count}，缺失PDF {no_pdf_count}")
    print("=" * 60)
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
