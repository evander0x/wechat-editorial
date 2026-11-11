#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
wechat_layout.py — 公众号排版模板（编辑手记 / editorial-teal）

把 Markdown 渲染成可直接粘贴进微信编辑器的 HTML：
全部内联样式、无外部字体、无脚本、无 <style> 依赖。

用法：
    python3 wechat_layout.py article.md -o article.html
    python3 wechat_layout.py article.md -o article.html --theme teal|ink|orange|yicai|deepseek

Markdown 约定（除标准语法外）：
    ---
    label: 职场观察 · 效率        # 可选，标题上方的栏目标签
    lead: 一句话导语               # 可选，标题下方的灰色引子
    ---
    # 标题
    ## 01 小节标题                 # 以数字开头 → 自动渲染成序号块
    ==需要高亮的句子==             # 浅色下划线高亮
    > 引用 / 示例                  # 淡底竖线引用块
    :::card 卡片标题               # 清单卡片开始
    1. 第一条
    2. 第二条
    :::                           # 卡片结束
    :::punch                      # 金句区开始（居中小节，上下细线）
    第一行（大字）
    第二行（灰色）
    :::
"""

import argparse
import html
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 设计变量

THEMES = {
    "teal": {
        "accent": "#0e7490",
        "accent_soft": "#f4f8f9",
        "accent_light": "#e6f4f6",
        "ink": "#171717",
        "text": "#333333",
        "muted": "#8b8b8b",
        "hairline": "#ececec",
        "card_bg": "#faf9f7",
        "card_border": "#ecebe6",
        "quote_text": "#3d4a4d",
    },
    "ink": {
        "accent": "#4a4a4a",
        "accent_soft": "#f5f2ec",
        "accent_light": "#ebe6dc",
        "ink": "#1a1a1a",
        "text": "#333333",
        "muted": "#8b8b8b",
        "hairline": "#e8e4dc",
        "card_bg": "#faf8f4",
        "card_border": "#eae5db",
        "quote_text": "#4a4a4a",
    },
    # 橙色科技流：参考「逛逛GitHub」的极简版式
    #   正文 17px / 行高 2em / 90% 黑 / 字间距 .034em / 两端对齐
    #   小标题 = 32px 橙色 Futura 编号 + 17px 常规标题
    #   强调只用加粗；无卡片、无分割线、无图注
    "orange": {
        "accent": "#ff6827",
        "accent_soft": "#fff4ef",
        "accent_light": "#ffe3d6",
        "ink": "#0d0d0d",
        "text": "rgba(0,0,0,0.9)",
        "muted": "#8b8b8b",
        "hairline": "#ececec",
        "card_bg": "#fafafa",
        "card_border": "#eeeeee",
        "quote_text": "#333333",
        "variant": "orange",
        "body_size": "17px",
        "body_lh": "2",
        "body_ls": "0.034em",
        "body_margin": "0 8px 16px",
        "font": "'PingFang SC',system-ui,-apple-system,'Helvetica Neue',"
        "'Hiragino Sans GB','Microsoft YaHei UI','Microsoft YaHei',Arial,sans-serif",
        "num_font": "Futura-Medium,Futura,'Helvetica Neue',Helvetica,Arial,sans-serif",
    },
    # 财经蓝快讯流：参考「第一财经」新闻推送版式
    #   正文 17px / 行高 1.75 / 90% 黑 / 字间距 1px / 两端对齐 / 左右 8px
    #   小标题 = 16px 财经蓝加粗独立成段，无底色无边框无序号块
    #   图注 12px 灰色；无卡片、无引用块、无分割线，纯段落极简流
    "yicai": {
        "accent": "#0098d6",
        "accent_soft": "#eef7fb",
        "accent_light": "#d9eff9",
        "ink": "#171717",
        "text": "rgba(0,0,0,0.9)",
        "muted": "#888888",
        "hairline": "#ececec",
        "card_bg": "#f7f7f7",
        "card_border": "#eeeeee",
        "quote_text": "#333333",
        "variant": "yicai",
        "body_size": "17px",
        "body_lh": "1.75",
        "body_ls": "1px",
        "body_margin": "0 8px 16px",
        "font": "'PingFang SC',system-ui,-apple-system,'Helvetica Neue',"
        "'Hiragino Sans GB','Microsoft YaHei UI','Microsoft YaHei',Arial,sans-serif",
    },
    # DeepSeek 蓝：参考「深度求索」官方公众号发布体版式
    #   正文 15px / 深灰 rgb(79,79,79) / 左右 8px、段后 16px / 默认左对齐
    #   小节标题 = 18px 加粗黑色独立成段，无序号块无底色无边框
    #   品牌蓝 #4d6bfe 只用于链接/地址行；图注 12px 灰色
    #   无卡片、无引用块、无分割线，纯段落极简流
    "deepseek": {
        "accent": "#4d6bfe",
        "accent_soft": "#f0f3ff",
        "accent_light": "#dfe6ff",
        "ink": "#0d0d0d",
        "text": "rgb(79,79,79)",
        "muted": "#888888",
        "hairline": "#ececec",
        "card_bg": "#f7f7f7",
        "card_border": "#eeeeee",
        "quote_text": "#4f4f4f",
        "variant": "deepseek",
        "body_size": "15px",
        "body_lh": "1.75",
        "body_ls": "0",
        "body_margin": "0 8px 16px",
        "font": "'PingFang SC NEW','PingFang SC',system-ui,-apple-system,'Helvetica Neue',"
        "'Hiragino Sans GB','Microsoft YaHei UI','Microsoft YaHei',Arial,sans-serif",
    },
}

# ---------------------------------------------------------------- 前置元数据


def split_front_matter(text: str):
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    raw = text[3:end]
    body = text[end + 4 :].lstrip("\n")
    meta = {}
    for line in raw.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, body


# ---------------------------------------------------------------- 行内标记


def inline(text: str, c: dict) -> str:
    t = html.escape(text, quote=False)

    def hl(m):
        if c.get("variant") in ("orange", "yicai", "deepseek"):
            # 这两种风格没有彩色高亮，强调只有加粗
            return '<strong style="font-weight:700;">%s</strong>' % m.group(1)
        return (
            '<span style="background:linear-gradient(to top,'
            + c["accent_light"]
            + " 40%,transparent 40%);font-weight:600;color:#111111;\">"
            + m.group(1)
            + "</span>"
        )

    t = re.sub(r"==(.+?)==", hl, t)
    t = re.sub(
        r"\*\*(.+?)\*\*",
        lambda m: '<strong style="font-weight:600;color:#111111;">%s</strong>' % m.group(1),
        t,
    )
    t = re.sub(
        r"`(.+?)`",
        lambda m: (
            '<code style="font-family:SFMono-Regular,Consolas,Menlo,monospace;'
            'font-size:13.5px;background:%s;color:%s;padding:2px 6px;border-radius:4px;">%s</code>'
            % (c["accent_soft"], c["accent"], m.group(1))
        ),
        t,
    )
    # 允许在标题/正文里手动换行
    t = t.replace("&lt;br&gt;", "<br>")
    return t


# ---------------------------------------------------------------- 块级渲染


def render_blocks(body: str, c: dict) -> str:
    lines = body.split("\n")
    out = []
    i = 0
    n = len(lines)

    def flush_paragraph(buf):
        if not buf:
            return
        text = " ".join(x.strip() for x in buf).strip()
        if text:
            if c.get("variant") in ("orange", "yicai", "deepseek"):
                align = "left" if c.get("variant") == "deepseek" else "justify"
                out.append(
                    '<p style="margin:%s; font-size:%s; line-height:%s; color:%s; '
                    'letter-spacing:%s; text-align:%s; font-family:%s;">%s</p>'
                    % (
                        c["body_margin"],
                        c["body_size"],
                        c["body_lh"],
                        c["text"],
                        c["body_ls"],
                        align,
                        c["font"],
                        inline(text, c),
                    )
                )
                return
            out.append(
                '<p style="margin:0 0 22px; font-size:16px; line-height:1.95; color:%s; '
                'letter-spacing:.4px; text-align:justify;">%s</p>' % (c["text"], inline(text, c))
            )

    para = []

    while i < n:
        raw = lines[i]
        line = raw.rstrip()
        stripped = line.strip()

        # 空行 → 结束当前段落
        if not stripped:
            flush_paragraph(para)
            para = []
            i += 1
            continue

        # 代码块：``` 围栏，原样保留缩进与换行（不走 inline 处理）
        if stripped.startswith("```"):
            flush_paragraph(para)
            para = []
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i].rstrip())
                i += 1
            i += 1  # 跳过结束围栏
            out.append(render_code("\n".join(buf), c))
            continue

        # 表格：| a | b | 表头 + |---|---| 分隔行
        if stripped.startswith("|") and i + 1 < n and re.match(
            r"^\|[\s:\-|]+\|$", lines[i + 1].strip()
        ):
            flush_paragraph(para)
            para = []
            rows = []
            while i < n and lines[i].strip().startswith("|"):
                cells = [x.strip() for x in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:\-]+$", "".join(cells)):
                    rows.append(cells)
                i += 1
            out.append(render_table(rows, c))
            continue

        # 围栏块
        if stripped.startswith(":::"):
            flush_paragraph(para)
            para = []
            head = stripped[3:].strip()
            kind = head.split()[0] if head else ""
            title = head[len(kind) :].strip()
            block = []
            i += 1
            while i < n and lines[i].strip() != ":::":
                block.append(lines[i].rstrip())
                i += 1
            i += 1  # 跳过结束标记

            if kind == "card":
                out.append(render_card(title, block, c))
            elif kind == "punch":
                out.append(render_punch(block, c))
            continue

        # 标题
        m = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m:
            flush_paragraph(para)
            para = []
            level = len(m.group(1))
            text = m.group(2).strip()
            if level == 1:
                out.append(
                    '<h1 style="margin:0 0 16px; font-size:26px; line-height:1.45; '
                    'font-weight:700; color:%s; letter-spacing:.6px;">%s</h1>'
                    % (c["ink"], inline(text, c))
                )
            else:
                out.append(render_h2(text, c))
            i += 1
            continue

        # 分隔线
        if re.match(r"^(-{3,}|\*{3,})$", stripped):
            flush_paragraph(para)
            para = []
            out.append(
                '<hr style="border:none;border-top:1px solid %s;margin:36px 0;">' % c["hairline"]
            )
            i += 1
            continue

        # 图片块：![说明](路径 "可选备注")  → 居中大图 + 灰色图注
        m = re.match(r'^!\[(.*?)\]\((\S+?)(?:\s+"(.*?)")?\)$', stripped)
        if m:
            flush_paragraph(para)
            para = []
            out.append(render_image(m.group(1), m.group(2), m.group(3), c))
            i += 1
            continue

        # 引用块
        if stripped.startswith(">"):
            flush_paragraph(para)
            para = []
            quote = []
            while i < n and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip()[1:].strip())
                i += 1
            text = " ".join(x for x in quote if x)
            out.append(
                '<section style="margin:0 0 24px; padding:18px 20px; background:%s; '
                'border-left:3px solid %s; border-radius:0 8px 8px 0;">'
                '<p style="margin:0; font-size:15px; line-height:1.9; color:%s; '
                'letter-spacing:.3px;">%s</p></section>'
                % (c["accent_soft"], c["accent"], c["quote_text"], inline(text, c))
            )
            continue

        # 列表
        if re.match(r"^([-*]|\d+\.)\s+", stripped):
            flush_paragraph(para)
            para = []
            items = []
            ordered = bool(re.match(r"^\d+\.\s+", stripped))
            while i < n and re.match(r"^([-*]|\d+\.)\s+", lines[i].strip()):
                items.append(re.sub(r"^([-*]|\d+\.)\s+", "", lines[i].strip()))
                i += 1
            out.append(render_list(items, ordered, c))
            continue

        # 地址：以「地址：」开头的行 → 地址栏 / 代码块（两种风格）
        if stripped.startswith("地址："):
            flush_paragraph(para)
            para = []
            addr = html.escape(stripped[len("地址："):].strip())
            if c.get("variant") == "deepseek":
                # DeepSeek 官方体：品牌蓝纯文本链接行，无底色
                out.append(
                    '<p style="margin:0 8px 16px; font-size:15px; line-height:1.75; '
                    'color:%s; word-break:break-all; font-family:%s;">%s</p>'
                    % (c["accent"], c["font"], addr)
                )
                i += 1
                continue
            if c.get("variant") in ("orange", "yicai", "deepseek"):
                # 参考风格：灰底等宽「代码块」，和正文同宽
                prefix = "开源地址：" if c.get("variant") == "orange" else ""
                out.append(
                    '<section style="margin:0 8px 16px; padding:14px 16px; background:#f7f7f7; '
                    'border-radius:6px;">'
                    '<p style="margin:0; font-size:15px; line-height:1.7; color:#333333; '
                    'font-family:SFMono-Regular,Consolas,Menlo,monospace; '
                    'letter-spacing:0; word-break:break-all;">%s%s</p></section>' % (prefix, addr)
                )
            else:
                out.append(
                    '<p style="margin:18px 0 26px;">'
                    '<span style="display:inline-block; padding:9px 16px; background:#1f2d33; '
                    'border-radius:8px; font-family:SFMono-Regular,Consolas,Menlo,monospace; '
                    'font-size:13px; letter-spacing:.2px;">'
                    '<span style="color:#62d9e8;">&#8599; </span>'
                    '<span style="color:#e6eef0;">%s</span></span></p>' % addr
                )
            i += 1
            continue

        para.append(stripped)
        i += 1

    flush_paragraph(para)
    return "\n".join(out)


def render_table(rows, c: dict) -> str:
    """Markdown 表格 → 全内联 <table>。微信会剥 class，所以样式必须写在标签上。"""
    if not rows:
        return ""
    header, body = rows[0], rows[1:]
    orange = c.get("variant") in ("orange", "yicai", "deepseek")
    head_bg = "transparent" if orange else c["accent_soft"]
    head_color = c["accent"] if orange else c["ink"]
    border = "#eeeeee" if orange else "#e7ecec"
    size = "14px" if orange else "13.5px"
    out = [
        '<section style="margin:0 0 26px; overflow-x:auto;">',
        '<table style="width:100%%; border-collapse:collapse; font-size:%s; line-height:1.7; '
        'color:%s;">' % (size, c["text"]),
        '<thead><tr style="background:%s;">' % head_bg,
    ]
    ncol = max(1, len(header))
    # 首列通常是短标签，给窄一点；其余平分，避免手机端列宽失衡
    if ncol == 1:
        widths = ["100%"]
    else:
        rest = round(74.0 / (ncol - 1), 1)
        widths = ["26%"] + ["%s%%" % rest] * (ncol - 1)
    for idx, cell in enumerate(header):
        out.append(
            '<th style="width:%s; padding:10px 8px; text-align:left; font-weight:600; color:%s; '
            'border-bottom:1px solid %s;">%s</th>'
            % (widths[idx], head_color, border, inline(cell, c))
        )
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>")
        for cell in row:
            out.append(
                '<td style="padding:10px 8px; vertical-align:top; '
                'border-bottom:1px solid %s;">%s</td>' % (border, inline(cell, c))
            )
        out.append("</tr>")
    out.append("</tbody></table></section>")
    return "".join(out)


def render_code(text: str, c: dict) -> str:
    """代码块：灰底 + 等宽字体，保留原始缩进。样式全内联，不用 <style>。"""
    body = html.escape(text)
    if c.get("variant") in ("orange", "yicai", "deepseek"):
        bg, border, code_color, size, radius = (
            "#f7f7f7",
            "1px solid #f0f0f0",
            "rgba(0,0,0,0.82)",
            "14px",
            "8px",
        )
        pad, margin, lh = "16px 18px", "24px 8px 28px", "1.9"
    else:
        bg, border, code_color, size, radius = (
            "#f6f8f9",
            "1px solid #e3ecef",
            "#2b3a40",
            "13px",
            "8px",
        )
        pad, margin, lh = "16px 18px", "0 0 24px", "1.85"
    return (
        '<section style="margin:%s; padding:%s; background:%s; border:%s; '
        'border-radius:%s; overflow-x:auto;">'
        '<pre style="margin:0; font-family:SFMono-Regular,Consolas,Menlo,\'Courier New\',monospace; '
        'font-size:%s; line-height:%s; color:%s; white-space:pre-wrap; word-break:break-word; '
        'letter-spacing:0;">%s</pre></section>'
        % (margin, pad, bg, border, radius, size, lh, code_color, body)
    )


def render_image(alt: str, src: str, note: str, c: dict) -> str:
    if c.get("variant") in ("yicai", "deepseek"):
        # 财经蓝/DeepSeek：满宽居中无修饰，图注 12px 灰色小字（原版规格）
        ls = "1px" if c.get("variant") == "yicai" else "0"
        parts = [
            '<img src="%s" alt="%s" style="max-width:100%%; height:auto; display:block; '
            'margin:24px auto 6px;">' % (html.escape(src), html.escape(alt))
        ]
        caption = note or alt
        if caption:
            parts.append(
                '<p style="text-align:center; font-size:12px; color:#888888; letter-spacing:%s; '
                'margin:0 8px 20px;">%s</p>' % (ls, html.escape(caption))
            )
        return "".join(parts)
    if c.get("variant") == "orange":
        # 参考风格：满宽居中 + 细边框小圆角；有标注时渲染 12.5px 居中灰字，无则不加图注
        parts = [
            '<section style="text-align:center; margin:28px 8px;">'
            '<img src="%s" alt="%s" style="max-width:100%%; height:auto; display:block; '
            'margin:0 auto; border:1px solid #ffe3d6; border-radius:6px;">' % (html.escape(src), html.escape(alt))
        ]
        caption = note or alt
        if caption:
            parts.append(
                '<p style="text-align:center; font-size:12.5px; line-height:1.7; color:#9a9a9a; '
                'letter-spacing:.5px; margin:10px 0 0;">%s</p>' % html.escape(caption)
            )
        parts.append("</section>")
        return "".join(parts)
    parts = [
        '<img src="%s" alt="%s" style="max-width:100%%; height:auto; display:block; '
        'margin:30px auto 8px; border-radius:8px;">' % (html.escape(src), html.escape(alt))
    ]
    caption = note or alt
    if caption:
        parts.append(
            '<p style="text-align:center; font-size:13px; color:#9a9a9a; letter-spacing:.4px; '
            'margin:0 0 28px;">%s</p>' % html.escape(caption)
        )
    return "".join(parts)


def render_h2(text: str, c: dict) -> str:
    m = re.match(r"^(\d{1,2})[\s　.、]*(.*)$", text)
    if c.get("variant") == "deepseek":
        # DeepSeek 官方体：18px 加粗黑色独立成段，无序号块无底色，不强调编号
        return (
            '<p style="margin:24px 8px 12px; font-size:18px; line-height:1.75; color:%s; '
            'font-weight:bold; letter-spacing:0; font-family:%s;">%s</p>'
            % (c["ink"], c["font"], inline(text, c))
        )
    if c.get("variant") == "yicai":
        # 财经蓝：16px 蓝色加粗独立成段，无序号块无底色，还原原版小节标题
        return (
            '<p style="margin:28px 8px 10px; font-size:16px; line-height:1.75; color:%s; '
            'font-weight:bold; letter-spacing:1px; font-family:%s;">%s</p>'
            % (c["accent"], c["font"], inline(text, c))
        )
    if c.get("variant") == "orange":
        # 32px 橙色 Futura 编号 + 17px 加粗标题，同一行，无底色无边框
        if m:
            num, title = m.group(1), m.group(2)
            return (
                '<p style="margin:24px 8px 0px; font-size:%s; line-height:%s; color:%s; '
                'letter-spacing:%s; text-align:justify; font-family:%s;">'
                '<span style="color:%s; font-family:%s; font-size:32px; font-weight:700; '
                'letter-spacing:1px;">%s</span> '
                '<span style="font-size:%s; font-weight:600; color:#171717;">%s</span></p>'
                % (
                    c["body_size"],
                    c["body_lh"],
                    c["text"],
                    c["body_ls"],
                    c["font"],
                    c["accent"],
                    c["num_font"],
                    num,
                    c["body_size"],
                    inline(title, c),
                )
            )
        return (
            '<p style="margin:24px 8px 0px; font-size:%s; line-height:%s; color:#171717; '
            'font-weight:600; letter-spacing:%s; font-family:%s;">%s</p>'
            % (c["body_size"], c["body_lh"], c["body_ls"], c["font"], inline(text, c))
        )

    if m:
        num, title = m.group(1), m.group(2)
        badge = (
            '<span style="display:inline-block; width:30px; height:30px; line-height:30px; '
            'text-align:center; background:%s; color:#ffffff; font-size:13px; font-weight:700; '
            'border-radius:8px; vertical-align:middle; margin-right:10px;">%s</span>'
            % (c["accent"], num)
        )
    else:
        badge = ""
        title = text
    return (
        '<section style="margin:38px 0 16px;">%s'
        '<span style="font-size:18px; font-weight:700; color:%s; letter-spacing:.5px; '
        'vertical-align:middle;">%s</span></section>'
        % (badge, c["ink"], inline(title, c))
    )


def render_list(items, ordered: bool, c: dict) -> str:
    if c.get("variant") in ("orange", "yicai", "deepseek"):
        rows = []
        for idx, item in enumerate(items, 1):
            mark = (
                '<span style="color:%s; font-weight:700;">%d</span>' % (c["accent"], idx)
                if ordered
                else '<span style="color:%s; font-weight:700;">·</span>' % c["accent"]
            )
            rows.append(
                '<p style="margin:%s; font-size:%s; line-height:%s; color:%s; '
                'letter-spacing:%s; text-align:justify; font-family:%s;">%s %s</p>'
                % (
                    c["body_margin"],
                    c["body_size"],
                    c["body_lh"],
                    c["text"],
                    c["body_ls"],
                    c["font"],
                    mark,
                    inline(item, c),
                )
            )
        return "".join(rows)

    rows = []
    for idx, item in enumerate(items, 1):
        mark = (
            '<span style="color:%s; font-weight:700; margin-right:8px;">%d</span>'
            % (c["accent"], idx)
            if ordered
            else '<span style="color:%s; font-weight:700; margin-right:8px;">·</span>' % c["accent"]
        )
        rows.append(
            '<p style="margin:0 0 14px; font-size:15px; line-height:1.85; color:#3a3a3a; '
            'letter-spacing:.3px;">%s%s</p>' % (mark, inline(item, c))
        )
    return '<section style="margin:0 0 30px;">%s</section>' % "".join(rows)


def render_card(title: str, block, c: dict) -> str:
    if c.get("variant") in ("orange", "yicai", "deepseek"):
        # 这两种风格没有卡片容器：标题加粗 + 纯段落，保持页面干净
        items = [b.strip() for b in block if b.strip()]
        parts = []
        if title:
            parts.append(
                '<p style="margin:24px 8px 8px; font-size:%s; line-height:%s; '
                'font-weight:700; color:%s; font-family:%s;">%s</p>'
                % (c["body_size"], c["body_lh"], c["ink"], c["font"], html.escape(title))
            )
        for item in items:
            m = re.match(r"^(\d+)[.、]\s*(.*)$", item)
            body = m.group(2) if m else item
            num = (
                '<span style="color:%s; font-weight:700;">%s</span> '
                % (c["accent"], m.group(1))
                if m
                else ""
            )
            parts.append(
                '<p style="margin:%s; font-size:%s; line-height:%s; color:%s; '
                'letter-spacing:%s; text-align:justify; font-family:%s;">%s%s</p>'
                % (
                    c["body_margin"],
                    c["body_size"],
                    c["body_lh"],
                    c["text"],
                    c["body_ls"],
                    c["font"],
                    num,
                    inline(body, c),
                )
            )
        return "".join(parts)

    items = [b.strip() for b in block if b.strip()]
    rows = []
    for item in items:
        m = re.match(r"^(\d+)[.、]\s*(.*)$", item)
        if m:
            rows.append(
                '<p style="margin:0 0 14px; font-size:15px; line-height:1.85; color:#3a3a3a; '
                'letter-spacing:.3px;"><span style="color:%s; font-weight:700; margin-right:8px;">'
                "%s</span>%s</p>" % (c["accent"], m.group(1), inline(m.group(2), c))
            )
        else:
            rows.append(
                '<p style="margin:0 0 14px; font-size:15px; line-height:1.85; color:#3a3a3a; '
                'letter-spacing:.3px;">%s</p>' % inline(item, c)
            )
    head = (
        '<p style="margin:0 0 16px; font-size:14px; font-weight:700; color:%s; '
        'letter-spacing:1.5px;">%s</p>' % (c["accent"], html.escape(title))
        if title
        else ""
    )
    return (
        '<section style="margin:0 0 34px; padding:22px 20px 8px; background:%s; '
        'border:1px solid %s; border-radius:14px;">%s%s</section>'
        % (c["card_bg"], c["card_border"], head, "".join(rows))
    )


def render_punch(block, c: dict) -> str:
    lines = [b.strip() for b in block if b.strip()]

    if c.get("variant") in ("orange", "yicai", "deepseek"):
        # 这两种风格没有金句框：居中加粗 + 常规副行，靠留白分隔
        parts = []
        for idx, line in enumerate(lines):
            if idx == 0:
                parts.append(
                    '<p style="margin:0 8px 8px; text-align:center; font-size:19px; '
                    'line-height:%s; font-weight:700; color:%s; font-family:%s;">%s</p>'
                    % (c["body_lh"], c["ink"], c["font"], inline(line, c))
                )
            else:
                parts.append(
                    '<p style="margin:0 8px 16px; text-align:center; font-size:%s; '
                    'line-height:%s; color:#666666; font-family:%s;">%s</p>'
                    % (c["body_size"], c["body_lh"], c["font"], inline(line, c))
                )
        return '<section style="margin:28px 0;">%s</section>' % "".join(parts)

    parts = []
    for idx, line in enumerate(lines):
        if idx == 0:
            parts.append(
                '<p style="margin:0 0 8px; font-size:17px; line-height:2; color:%s; '
                'font-weight:600; letter-spacing:.5px;">%s</p>' % (c["ink"], inline(line, c))
            )
        else:
            parts.append(
                '<p style="margin:0; font-size:15px; line-height:2; color:#6b7280; '
                'letter-spacing:.4px;">%s</p>' % inline(line, c)
            )
    return (
        '<section style="margin:0 0 30px; padding:26px 8px; border-top:1px solid %s; '
        'border-bottom:1px solid %s; text-align:center;">%s</section>'
        % (c["hairline"], c["hairline"], "".join(parts))
    )


# ---------------------------------------------------------------- 组装页面


def render_article(md_text: str, theme: str = "teal", include_header: bool = True) -> tuple:
    """渲染正文片段（不含页面外壳）。返回 (title, article_html)。

    include_header=False 时省略栏目标签和大标题（公众号编辑器里标题单独填，
    正文再出现一遍是重复的）；导语保留，属于正文内容。
    """
    c = THEMES.get(theme, THEMES["teal"])
    meta, body = split_front_matter(md_text)

    label = meta.get("label", "").strip()
    lead = meta.get("lead", "").strip()

    head = []
    if label and include_header:
        head.append(
            '<section style="margin:0 0 18px;">'
            '<span style="display:inline-block; width:18px; height:2px; background:%s; '
            'vertical-align:middle; margin-right:8px;"></span>'
            '<span style="font-size:11px; letter-spacing:2.5px; color:%s; font-weight:600;">%s</span>'
            "</section>" % (c["accent"], c["accent"], html.escape(label))
        )

    if lead:
        if c.get("variant") in ("orange", "yicai", "deepseek"):
            lead_html = (
                '<p style="margin:0 8px 16px; font-size:15px; line-height:%s; color:%s; '
                'letter-spacing:%s; text-align:justify; font-family:%s;">%s</p>'
                % (c["body_lh"], c["muted"], c["body_ls"], c["font"], inline(lead, c))
            )
        else:
            lead_html = (
                '<section style="margin:0 0 30px; padding:0 0 0 14px; border-left:2px solid #e5e5e5;">'
                '<p style="margin:0; font-size:14px; line-height:1.9; color:%s; letter-spacing:.4px;">'
                "%s</p></section>" % (c["muted"], inline(lead, c))
            )
    else:
        lead_html = ""

    inner = render_blocks(body, c)

    # 标题单独抽出，顺序固定为：栏目标签 → 标题 → 导语 → 正文
    h1_match = re.search(r"<h1[^>]*>.*?</h1>", inner, re.S)
    if h1_match:
        h1_html = h1_match.group(0)
        inner = inner.replace(h1_html, "", 1)
    else:
        h1_html = ""

    article = "\n".join(
        [x for x in head + ([h1_html] if include_header else []) + [lead_html] if x]
    ).strip() + "\n" + inner

    return meta.get("title", "公众号文章"), article


def embed_local_images(article: str, base_dir: Path) -> str:
    """预览用：把本地图片内联成 data URI，避免预览面板里图片 404。

    推草稿箱时不用这个函数——微信需要的是上传后返回的 URL。
    """
    import base64
    import mimetypes

    def repl(m):
        src = m.group(1)
        if src.startswith(("http://", "https://", "data:")):
            return m.group(0)
        p = Path(src) if Path(src).is_absolute() else base_dir / src
        if not p.exists():
            return m.group(0)
        mime = mimetypes.guess_type(str(p))[0] or "image/png"
        b64 = base64.b64encode(p.read_bytes()).decode()
        return m.group(0).replace(src, f"data:{mime};base64,{b64}")

    return re.sub(r'<img[^>]+src="([^"]+)"', repl, article)


def build(md_text: str, theme: str = "teal") -> str:
    title, article = render_article(md_text, theme)
    article = embed_local_images(article, Path.cwd())

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
</head>
<body style="margin:0; padding:32px 16px 64px; background:#eceae6; font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif;">
<section style="max-width:420px; margin:0 auto 18px; font-size:12px; line-height:1.7; color:#8a8578; letter-spacing:.3px;">↑ 下方白色卡片内即正文，全选复制粘贴进公众号编辑器即可保留样式。</section>
<section style="max-width:420px; margin:0 auto; background:#ffffff; border-radius:14px; overflow:hidden;">
<section style="padding:34px 24px 40px; background:#ffffff;">
{article}
</section>
</section>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(description="Markdown → 微信兼容 HTML（编辑手记模板）")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--theme", default="teal", choices=list(THEMES))
    ap.add_argument(
        "--fragment",
        action="store_true",
        help="只输出正文片段（不含页面外壳），供推草稿箱等程序使用",
    )
    args = ap.parse_args()

    md = Path(args.input).read_text(encoding="utf-8")
    if args.fragment:
        _, article = render_article(md, args.theme, include_header=False)
        Path(args.output).write_text(article, encoding="utf-8")
    else:
        Path(args.output).write_text(build(md, args.theme), encoding="utf-8")
    print(f"OK → {args.output}")


if __name__ == "__main__":
    main()
