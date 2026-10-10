#!/usr/bin/env python3
"""skills/x-html/scripts/check_html.py 的回归测试：合格样本退出 0，各类缺陷退出 1。"""
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKER = ROOT / "skills/x-html/scripts/check_html.py"

GOOD = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>缓存是什么</title>
<style>body { color: var(--ink); }</style>
</head>
<body>
<header><h1>缓存是什么</h1><p>它让常用的数据离你更近。</p></header>
<main>
<section>
<h2>先问缓存</h2>
<figure>
<svg viewBox="0 0 640 240" role="img"><title>请求先到缓存</title><rect x="10" y="10" width="100" height="40"></rect></svg>
<figcaption>请求先问缓存。</figcaption>
</figure>
<p>缓存存常用的数据。</p>
<p><strong>记住这句：</strong>缓存让等待变短。</p>
</section>
</main>
<footer><p>本文只讲缓存的作用。</p></footer>
</body>
</html>
"""


def run(path, *args):
    return subprocess.run([sys.executable, str(CHECKER), str(path), *args], capture_output=True, text=True)


def main():
    cases = 0
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)

        def write(name, text):
            target = tmp / name
            target.write_text(text, encoding="utf-8")
            return target

        good = write("good.html", GOOD)
        result = run(good)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "result: passed" in result.stdout, result.stdout
        cases += 1

        bad_external = write("external.html", GOOD.replace(
            '<rect x="10" y="10" width="100" height="40"></rect>',
            '<image href="https://example.com/a.png" width="10" height="10"></image>'))
        result = run(bad_external)
        assert result.returncode == 1, result.stdout
        assert "external resource" in result.stdout, result.stdout
        cases += 1

        bad_svg = write("svg-title.html", GOOD.replace("<title>请求先到缓存</title>", ""))
        result = run(bad_svg)
        assert result.returncode == 1 and "缺 <title> 或 aria-label" in result.stdout, result.stdout
        cases += 1

        bad_section = write("empty-section.html", GOOD.replace(
            """<figure>
<svg viewBox="0 0 640 240" role="img"><title>请求先到缓存</title><rect x="10" y="10" width="100" height="40"></rect></svg>
<figcaption>请求先问缓存。</figcaption>
</figure>""", "<p>这一节只有字。</p>"))
        result = run(bad_section)
        assert result.returncode == 1 and "没有图或表格" in result.stdout, result.stdout
        cases += 1

        bad_tag = write("unclosed.html", GOOD.replace("</section>", ""))
        result = run(bad_tag)
        assert result.returncode == 1 and "没有关闭" in result.stdout, result.stdout
        cases += 1

        bad_charset = write("charset.html", GOOD.replace('<meta charset="utf-8">', ""))
        result = run(bad_charset)
        assert result.returncode == 1 and "缺 <meta charset" in result.stdout, result.stdout
        cases += 1

        long_sentence = write("long.html", GOOD.replace(
            "缓存存常用的数据。", "缓存把经常用到的数据放在离使用者更近的地方，这样就不用每次都去远处取。"))
        result = run(long_sentence)
        assert result.returncode == 0 and "WARN: line" in result.stdout, result.stdout
        result = run(long_sentence, "--strict")
        assert result.returncode == 1 and "result: failed" in result.stdout, result.stdout
        cases += 1

        result = run(tmp / "missing.html")
        assert result.returncode == 2, result.stdout
        cases += 1

    print(f"test-html-check: passed ({cases} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
