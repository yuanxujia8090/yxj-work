#!/usr/bin/env python3
"""x-html 产物的机器检查：离线、标签闭合、图有名称、每节有图、句子与段落不过长。

用法：
    python3 check_html.py FILE.html [--strict] [--max-sentence N] [--max-sentences-per-block N]

退出码：0 通过；1 有硬失败（--strict 时警告也算失败）；2 用法错误。
硬失败才是"必须修"。警告只提示，交给写的人判断。
"""
from __future__ import annotations

import argparse
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
SKIP_TEXT = {"style", "script"}
BLOCK = {"p", "li", "dd", "dt", "figcaption", "h1", "h2", "h3", "h4", "h5", "h6", "td", "th", "summary", "blockquote"}
VISUAL = {"svg", "img", "figure", "table", "pre", "video", "canvas", "picture"}
EXTERNAL = re.compile(r"^\s*(?:https?:)?//", re.I)
CJK = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9]+")
SENTENCE_SPLIT = re.compile(r"[。！？；!?;\n]+")
WORDS_PER_FIGURE = 200


def rough_length(text: str) -> int:
    """按'字'粗算长度：汉字算 1，连续字母数字算 1，标点和空白不算。"""
    return len(CJK.findall(text))


def sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_SPLIT.split(text) if part.strip()]


class Doc(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hard: list[str] = []
        self.warn: list[str] = []
        self.open_tags: list[tuple[str, int]] = []
        self.block_stack: list[tuple[str, int, list[str]]] = []
        self.blocks: list[tuple[str, int, str]] = []
        self.section_stack: list[tuple[int, bool]] = []
        self.svg_starts: list[int] = []
        self.in_head = False
        self.lang = ""
        self.has_charset = False
        self.title = ""

    # ---- 外部资源
    def _check_external(self, tag: str, attrs: dict, line: int) -> None:
        for key in ("src", "srcset", "poster", "data"):
            if key in attrs and EXTERNAL.match(attrs[key]):
                self.hard.append(f"line {line}: external resource in <{tag} {key}=...>")
        # <a href> 指向出处是允许的；其他 href（link、use、image 等）都是外部资源。
        if tag != "a":
            for key in ("href", "xlink:href"):
                if key in attrs and EXTERNAL.match(attrs[key]):
                    self.hard.append(f"line {line}: external resource in <{tag} {key}=...>")

    # ---- HTMLParser hooks
    def handle_startendtag(self, tag, attrs):
        attrs = {key.lower(): (value or "") for key, value in attrs}
        line = self.getpos()[0]
        self._check_external(tag, attrs, line)
        if tag == "img":
            if not attrs.get("alt", "").strip():
                self.hard.append(f"line {line}: <img> 缺 alt 文本")
            if self.section_stack:
                self.section_stack[-1] = (self.section_stack[-1][0], True)

    def handle_starttag(self, tag, attrs):
        line = self.getpos()[0]
        attrs = {key.lower(): (value or "") for key, value in attrs}
        if tag == "html":
            self.lang = attrs.get("lang", "")
        elif tag == "meta" and "charset" in attrs:
            self.has_charset = True
        elif tag == "head":
            self.in_head = True
        elif tag == "title":
            if any(name == "svg" for name, _ in self.open_tags) and self.svg_starts:
                self.svg_starts[-1] = 0  # svg 已有 <title> 子元素
            self.open_tags.append(("title", line))
            return
        self._check_external(tag, attrs, line)
        if tag == "img" and not attrs.get("alt", "").strip():
            self.hard.append(f"line {line}: <img> 缺 alt 文本")
        if tag == "svg":
            if attrs.get("aria-label") or attrs.get("aria-labelledby"):
                self.svg_starts.append(0)  # 已有名称，不需要 title
            else:
                self.svg_starts.append(line)
        if tag == "section":
            self.section_stack.append((line, False))
        if self.section_stack and tag in VISUAL:
            self.section_stack[-1] = (self.section_stack[-1][0], True)
        if tag in BLOCK:
            self.block_stack.append((tag, line, []))
        if tag not in VOID:
            self.open_tags.append((tag, line))

    def handle_endtag(self, tag):
        line = self.getpos()[0]
        if tag == "head":
            self.in_head = False
        if tag == "title":
            for index in range(len(self.open_tags) - 1, -1, -1):
                if self.open_tags[index][0] == "title":
                    del self.open_tags[index]
                    break
            return
        if tag == "svg" and self.svg_starts:
            start = self.svg_starts.pop()
            if start:
                self.hard.append(f"line {start}: <svg> 缺 <title> 或 aria-label")
        if tag == "section" and self.section_stack:
            start, has_visual = self.section_stack.pop()
            if not has_visual:
                self.hard.append(f"line {start}: <section> 里没有图或表格")
        if tag in BLOCK:
            for index in range(len(self.block_stack) - 1, -1, -1):
                if self.block_stack[index][0] == tag:
                    _, start, parts = self.block_stack.pop(index)
                    self.blocks.append((tag, start, " ".join(parts).strip()))
                    break
        if tag in VOID:
            return
        for index in range(len(self.open_tags) - 1, -1, -1):
            if self.open_tags[index][0] == tag:
                del self.open_tags[index]
                return
        self.hard.append(f"line {line}: 多余的 </{tag}>")

    def handle_data(self, data):
        if self.in_head and not self.title.strip():
            self.title = data.strip()
            return
        for frame in self.block_stack:
            frame[2].append(data)


def check(path: Path, strict: bool, max_sentence: int, max_per_block: int) -> int:
    text = path.read_text(encoding="utf-8")
    doc = Doc()
    doc.feed(text)
    doc.close()

    if not doc.lang.lower().startswith("zh"):
        doc.hard.append("<html> 的 lang 必须以 zh 开头")
    if not doc.has_charset:
        doc.hard.append('缺 <meta charset="utf-8">')
    if not doc.title:
        doc.hard.append("缺非空的 <title>")
    for tag, line in doc.open_tags:
        doc.hard.append(f"line {line}: <{tag}> 没有关闭")
    for line in doc.svg_starts:
        if line:
            doc.hard.append(f"line {line}: <svg> 缺 <title> 或 aria-label")
    if not doc.blocks:
        doc.hard.append("正文没有可读段落（没有 <p> 等块元素）")
    if "@import" in text or re.search(r"url\(\s*['\"]?\s*(?:https?:)?//", text):
        doc.hard.append("CSS 里引用了外部资源（@import 或 url(//...)）")

    figures = text.lower().count("<svg") + len(re.findall(r"<img[\s/>]", text, re.I))
    if figures == 0:
        doc.hard.append("整份文件没有图")

    words = sum(rough_length(body) for _, _, body in doc.blocks)
    for tag, line, body in doc.blocks:
        if not body:
            continue
        found = sentences(body)
        if len(found) > max_per_block:
            doc.warn.append(f"line {line}: <{tag}> 有 {len(found)} 句，超过 {max_per_block} 句")
        for sentence in found:
            length = rough_length(sentence)
            if length > max_sentence:
                doc.warn.append(f"line {line}: 句子 {length} 字（上限 {max_sentence}）：{sentence[:30]}")
    if figures and words and words / figures > WORDS_PER_FIGURE:
        doc.warn.append(f"文字偏多：约 {words} 字 / {figures} 张图，平均每张图 {words // figures} 字")

    for item in doc.hard:
        print(f"HARD: {item}")
    for item in doc.warn:
        print(f"WARN: {item}")
    print(f"figures: {figures}  blocks: {len(doc.blocks)}  words: {words}")
    print(f"hard: {len(doc.hard)}  warnings: {len(doc.warn)}")
    failed = bool(doc.hard) or (strict and bool(doc.warn))
    print("result:", "failed" if failed else "passed")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--max-sentence", type=int, default=20)
    parser.add_argument("--max-sentences-per-block", type=int, default=3)
    args = parser.parse_args()
    path = Path(args.file)
    if not path.is_file():
        print(f"check_html: not a file: {path}", file=sys.stderr)
        return 2
    return check(path, args.strict, args.max_sentence, args.max_sentences_per_block)


if __name__ == "__main__":
    raise SystemExit(main())
