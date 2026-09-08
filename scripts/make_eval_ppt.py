#!/usr/bin/env python3
"""把「地端模型可用性評估」產成公司格式（統一資訊）的 PPTX。

報告主軸是**地端模型能不能用**，不是五個模型的通用比較；雲端三臂的角色是基準線，
用來回答「地端離雲端還差多少」。

格式來源：`711_Store_效能測試報告_20260831_統一資訊格式_場景合併.pptx`，
用它當底稿（保留佈景主題、標題頁 logo、表格樣式），清掉原有投影片後重建。

版面規則（從底稿量出來的，不要自己改）：
- 16:9，13.33 x 7.5 in
- 主色 #00508E、輔色 #ED6C00、卡片底 #EFEFEF、內文 #3C3C3C / #666666 / #999999
- 內容頁標題 (0.92, 0.35) 32pt 粗體；左側藍橘方塊 + 標題下橘藍雙色底線 + 右上平行四邊形
- 內容區 x 0.58–12.40、y 1.45–6.50

用法：
  cd apps/backend && uv run python ../../scripts/make_eval_ppt.py \\
      --template "/mnt/c/Users/P10359945/Downloads/711_Store_效能測試報告_20260831_統一資訊格式_場景合併.pptx" \\
      --out "/mnt/c/Users/P10359945/Downloads/雲端地端模型評測報告_20260908.pptx"
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

BLUE = RGBColor(0x00, 0x50, 0x8E)
ORANGE = RGBColor(0xED, 0x6C, 0x00)
CARD = RGBColor(0xEF, 0xEF, 0xEF)
INK = RGBColor(0x3C, 0x3C, 0x3C)
BODY = RGBColor(0x66, 0x66, 0x66)
MUTED = RGBColor(0x99, 0x99, 0x99)
RED = RGBColor(0xEF, 0x53, 0x50)
AMBER = RGBColor(0xFF, 0xA7, 0x26)
GREEN = RGBColor(0x43, 0xA0, 0x47)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "微軟正黑體"

TABLE_STYLE_ID = "{5C22544A-7EE6-4342-B048-85BDC9FD1C3A}"


# ── 基礎工具 ────────────────────────────────────────────────────────────────

def clear_slides(prs) -> None:
    """清掉底稿原有投影片，只留佈景主題與版面配置。"""
    xml_slides = prs.slides._sldIdLst
    for sld in list(xml_slides):
        rId = sld.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        prs.part.drop_rel(rId)
        xml_slides.remove(sld)


def box(slide, x, y, w, h, *, shape=MSO_SHAPE.RECTANGLE, fill=None, radius=None):
    sh = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.line.fill.background()
    sh.shadow.inherit = False
    if fill is None:
        sh.fill.background()
    else:
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        sh.adjustments[0] = radius
    if sh.has_text_frame:
        sh.text_frame.text = ""
    return sh


def text(slide, x, y, w, h, lines, *, size=10, color=BODY, bold=False,
         align=PP_ALIGN.LEFT, spacing=1.15, anchor=MSO_ANCHOR.TOP):
    """lines 可為字串或 (文字, 覆寫屬性dict) 的串列。"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    items = lines if isinstance(lines, list) else [lines]
    for i, item in enumerate(items):
        s, over = item if isinstance(item, tuple) else (item, {})
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = over.get("align", align)
        p.line_spacing = over.get("spacing", spacing)
        if over.get("space_before"):
            p.space_before = Pt(over["space_before"])
        r = p.add_run()
        r.text = s
        r.font.name = FONT
        r.font.size = Pt(over.get("size", size))
        r.font.bold = over.get("bold", bold)
        r.font.color.rgb = over.get("color", color)
    return tb


def content_slide(prs, title: str):
    """內容頁：套 1_標題 版面 + 補上底稿的裝飾件與標題。"""
    layout = {lay.name: lay for lay in prs.slide_layouts}["1_標題"]
    s = prs.slides.add_slide(layout)

    ph = s.shapes.title
    ph.left, ph.top = Inches(0.92), Inches(0.35)
    ph.width, ph.height = Inches(11.5), Inches(0.8)
    tf = ph.text_frame
    tf.text = title
    para = tf.paragraphs[0]
    para.alignment = PP_ALIGN.LEFT          # 版面配置預設靠右，會撞到右上裝飾
    r = para.runs[0]
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(32), True, BLUE

    box(s, 0.58, 0.44, 0.14, 0.62, fill=BLUE)        # 左側藍塊
    box(s, 0.58, 0.94, 0.14, 0.12, fill=ORANGE)      # 左側橘塊
    box(s, 12.30, 0.30, 0.72, 0.42, shape=MSO_SHAPE.PARALLELOGRAM, fill=BLUE)
    box(s, 12.78, 0.52, 0.48, 0.30, shape=MSO_SHAPE.PARALLELOGRAM, fill=ORANGE)
    box(s, 0.92, 1.26, 1.15, 0.06, fill=ORANGE)      # 標題下橘線
    box(s, 2.17, 1.28, 10.25, 0.03, fill=BLUE)       # 標題下藍線

    # 頁尾不自己畫：版面配置已附公司版權列與頁碼
    return s


def table(slide, rows, x, y, w, h, col_w, *, head_size=11, body_size=10.5,
          row_h=0.34, emphasis=None):
    """rows[0] 為表頭。emphasis: {列索引: RGBColor} 讓整列文字換色。"""
    gt = slide.shapes.add_table(len(rows), len(rows[0]),
                                Inches(x), Inches(y), Inches(w), Inches(h))
    t = gt.table
    t._tbl.find(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}tblPr"
    ).find(
        "{http://schemas.openxmlformats.org/drawingml/2006/main}tableStyleId"
    ).text = TABLE_STYLE_ID
    for i, cw in enumerate(col_w):
        t.columns[i].width = Inches(cw)
    for ri, row in enumerate(rows):
        t.rows[ri].height = Inches(row_h if ri else row_h + 0.06)
        for ci, val in enumerate(row):
            cell = t.cell(ri, ci)
            cell.margin_left = cell.margin_right = Inches(0.08)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if ci == 0 else PP_ALIGN.CENTER
            r = p.add_run()
            r.text = str(val)
            r.font.name = FONT
            r.font.size = Pt(head_size if ri == 0 else body_size)
            r.font.bold = ri == 0
            if ri == 0:
                r.font.color.rgb = WHITE
            else:
                r.font.color.rgb = (emphasis or {}).get(ri, INK)
    return t


def card(slide, x, y, w, h, heading, lines, *, heading_color=BLUE,
         heading_size=12.5, body_size=9.5):
    box(slide, x, y, w, h, shape=MSO_SHAPE.ROUNDED_RECTANGLE, fill=CARD, radius=0.06)
    text(slide, x + 0.17, y + 0.13, w - 0.34, 0.30, heading,
         size=heading_size, color=heading_color, bold=True)
    text(slide, x + 0.17, y + 0.52, w - 0.34, h - 0.65, lines,
         size=body_size, color=BODY, spacing=1.35)


def metric(slide, x, y, w, label, value, *, value_color=BLUE, h=0.86):
    box(slide, x, y, w, h, shape=MSO_SHAPE.ROUNDED_RECTANGLE, fill=CARD, radius=0.1)
    text(slide, x, y + 0.09, w, 0.24, label, size=8.5, color=MUTED,
         align=PP_ALIGN.CENTER)
    text(slide, x, y + 0.36, w, 0.42, value, size=16, color=value_color,
         bold=True, align=PP_ALIGN.CENTER)


def bullets(slide, x, y, w, h, items, *, size=11, gap=0.46, dot=ORANGE):
    """項目符號用小方塊，跟底稿的視覺語彙一致。"""
    for i, (lead, rest) in enumerate(items):
        yy = y + i * gap
        box(slide, x, yy + 0.09, 0.09, 0.09, fill=dot)
        text(slide, x + 0.22, yy, w - 0.22, gap,
             [(lead, {"bold": True, "color": INK}), (rest, {"color": BODY})]
             if rest else [(lead, {"bold": True, "color": INK})],
             size=size, spacing=1.2)


# ── 各頁內容 ────────────────────────────────────────────────────────────────

def slide_title(prs):
    layout = {lay.name: lay for lay in prs.slide_layouts}["標題投影片"]
    s = prs.slides.add_slide(layout)
    for ph in list(s.placeholders):
        if ph.placeholder_format.idx not in (0, 1):
            ph._element.getparent().remove(ph._element)

    t = s.shapes.title
    t.left, t.top, t.width, t.height = (
        Inches(1.67), Inches(1.78), Inches(10.0), Inches(1.3)
    )
    tf = t.text_frame
    tf.text = "地端大型語言模型可用性評估"
    r = tf.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(36), True, BLUE

    sub = s.placeholders[1]
    sub.left, sub.top, sub.width, sub.height = (
        Inches(1.67), Inches(3.15), Inches(10.0), Inches(1.0)
    )
    stf = sub.text_frame
    stf.text = "客服 RAG 平台 — 地端模型能不能取代雲端？"
    r = stf.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.color.rgb = FONT, Pt(20), INK
    p2 = stf.add_paragraph()
    r2 = p2.add_run()
    r2.text = "地端 2 款 vs 雲端 3 款基準線・92 輪題目・3 次重跑・300 則盲評  |  2026-09-08"
    r2.font.name, r2.font.size, r2.font.color.rgb = FONT, Pt(13), MUTED

    box(s, 10.40, 2.80, 2.60, 2.20, shape=MSO_SHAPE.CHEVRON, fill=BLUE)
    box(s, 11.60, 3.90, 1.60, 1.35, shape=MSO_SHAPE.CHEVRON, fill=ORANGE)

    cards = [
        ("受測地端模型", "Qwen 兩款"),
        ("雲端基準線", "GPT・Gemini"),
        ("驗收門檻", "4 項"),
        ("結論", "有條件可用"),
    ]
    for i, (label, value) in enumerate(cards):
        x = 1.42 + i * 2.70
        box(s, x, 5.30, 2.40, 1.10, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
            fill=CARD, radius=0.08)
        text(s, x, 5.42, 2.40, 0.28, label, size=9, color=MUTED,
             align=PP_ALIGN.CENTER)
        text(s, x, 5.76, 2.40, 0.42, value, size=14, color=BLUE, bold=True,
             align=PP_ALIGN.CENTER)
    return s


def slide_verdict(prs):
    s = content_slide(prs, "結論：地端可用，但只有一款、而且要加護欄")
    rows = [
        ["驗收門檻", "標準", "qwen3.6-35b-a3b", "qwen3.8-27b", "雲端基準線"],
        ["回應速度", "不明顯劣於雲端", "2.20 秒　通過", "5.50 秒　未通過", "1.77–1.80 秒"],
        ["答題品質", "接近雲端水準", "5.62　勉強通過", "5.65　勉強通過", "5.70–5.85"],
        ["工具呼叫", "不低於雲端", "97%　優於雲端", "83%　未通過", "87–93%"],
        ["結構化輸出", "契約 100% 遵守", "100%　通過", "100%　通過", "100%"],
    ]
    table(s, rows, 0.92, 1.50, 11.48, 1.95, [2.05, 2.35, 2.60, 2.28, 2.20],
          head_size=10.5, body_size=10.5, row_h=0.36)

    card(s, 0.92, 3.72, 5.60, 1.28, "qwen3.6-35b-a3b（MoE）　可用", [
        "四道門檻過三道，工具呼叫甚至優於全部雲端模型。",
        "唯一的缺口在難題的清單與計數 —— 可用護欄補，不必換模型。",
    ], heading_color=GREEN, heading_size=13, body_size=10)
    card(s, 6.80, 3.72, 5.60, 1.28, "qwen3.8-27b（dense）　不可用", [
        "回應 5.5 秒是雲端的 3 倍，客服場景直接出局。",
        "而且品質沒有因此換到 —— 工具選對率 83% 是全場最低。",
    ], heading_color=RED, heading_size=13, body_size=10)

    box(s, 0.92, 5.35, 11.48, 1.20, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.52, 11.0, 0.30, "給決策的一句話", size=12, color=BLUE, bold=True)
    text(s, 1.15, 5.90, 11.0, 0.55,
         "要資料不出境的案子，現在就可以用 qwen3.6-35b-a3b 提案 —— 前提是清單與計數類問題走結構化路徑、"
         "提示收緊、上線初期人工抽檢難題。不要求資料落地的案子，雲端仍然更省事也更便宜。",
         size=10.5, color=INK)
    return s


def slide_why(prs):
    s = content_slide(prs, "為什麼要評估地端")
    for i, (h, lines, col) in enumerate([
        ("資料不出境", [
            "金融、製造、公部門客戶要求資料不離開內網。",
            "這是雲端方案直接出局的場景 —— 不是價格問題，是能不能投標的問題。",
        ], BLUE),
        ("供應商風險", [
            "Gemini 3.8 Flash 2027 年起牌價翻倍。",
            "手上有可切換的地端選項，才有議價空間與退路。",
        ], BLUE),
        ("延遲可控", [
            "雲端延遲取決於對方的服務水準與網路。",
            "地端是自己的機器，尖峰行為可預測。",
        ], BLUE),
    ]):
        card(s, 0.92 + i * 3.90, 1.50, 3.66, 1.85, h, lines,
             heading_color=col, heading_size=13, body_size=10)

    box(s, 0.92, 3.62, 11.48, 1.28, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.20, 3.78, 10.9, 0.32, "地端不是為了省錢 —— 這點要先講清楚",
         size=13, color=ORANGE, bold=True)
    text(s, 1.20, 4.20, 10.9, 0.60,
         "地端是固定月費（RTX PRO 6000 級約 US$1,500／月、L40S 級約 US$720／月），雲端是每輪計價。\n"
         "以雲端最便宜的 luna 每輪 US$0.0017 換算，月流量要超過約 40–90 萬輪對話，地端才划算。POC 流量下地端更貴。",
         size=10.5, color=INK, spacing=1.35)

    text(s, 0.92, 5.10, 11.48, 0.30, "所以這次要回答的是一個是非題",
         size=13, color=BLUE, bold=True)
    box(s, 0.92, 5.52, 11.48, 1.05, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.20, 5.72, 10.9, 0.70,
         [("在同一條客服管線上，地端模型的品質、延遲、工具與結構化輸出，"
           "能不能撐到「可以拿出去提案」的水準？", {"bold": True, "color": INK, "size": 13}),
          ("如果可以，缺口在哪、要補什麼。", {"color": BODY, "size": 11, "space_before": 6})],
         spacing=1.3)
    return s


def slide_method(prs):
    s = content_slide(prs, "怎麼驗證「可用」")
    text(s, 0.92, 1.48, 11.48, 0.32,
         "地端 2 款與雲端 3 款接在同一條管線上：同一份知識庫、同一組系統提示、同一個檢索與防護設定，"
         "推理強度全部設為最低。唯一的變因是模型本身 —— 雲端三款的角色是基準線，不是競爭對手。",
         size=11, color=BODY)

    rows = [
        ["驗收門檻", "用什麼題組驗", "規模", "為什麼這個門檻重要"],
        ["答題品質", "問答 60 輪（簡 24／中 24／難 12），標準答案可回溯知識庫原文",
         "60 × 3 × 5", "答錯或編造，客服場景不能上線"],
        ["工具呼叫", "轉真人、查 DM 圖卡、不該叫工具、多工具串接、邊界情境",
         "20 × 3 × 5", "叫錯工具＝誤發真人工單或漏轉接"],
        ["結構化輸出", "命中／未命中／干擾三類，固定 schema",
         "12 × 3 × 5", "3D 展與 API 整合都依賴 JSON 契約"],
        ["回應速度", "以上三組全部量測首字與總時間",
         "1,380 次對話", "客服體驗的硬門檻"],
    ]
    table(s, rows, 0.92, 1.95, 11.48, 1.95, [1.60, 5.00, 1.55, 3.33], row_h=0.40)

    card(s, 0.92, 4.20, 5.60, 1.55, "品質為什麼要用盲評", [
        "機械指標量不到「答得好不好」，只能抓大異常。",
        "由完全不知道答案來源的獨立評審，對 300 則回答依三個維度各給 0–2 分。",
    ], heading_size=12, body_size=9.5)
    card(s, 6.80, 4.20, 5.60, 1.55, "盲評如何確保無偏", [
        "評審在專案外環境作業，看不到模型名稱、延遲、來源檔案。",
        "代號每輪重新洗牌；三次重跑分層抽樣各取 20 輪，避免單次手氣影響結論。",
    ], heading_size=12, body_size=9.5)

    text(s, 0.92, 5.92, 11.48, 0.55,
         [("題目全部從既有客服資料抽取，不為地端模型量身訂做。",
           {"bold": True, "color": INK}),
          ("8 個知識庫內資料互相矛盾的商品事先排除，避免答案無法判定對錯。", {})],
         size=10.5, color=BODY)
    return s


def slide_quality(prs):
    s = content_slide(prs, "門檻一：答題品質 — 勉強通過")
    rows = [
        ["", "模型", "正確性", "忠實度", "格式", "總分／6"],
        ["雲端基準", "gpt-5.6-terra", "1.92", "1.93", "2.00", "5.85"],
        ["雲端基準", "gpt-5.6-luna", "1.92", "1.92", "2.00", "5.83"],
        ["雲端基準", "gemini-3.8-flash", "1.97", "1.82", "1.92", "5.70"],
        ["地端", "qwen3.8-27b", "1.90", "1.83", "1.92", "5.65"],
        ["地端", "qwen3.6-35b-a3b", "1.85", "1.82", "1.95", "5.62"],
    ]
    table(s, rows, 0.92, 1.50, 6.90, 2.25, [1.05, 2.15, 0.90, 0.90, 0.90, 1.00],
          head_size=10, body_size=10, row_h=0.32)

    card(s, 8.10, 1.50, 4.30, 2.25, "地端只差 0.08–0.23 分，但別被平均值騙了", [
        "60 輪裡有 34 輪五臂全部滿分 —— 簡單題大家都會。",
        "只看 26 輪有鑑別力的題目，差距放大：",
        "雲端 5.65／5.62　vs　地端 5.19／5.12。",
    ], heading_size=11.5, body_size=9.5)

    text(s, 0.92, 4.02, 11.48, 0.30, "缺口集中在難題，而且錯法跟雲端不一樣",
         size=13, color=BLUE, bold=True)
    rows2 = [
        ["", "簡單題正確性", "中等題正確性", "難題正確性", "主要失分型態"],
        ["雲端基準（三款）", "1.92–1.96", "2.00", "1.67–1.92", "補充參考答案以外的細節（講太多）"],
        ["qwen3.8-27b", "2.00", "1.96", "1.58", "方向反轉、結構鬆散"],
        ["qwen3.6-35b-a3b", "1.92", "1.96", "1.50", "清單／計數錯、中途自我修正"],
    ]
    table(s, rows2, 0.92, 4.42, 11.48, 1.30, [2.55, 1.80, 1.80, 1.65, 3.68],
          head_size=10, body_size=10, row_h=0.34)

    box(s, 0.92, 5.90, 11.48, 0.78, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.20, 6.04, 10.9, 0.52,
         [("這個差別決定了護欄怎麼設計：", {"bold": True, "color": INK}),
          ("雲端錯在「講太多」，用提示收緊即可；地端錯在「算錯」—— 數字、家數、方向，"
           "使用者會直接拿去用，必須把這類題目移出模型自由發揮的範圍。", {})],
         size=10.5, color=BODY)
    return s


def slide_latency(prs):
    s = content_slide(prs, "門檻二：回應速度 — 一款通過、一款出局")
    rows = [
        ["", "模型", "首字回應", "總時間（中位數）", "生成速度"],
        ["雲端基準", "gpt-5.6-luna", "0.97 秒", "1.77 秒", "122 字/秒"],
        ["雲端基準", "gpt-5.6-terra", "1.03 秒", "1.79 秒", "123 字/秒"],
        ["雲端基準", "gemini-3.8-flash", "1.30 秒", "1.80 秒", "442 字/秒"],
        ["地端", "qwen3.6-35b-a3b", "1.17 秒", "2.20 秒", "112 字/秒"],
        ["地端", "qwen3.8-27b", "1.69 秒", "5.50 秒", "30 字/秒"],
    ]
    table(s, rows, 0.92, 1.50, 7.00, 2.25, [1.05, 2.15, 1.20, 1.60, 1.00],
          head_size=10, body_size=10, row_h=0.32, emphasis={5: RED})

    for i, (label, value, col) in enumerate([
        ("35B-A3B 與雲端差距", "＋0.4 秒", GREEN),
        ("27B 與雲端差距", "＋3.7 秒", RED),
    ]):
        metric(s, 8.30 + i * 2.10, 1.50, 1.95, label, value, value_color=col)

    card(s, 8.30, 2.55, 4.05, 1.20, "管線本身只佔 60 毫秒", [
        "模型佔整體時間 95–99%。壓延遲只能換模型或縮短提示，優化檢索沒有空間。",
    ], heading_size=11.5, body_size=9.5)

    bullets(s, 0.95, 4.05, 11.4, 1.4, [
        ("35B-A3B 是 MoE 架構（35B 參數、每次只啟用 3B）　",
         "這是它能在地端跑出雲端級延遲的原因，也是它比 27B 快 2.5 倍的原因。"),
        ("27B 是 dense 架構　",
         "全參數參與運算，5.5 秒的回應時間在客服場景不可接受 —— 這是它出局的直接原因。"),
        ("這個數字綁在測試用的 GPU 上　",
         "RTX PRO 6000（96GB、單機獨佔）。公司自架若用不同等級的卡，延遲需重新驗證。"),
    ], size=11, gap=0.46)

    box(s, 0.92, 5.62, 11.48, 1.05, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.76, 11.0, 0.30, "對提案的意義", size=12, color=BLUE, bold=True)
    text(s, 1.15, 6.10, 11.0, 0.45,
         "地端不再是「慢到不能用」的選項。35B-A3B 慢 0.4 秒，一般客服對話感受不到；"
         "27B 則要明確排除，不要因為「參數比較新」就選它。",
         size=10.5, color=INK)
    return s


def slide_tools(prs):
    s = content_slide(prs, "門檻三：工具呼叫 — 地端優於雲端")
    rows = [
        ["", "模型", "選對率", "平均呼叫（期望 0.95）", "該叫沒叫", "多叫"],
        ["地端", "qwen3.6-35b-a3b", "97%", "0.92", "2", "0"],
        ["雲端基準", "gpt-5.6-terra", "93%", "0.95", "4", "4"],
        ["雲端基準", "gpt-5.6-luna", "90%", "0.90", "6", "3"],
        ["雲端基準", "gemini-3.8-flash", "87%", "1.05", "5", "8"],
        ["地端", "qwen3.8-27b", "83%", "0.78", "10", "0"],
    ]
    table(s, rows, 0.92, 1.50, 7.30, 2.25, [1.05, 2.15, 0.95, 1.85, 0.75, 0.55],
          head_size=9.5, body_size=10, row_h=0.32,
          emphasis={1: GREEN, 5: RED})

    card(s, 8.60, 1.50, 3.80, 2.25, "35B-A3B 是全場唯一零多叫", [
        "工具用得準又克制，這是地端在本次評測唯一勝過所有雲端的項目。",
        "Gemini 多叫 8 次 —— 每次多叫都是一張真人工單或一次影像辨識費用。",
    ], heading_color=GREEN, heading_size=11.5, body_size=9.5)

    text(s, 0.92, 4.02, 11.48, 0.30, "依情境類型：地端強在克制，雲端強在串接",
         size=13, color=BLUE, bold=True)
    rows2 = [
        ["情境", "qwen3.6-35b-a3b", "qwen3.8-27b", "gpt-5.6-terra",
         "gpt-5.6-luna", "gemini-3.8-flash"],
        ["邊界（該不該叫的灰色地帶）", "100%", "50%", "75%", "50%", "75%"],
        ["多工具串接", "67%", "100%", "100%", "100%", "67%"],
        ["多輪承接", "100%", "92%", "92%", "100%", "75%"],
        ["不該叫工具", "100%", "100%", "100%", "100%", "100%"],
    ]
    table(s, rows2, 0.92, 4.42, 11.48, 1.55, [3.08, 1.86, 1.66, 1.66, 1.62, 1.60],
          head_size=9.5, body_size=10, row_h=0.30)

    text(s, 0.92, 6.20, 11.48, 0.34,
         [("待補：多工具串接情境只有 3 個，樣本太小。　", {"bold": True, "color": ORANGE}),
          ("35B-A3B 在這一格 67% 是目前唯一的疑慮，補到 8–10 個情境才能定論。", {})],
         size=10.5, color=BODY)
    return s


def slide_json(prs):
    s = content_slide(prs, "門檻四：結構化輸出 — 通過，且地端代價最小")
    rows = [
        ["", "模型", "可解析", "合 schema", "status 正確", "需剝 code fence"],
        ["地端", "qwen3.6-35b-a3b", "100%", "100%", "100%", "0"],
        ["地端", "qwen3.8-27b", "100%", "100%", "100%", "0"],
        ["雲端基準", "三款雲端模型", "100%", "100%", "100%", "0"],
    ]
    table(s, rows, 0.92, 1.50, 11.48, 1.10, [1.20, 2.60, 1.75, 1.85, 2.10, 1.98],
          head_size=10, body_size=10.5, row_h=0.36)

    text(s, 0.92, 3.18, 11.48, 0.30, "但 JSON 不是免費的 —— 各模型付的延遲代價差很多",
         size=13, color=BLUE, bold=True)
    rows2 = [
        ["模型", "純文字輸出", "JSON 輸出", "JSON 的延遲代價"],
        ["qwen3.6-35b-a3b（地端）", "2,322 ms", "2,657 ms", "＋335 ms"],
        ["gpt-5.6-luna", "1,491 ms", "1,960 ms", "＋469 ms"],
        ["gpt-5.6-terra", "1,700 ms", "2,186 ms", "＋486 ms"],
        ["gemini-3.8-flash", "2,079 ms", "3,257 ms", "＋1,178 ms"],
    ]
    table(s, rows2, 0.92, 3.58, 7.60, 1.55, [3.10, 1.55, 1.50, 1.45],
          head_size=10, body_size=10, row_h=0.30,
          emphasis={1: GREEN, 4: RED})

    card(s, 8.85, 3.58, 3.55, 1.55, "地端反而最不吃虧", [
        "35B-A3B 的 JSON 代價只有 Gemini 的四分之一。",
        "需要結構化輸出的整合案（3D 展、API 串接），地端不是弱勢。",
    ], heading_color=GREEN, heading_size=11.5, body_size=9.5)

    box(s, 0.92, 5.20, 11.48, 1.45, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.20, 5.38, 10.9, 0.32, "這個發現的實務價值", size=12.5, color=ORANGE, bold=True)
    text(s, 1.20, 5.78, 10.9, 0.75,
         "同一條管線上量到：純文字 bot 約 2,060 ms、JSON bot 約 3,256 ms，跨兩個租戶、不同知識庫與提示，"
         "切分完全一致 —— 慢的是結構化輸出本身，不是知識庫或提示。\n"
         "既有的 3D 展看板若改走純文字 + 自行解析，或改用 JSON 代價較低的模型，可望省下約 1.2 秒。",
         size=10.5, color=INK, spacing=1.35)
    return s


def slide_guardrails(prs):
    s = content_slide(prs, "地端上線要補的三道護欄")
    text(s, 0.92, 1.48, 11.48, 0.32,
         "35B-A3B 的缺口很集中：難題的清單、計數與方向判斷。這三道護欄各自對應一個已觀察到的失敗模式，"
         "不是通用建議。",
         size=11, color=BODY)

    for i, (h, why, how, col) in enumerate([
        ("清單與計數題走結構化路徑",
         "觀察到：36 間寫成 34、說 5 家只列 4 家、分區歸錯。",
         "門市清單、家數、交集這類題目改由工具查表輸出，不讓模型自己數。", RED),
        ("提示收緊「不得補充」",
         "觀察到：五款模型共同的失分模式都是補充參考答案以外的內容。",
         "用提示約束比換模型便宜，且對雲端與地端同樣有效。", ORANGE),
        ("難題層人工抽檢",
         "觀察到：難題正確性地端 1.50 vs 雲端 1.67–1.92，缺口只在這一層。",
         "上線初期對「比較」「交集」「條件分支」類問題抽檢即可，不必全量。", BLUE),
    ]):
        x = 0.92 + i * 3.90
        box(s, x, 1.95, 3.66, 2.60, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
            fill=CARD, radius=0.06)
        text(s, x + 0.18, 2.10, 3.30, 0.30, f"{i + 1}", size=15, color=col, bold=True)
        text(s, x + 0.18, 2.46, 3.30, 0.55, h, size=12, color=INK, bold=True,
             spacing=1.25)
        text(s, x + 0.18, 3.10, 3.30, 0.60, why, size=9.5, color=col, spacing=1.3)
        text(s, x + 0.18, 3.78, 3.30, 0.65, how, size=9.5, color=BODY, spacing=1.3)

    box(s, 0.92, 4.78, 11.48, 0.95, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 4.92, 11.0, 0.30, "補上護欄之後，地端與雲端的實際差距",
         size=12, color=BLUE, bold=True)
    text(s, 1.15, 5.26, 11.0, 0.34,
         "清單與計數移出模型後，剩下的差距只有難題的方向判斷 —— 那是抽檢可以攔住的，不是天天發生的問題。",
         size=10.5, color=INK)

    text(s, 0.92, 5.95, 11.48, 0.55,
         [("這份評測沒有涵蓋的：", {"bold": True, "color": INK}),
          ("地端延遲只在一張高階卡上量過，換卡需重測　｜　多工具串接情境只有 3 個　｜　"
           "沒有做真實流量回放，題目來自 FAQ 與 DM", {})],
         size=10.5, color=BODY)
    return s


def slide_cost(prs):
    s = content_slide(prs, "成本：地端不是省錢方案")
    rows = [
        ["方案", "計價方式", "本次工作負載", "每輪成本"],
        ["gpt-5.6-luna（雲端最省）", "每輪計價　US$0.20 / US$1.20 每百萬 token",
         "US$0.46", "US$0.0017"],
        ["gemini-3.8-flash", "每輪計價　US$0.75 / US$3.75（2027 起翻倍）",
         "US$1.68", "US$0.0061"],
        ["gpt-5.6-terra", "每輪計價　US$2.00 / US$12.00", "US$4.68", "US$0.0170"],
        ["地端 Qwen（自架）", "固定月費　RTX PRO 6000 級約 US$1,500／月",
         "US$14.68（租用）", "與流量無關"],
    ]
    table(s, rows, 0.92, 1.50, 11.48, 1.75, [2.95, 4.65, 2.05, 1.83],
          head_size=10.5, body_size=10, row_h=0.36)

    box(s, 0.92, 3.55, 11.48, 1.35, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.20, 3.72, 10.9, 0.32, "損益平衡點：月流量約 40–90 萬輪對話",
         size=13, color=ORANGE, bold=True)
    text(s, 1.20, 4.14, 10.9, 0.62,
         "以雲端最省的 luna 每輪 US$0.0017 換算，地端月費要攤到 40–90 萬輪才划算（視 GPU 等級）。\n"
         "POC 與一般企業客服流量都遠低於此 —— 用成本說服客戶選地端會被拆穿，要用資料落地說服。",
         size=10.5, color=INK, spacing=1.35)

    card(s, 0.92, 5.08, 5.60, 1.45, "本次評測實際支出", [
        "地端 GPU 租用（含磁碟）US$14.68　＋　雲端 API US$6.82",
        "合計約 US$21.5，原規劃預算為 US$80–120。",
    ], heading_size=12, body_size=10)
    card(s, 6.80, 5.08, 5.60, 1.45, "地端真正的成本在哪", [
        "不是每輪費用，是 GPU 採購或租用、維運人力與可用性責任。",
        "提案時要把這塊算進去，不能只比 API 帳單。",
    ], heading_size=12, body_size=10)
    return s


def slide_credibility(prs):
    s = content_slide(prs, "這些數字為什麼可信")
    text(s, 0.92, 1.48, 11.48, 0.32,
         "正式量測前，前導測試發現三個會讓模型分數失真的平台問題。全部修正並上線後才重跑所有數據 —— "
         "本報告的每一個數字都來自修正後的量測。",
         size=11, color=BODY)

    rows = [
        ["發現的問題", "若沒有修，會得到的錯誤結論"],
        ["多輪對話時檢索內容被丟棄（只影響 Gemini）",
         "Gemini 覆蓋率 41%、多輪一路崩，基準線會被拉低，地端看起來比實際更好"],
        ["Gemini 綁定工具時呼叫必定失敗", "工具門檻少一個雲端基準可比"],
        ["防護攔截時回純文字、破壞 JSON 契約",
         "結構化輸出五款分數完全相同，看起來像模型都一樣差 —— 實際上是攔截回合模型根本沒被呼叫"],
    ]
    table(s, rows, 0.92, 2.00, 11.48, 1.60, [5.20, 6.28], row_h=0.42)

    box(s, 0.92, 3.90, 11.48, 1.55, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.20, 4.06, 10.9, 0.32,
         "三次都是同一個訊號抓到的：五個模型的數字一模一樣",
         size=13, color=BLUE, bold=True)
    text(s, 1.20, 4.48, 10.9, 0.85,
         "五個不同來源的模型不可能剛好同分 —— 跨模型一致代表「平台在說話」，不是模型在說話。\n"
         "這個檢查已經內建到報告產生器，未來評測會自動標示，不需要再靠人工察覺。",
         size=11, color=INK, spacing=1.35)

    for i, (label, value, col) in enumerate([
        ("量測前修正", "3 個問題", BLUE),
        ("重跑對話數", "1,380 次", BLUE),
        ("盲評樣本", "300 則", BLUE),
        ("評分有效率", "100%", GREEN),
    ]):
        metric(s, 0.92 + i * 2.92, 5.65, 2.72, label, value, value_color=col)
    return s


def slide_next(prs):
    s = content_slide(prs, "結論與下一步")
    box(s, 0.92, 1.50, 11.48, 1.42, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.30, 1.70, 10.8, 1.10,
         [("地端模型已經可用 —— 但只有 qwen3.6-35b-a3b，而且要補三道護欄。",
           {"bold": True, "color": INK, "size": 14}),
          ("它在四道門檻過三道，工具呼叫甚至優於全部雲端模型；缺口集中在難題的清單與計數，"
           "可以用結構化路徑與抽檢補上。qwen3.8-27b 應明確排除。",
           {"color": BODY, "size": 11.5, "space_before": 8})],
         spacing=1.35)

    text(s, 0.92, 3.15, 11.48, 0.30, "下一步", size=13, color=BLUE, bold=True)
    bullets(s, 0.95, 3.58, 11.4, 1.9, [
        ("換一張接近自架配置的 GPU 重測延遲　",
         "目前的「只慢 0.4 秒」綁在單機獨佔的高階卡上，這是提案前必須確認的前提。"),
        ("補足多工具串接樣本　",
         "情境從 3 個增加到 8–10 個，這是 35B-A3B 目前唯一沒有結論的項目。"),
        ("先在一個內部場景試行　",
         "帶著三道護欄上線，用真實流量驗證抽檢頻率能不能降下來。"),
        ("既有 3D 展看板可考慮換模型　",
         "量到 JSON 結構化輸出讓 Gemini 多花約 1.2 秒，換成代價較低的模型可直接改善。"),
    ], size=11, gap=0.46)

    box(s, 0.92, 5.60, 11.48, 1.05, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.74, 11.0, 0.30, "評測資產（換模型可重跑）", size=12, color=BLUE, bold=True)
    text(s, 1.15, 6.08, 11.0, 0.45,
         "92 輪題組與標準答案　｜　四道門檻的量測腳本（換模型只改設定）　｜　"
         "盲評包產生與揭盲工具　｜　跨模型一致性異常偵測",
         size=10.5, color=INK)
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    prs = Presentation(args.template)
    clear_slides(prs)

    slide_title(prs)
    slide_verdict(prs)
    slide_why(prs)
    slide_method(prs)
    slide_quality(prs)
    slide_latency(prs)
    slide_tools(prs)
    slide_json(prs)
    slide_guardrails(prs)
    slide_cost(prs)
    slide_credibility(prs)
    slide_next(prs)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print(f"已產出 {out}（{len(prs.slides._sldIdLst)} 張）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
