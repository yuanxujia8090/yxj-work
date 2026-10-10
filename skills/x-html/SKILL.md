---
name: x-html
description: 用户主动调用时，把一个主题或一份文档做成自包含的中文图文 HTML 讲解，面向初中生阅读水平，以图为主、文字遵循受控短句写法。适合"讲给不懂的人听""做成网页图册""给一篇文章配图"。
disable-model-invocation: true
---

# x-html

## File boundary

The workflow root is the directory this skill runs in (`<execution-root>`). Every durable file this skill
generates goes under:

```text
<execution-root>/.work-docs/tasks/<task-id>/
├── contract.md   what done means, allowed changes, verification layers
├── state.md      stage, status, evidence pointers, blockers
├── outputs/      the HTML explainer and any other deliverable
├── evidence/     command output, measurements, failure evidence
├── audit/        decisions, checkpoints, work-in-progress records
└── tmp/          fixtures and disposable material
```

Reuse the task id already in progress when the scope matches (read `.work-docs/index.md` first), otherwise
allocate one: `{YYYYMMDD}-{NN}-{slug}`, where `NN` is a two-digit per-day counter that
restarts at `01` and never reuses a retired number, then append the new task to `.work-docs/index.md`.
Never place workflow output in a project docs directory, in another skill's directory, in a
tool-specific hidden directory, or outside the repository.

Files that are themselves the task target -- project code, project docs, existing config -- may be modified
in place. Record those paths in the contract and in `evidence/` before changing them, and do not copy them
into `.work-docs`. Before running any third-party skill that writes files, take a before/after inventory; a
write outside `.work-docs` that the contract did not authorize is a boundary violation: stop and report it.

例外：用户明确给出 HTML 的输出路径时，写到那个路径。把路径同时写进契约和 `evidence/`，不复制进 `.work-docs`。用户没给路径时，写到 `outputs/<slug>.html`，并在回复里给出完整路径。

## 这个技能做什么

把一个主题或一份文档，变成**一个** HTML 文件。读者是初中生。读者打开文件就能看懂，不需要你旁边讲解。

三条硬要求：

1. **自包含**：单文件，双击可看。不联网。图片、字体、脚本全部写在文件里。
2. **以图为主**：每个小节至少一个图。文字只说图在说什么。
3. **受控短句**：中文，一句一个意思，句子不超过 20 字。规则见下文。

图只能用内联 SVG 和 CSS 画。联网取图、外链 CDN、外部字体一律禁止：文件必须离线可看。

## 步骤

1. **定三件事**。读输入（主题文字，或用户给的文档路径）。确认：读者原有水平、读完必须知道的 3 到 7 件事、输出路径。用户没说就按初中生、3 到 7 件事、`outputs/<slug>.html` 处理。
2. **写内容清单**。每条一件事，写成一句话。每句话后面标一个图型（见图形词汇表）。清单先写进 `outputs/`，再动手画。清单超过 7 条就砍。
3. **画图**。按图形词汇表选图型，用内联 SVG 画。一张图只讲一件事。图里写中文标签和数字，不写英文缩写。
4. **写文字**。每张图配：一句图标题、最多 3 句说明、一句"记住这句"。全文用受控短句规则。生词第一次出现时，先用日常生活里的事物解释。
5. **自检**。运行检查器：

```bash
python3 <skill-dir>/scripts/check_html.py <你的文件>.html --strict
```

硬失败必须修到 0。警告逐条判断：能改就改，不能改就在交付说明里写出原因。
6. **交付**。在回复里写：文件完整路径、共有几节几张图、哪些内容没覆盖、怎么打开。

## 受控短句规则

规则来自 ASD-STE100 的思路：把文字限制在一个小词表和小句式里，让任何人第一次读就能懂。用中文时按下面十条执行。

| 编号 | 规则 | 改前 | 改后 |
|---|---|---|---|
| 1 | 一句一个意思，不超过 20 字 | 由于请求在到达服务器之前就已经被缓存层拦截，所以你看到的是旧数据。 | 请求先到缓存层。缓存层存着旧数据。所以你看到的是旧数据。 |
| 2 | 一段最多 3 句 | 上面那句加这句加下一句。 | 拆成两段。 |
| 3 | 主动语态，句子里有主语和动词 | 数据被缓存层拦住了。 | 缓存层拦住数据。 |
| 4 | 一个概念一个词，全文不改名 | 前面叫"缓存"，后面叫"暂存区"。 | 全文只叫"缓存"。 |
| 5 | 用日常词 | 进行、该、其、此外、因此、以便、实现、基于、若干 | 做、这个、它的、还有、所以、这样就能、做到、用、几个 |
| 6 | 不写从句和括号夹注 | 缓存（一种临时存储）会先返回旧数据。 | 缓存是一种临时存储。它会先返回旧数据。 |
| 7 | 让人做事时用祈使句 | 用户可以点击这个按钮。 | 点这个按钮。 |
| 8 | 数字、单位、时间写全 | 等几秒、上次 | 等 3 秒、2026 年 10 月 |
| 9 | 不用比喻动词；打比方时单独写一行 | 请求骑着缓存飞回来。 | 打个比方：缓存像门口的小货架。 |
| 10 | 不写空话结论，只写看得见的事实 | 性能得到极大提升。 | 等待时间从 3 秒降到 0.2 秒。 |

另外两条只对初中生读者生效：

- 生词第一次出现，立刻用一个生活里的东西解释。例如"缓存像门口的小货架，拿东西不用进屋"。
- 一屏只说一个重点。重点之间用空行和图隔开。

## 图形词汇表

要讲什么意思，就用对应的图。图型不够用时，宁可拆成两张图，不要塞进一张。

| 要讲的意思 | 画什么 | SVG 画法 |
|---|---|---|
| 先后步骤 | 竖排编号块 + 向下箭头 | 每块一个 `<rect rx="6">`，块内 `<text>` 写步骤名，块之间画 `<line>` 并加箭头标记 |
| 两样东西的差别 | 等高两栏 | 两块 `<rect>` 并排，中间一条 `<line>`，差异项用同一颜色标出 |
| 数量或比例 | 横条形图，条形端点写数字 | 每项一条 `<rect width>`，宽度按数值算，`<text>` 标数值和单位 |
| 一部分占比 | 点阵网格 | 10×10 个 `<circle>`，按比例涂色，图注写"每个点表示 1%" |
| 谁包含谁 | 嵌套方框 | 外层 `<rect>`，内层偏左上的小 `<rect>`，标签写层级名 |
| 时间先后 | 横轴 + 刻度 | 一条 `<line>` 作轴，`<text>` 写时间，事件用小圆点加标签 |
| 原因和结果 | 左框 → 箭头 → 右框 | 两个 `<rect>`，中间 `<line>` 加箭头，箭头旁 `<text>` 写条件 |
| 变化前后 | 三格并排 | 三块 `<rect>`，依次写"原来""发生什么""现在"，变化处用强调色 |

图的统一写法：

```html
<figure>
  <svg viewBox="0 0 640 240" role="img" aria-labelledby="f1-title">
    <title id="f1-title">缓存让请求更快</title>
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto">
        <path d="M0 0 L10 5 L0 10 z" fill="currentColor"></path>
      </marker>
    </defs>
    <!-- 图形写在这里 -->
  </svg>
  <figcaption>请求先到缓存。</figcaption>
</figure>
```

约束：

- 每张图必须有 `<title>`（或 `aria-label`）。检查器按硬失败处理。
- 同一文件里 `id` 只出现一次。多张图用不同的 marker id。
- 用 `viewBox`，不写固定宽高。移动端和打印都要能看。
- 颜色只用 CSS 变量：`--ink`（文字）、`--bg`（底色）、`--accent`（强调）。同时在 `@media (prefers-color-scheme: dark)` 里给一套深色值。可直接抄 `docs/usage-guide.html` 顶部那段变量和深色覆盖。
- 图内文字用 `<text>`，字号不小于 13。不要用 emoji 当图。

## 页面骨架

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>读者能看懂的一句话标题</title>
<style>/* 变量、正文 16px/1.7、max-width 860px、图与表格样式 */</style>
</head>
<body>
<header><h1>标题</h1><p>一句话说明这份讲解回答什么问题</p></header>
<main>
  <section>
    <h2>第一节的结论</h2>
    <figure>…</figure>
    <p>最多 3 句。</p>
    <p><strong>记住这句：</strong>一句话。</p>
  </section>
</main>
<footer><p>本文只讲清了什么；哪些没讲。</p></footer>
</body>
</html>
```

每个 `<section>` 必须含至少一个图或表格。检查器按硬失败处理。

## 不做什么

- 不联网查资料。需要外部事实时，先让 `research` 阶段给出带来源的结论，再进入本技能。
- 不写 API 参考手册和代码说明。那是 `x-technical-writing` 的范围。
- 不做幻灯片和视频。本技能只产出一个可滚动的 HTML 文件。
- 不把长文档整篇搬进来。来源文档只用来提取"必须知道的 3 到 7 件事"。
- 不引用外部图片地址，不用 emoji 代替图。

## 自检与证据

检查器只报可机检的事：标签是否闭合、是否引用外部资源、每张图是否有名称、每个小节是否有图、句子是否过长、段落是否超过 3 句。

```bash
python3 <skill-dir>/scripts/check_html.py <file>.html          # 警告只提示
python3 <skill-dir>/scripts/check_html.py <file>.html --strict # 有警告就退出 1
```

退出码 0 表示没有硬失败。它不证明内容正确、图好看或读者真的看懂。把检查器输出存进 `evidence/`，交付时说明哪些要求没有机器检查（例如图解是否准确、类比是否恰当）。
