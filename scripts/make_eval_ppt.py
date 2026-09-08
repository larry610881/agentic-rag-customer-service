#!/usr/bin/env python3
"""把模型評測正式報告產成公司格式（統一資訊）的 PPTX。

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
    tf.text = "雲端 × 地端大型語言模型評測"
    r = tf.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.bold, r.font.color.rgb = FONT, Pt(36), True, BLUE

    sub = s.placeholders[1]
    sub.left, sub.top, sub.width, sub.height = (
        Inches(1.67), Inches(3.15), Inches(10.0), Inches(1.0)
    )
    stf = sub.text_frame
    stf.text = "客服 RAG 平台選型依據"
    r = stf.paragraphs[0].runs[0]
    r.font.name, r.font.size, r.font.color.rgb = FONT, Pt(20), INK
    p2 = stf.add_paragraph()
    r2 = p2.add_run()
    r2.text = "五個模型・92 輪題目・3 次重跑・300 則盲評  |  報告產出：2026-09-08"
    r2.font.name, r2.font.size, r2.font.color.rgb = FONT, Pt(13), MUTED

    box(s, 10.40, 2.80, 2.60, 2.20, shape=MSO_SHAPE.CHEVRON, fill=BLUE)
    box(s, 11.60, 3.90, 1.60, 1.35, shape=MSO_SHAPE.CHEVRON, fill=ORANGE)

    cards = [
        ("評測日期", "2026-09-08"),
        ("受測模型", "雲端 3 ・ 地端 2"),
        ("對話次數", "1,380 次"),
        ("盲評樣本", "300 則回答"),
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


def slide_summary(prs):
    s = content_slide(prs, "一頁結論")
    rows = [
        ["模型", "盲評總分", "工具選對率", "回應時間", "每輪成本", "定位"],
        ["gpt-5.6-terra（雲）", "5.85", "93%", "1.79 秒", "US$0.0170", "品質上限"],
        ["gpt-5.6-luna（雲）", "5.83", "90%", "1.77 秒", "US$0.0017", "品質／成本最佳"],
        ["gemini-3.8-flash（雲）", "5.70", "87%", "1.80 秒", "US$0.0061", "吞吐最高"],
        ["qwen3.6-35b-a3b（地端）", "5.62", "97%", "2.20 秒", "GPU 月租", "資料不出境可用"],
        ["qwen3.8-27b（地端）", "5.65", "83%", "5.50 秒", "GPU 月租", "不建議"],
    ]
    table(s, rows, 0.92, 1.50, 11.48, 2.30, [2.85, 1.35, 1.45, 1.35, 1.55, 2.93],
          emphasis={5: RED}, row_h=0.33)

    bullets(s, 0.95, 3.86, 11.4, 1.8, [
        ("雲端 GPT 兩款品質最穩　", "盲評 5.85／5.83，差距在雜訊內；luna 的牌價是 terra 的十分之一。"),
        ("地端 35B-A3B 延遲已達雲端同級　", "2.2 秒 vs 雲端 1.8 秒，且工具選擇最準（97%），但答題品質墊底。"),
        ("地端 27B 出局　", "5.5 秒是其餘四臂的 3 倍，品質沒有換到。"),
        ("結構化輸出五臂全部 100%　", "JSON 契約不構成選型差異，連地端 27B 都守得住。"),
    ], size=11, gap=0.44)

    box(s, 0.92, 5.74, 11.48, 0.92, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.87, 11.0, 0.30, "選型建議", size=12, color=BLUE, bold=True)
    text(s, 1.15, 6.21, 11.0, 0.34,
         "不要求資料落地 → luna（品質與 terra 相同、成本十分之一）　｜　"
         "要求資料不出境 → 35B-A3B 可用，須加三道護欄　｜　27B 不建議",
         size=10.5, color=INK)
    return s


def slide_design(prs):
    s = content_slide(prs, "評測設計")
    text(s, 0.92, 1.48, 11.48, 0.32,
         "五個模型接在同一條管線上：同一份知識庫、同一組系統提示、同一個檢索與防護設定，"
         "推理強度全部設為最低。唯一的變因是模型本身。",
         size=11, color=BODY)

    rows = [
        ["題組", "內容", "輪數 × 重跑 × 模型", "量什麼"],
        ["問答 60 輪", "14 段對話，三層難度（簡 24／中 24／難 12），標準答案可回溯知識庫原文",
         "60 × 3 × 5 ＝ 900", "正確性、忠實度、格式、多輪承接"],
        ["工具 20 輪", "轉真人、查 DM 圖卡、不該叫工具、多工具串接、邊界情境",
         "20 × 3 × 5 ＝ 300", "模型自己選對工具的能力"],
        ["JSON 12 輪", "命中／未命中／干擾三類，固定 schema",
         "12 × 3 × 5 ＝ 180", "結構化輸出契約"],
    ]
    table(s, rows, 0.92, 1.95, 11.48, 1.55, [1.55, 5.15, 2.18, 2.60], row_h=0.42)

    card(s, 0.92, 3.86, 5.60, 1.58, "量測方法：機械指標 + 人工盲評", [
        "六張機械指標表：延遲、穩定度、答案覆蓋率、多輪衰減、工具、結構化輸出",
        "盲評：獨立評審對 300 則回答依三個維度各給 0–2 分",
        "機械指標只用來抓異常，排名以盲評為準",
    ], body_size=9.5)
    card(s, 6.80, 3.86, 5.60, 1.58, "盲評如何確保無偏", [
        "評審在專案外環境作業，看不到模型名稱、延遲、來源檔案",
        "代號每輪重新洗牌，無法跨輪累積指紋",
        "三次重跑分層抽樣各取 20 輪，避免單次手氣影響結論",
    ], body_size=9.5)

    text(s, 0.92, 5.66, 11.48, 0.9,
         [("題目全部從既有客服資料抽取，不為地端模型量身訂做；",
           {"bold": True, "color": INK}),
          ("8 個知識庫內資料互相矛盾的商品事先排除，避免答案無法判定對錯。", {})],
         size=10.5, color=BODY)
    return s


def slide_blind(prs):
    s = content_slide(prs, "品質：盲評結果")
    rows = [
        ["模型", "正確性", "忠實度", "格式與繁體", "總分（滿分 6）"],
        ["gpt-5.6-terra", "1.92", "1.93", "2.00", "5.85"],
        ["gpt-5.6-luna", "1.92", "1.92", "2.00", "5.83"],
        ["gemini-3.8-flash", "1.97", "1.82", "1.92", "5.70"],
        ["qwen3.8-27b", "1.90", "1.83", "1.92", "5.65"],
        ["qwen3.6-35b-a3b", "1.85", "1.82", "1.95", "5.62"],
    ]
    table(s, rows, 0.92, 1.50, 6.35, 2.25, [1.95, 0.96, 0.96, 1.16, 1.32],
          body_size=10, row_h=0.32)

    card(s, 7.60, 1.50, 4.80, 1.80, "總分差只有 0.23，因為有天花板效應", [
        "60 輪裡有 34 輪（57%）五臂全部滿分 —— 簡單題大家都會。",
        "真正能分出高下的是剩下 26 輪，差距在那裡放大到 0.5 分，排序不變。",
    ], heading_size=12, body_size=10)

    text(s, 0.92, 4.02, 11.48, 0.30, "只看 26 輪有鑑別力的題目",
         size=13, color=BLUE, bold=True)
    rows2 = [
        ["模型", "gpt-5.6-terra", "gpt-5.6-luna", "gemini-3.8-flash",
         "qwen3.8-27b", "qwen3.6-35b-a3b"],
        ["平均總分", "5.65", "5.62", "5.31", "5.19", "5.12"],
        ["其中拿滿分", "19 / 26", "19 / 26", "13 / 26", "11 / 26", "8 / 26"],
    ]
    table(s, rows2, 0.92, 4.42, 11.48, 1.0, [1.85, 1.93, 1.93, 1.99, 1.90, 1.88],
          head_size=10.5, body_size=10.5, row_h=0.33)

    box(s, 0.92, 5.72, 11.48, 0.92, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.85, 11.0, 0.30, "難題層才是分水嶺", size=12, color=BLUE, bold=True)
    text(s, 1.15, 6.19, 11.0, 0.34,
         "難題正確性：gemini 1.92　>　terra 1.75　>　luna 1.67　>　27B 1.58　>　"
         "35B-A3B 1.50　—　簡單與中等題五臂幾乎無差，地端只在需要「算」的題目上落後 0.3–0.4 分。",
         size=10.5, color=INK)
    return s


def slide_errors(prs):
    s = content_slide(prs, "錯法不一樣：這比分數更重要")
    rows = [
        ["模型", "扣分筆數", "主要型態", "代表例"],
        ["gpt-5.6-terra", "7", "補充超出參考答案的細節", "清單 13 家全對，但家數寫成 10"],
        ["gpt-5.6-luna", "7", "補充超出參考答案的細節", "清單漏一家、誤列一家"],
        ["gemini-3.8-flash", "13", "補充過多（11 筆）、輸出中斷", "清單題只輸出第一家就中斷"],
        ["qwen3.6-35b-a3b", "18", "清單／計數錯、中途自我修正",
         "36 間寫成 34；比價先答錯再在文中改口"],
        ["qwen3.8-27b", "15", "方向反轉、結構鬆散", "「五月花較貴」寫成「黑松較貴」"],
    ]
    table(s, rows, 0.92, 1.50, 11.48, 2.25, [2.35, 1.20, 3.35, 4.58],
          emphasis={4: RED, 5: RED}, body_size=10, row_h=0.33)

    card(s, 0.92, 4.00, 3.65, 1.75, "雲端的錯是「講太多」", [
        "方向對、事實對，只是補了參考答案沒寫的細節。",
        "這類錯用提示收緊即可，不必換模型。",
    ], heading_color=BLUE, heading_size=12, body_size=10)
    card(s, 4.83, 4.00, 3.65, 1.75, "地端的錯是「算錯」", [
        "數字、家數、方向。",
        "在客服場景比「講太多」危險得多 —— 使用者會直接拿去用。",
    ], heading_color=RED, heading_size=12, body_size=10)
    card(s, 8.74, 4.00, 3.66, 1.75, "35B 會在同一段自我修正", [
        "比價題先說「黑松貴 50 元」，接著「修正：五月花貴 235 元」。",
        "最終答案對，但客戶看到的是自相矛盾的文字。",
    ], heading_color=AMBER, heading_size=12, body_size=10)

    text(s, 0.92, 5.95, 11.48, 0.55,
         [("五臂共同的失分模式是同一個：補充無法從參考答案佐證的內容　",
           {"bold": True, "color": INK}),
          ("（gemini 11、35B 11、27B 10、luna 5、terra 4）。"
           "這不只是模型問題，是提示允許發揮 —— 平台端收緊比換模型便宜。", {})],
         size=10.5, color=BODY)
    return s


def slide_tools(prs):
    s = content_slide(prs, "工具呼叫")
    rows = [
        ["模型", "選對率", "平均呼叫次數（期望 0.95）", "該叫沒叫", "多叫"],
        ["qwen3.6-35b-a3b", "97%", "0.92", "2", "0"],
        ["gpt-5.6-terra", "93%", "0.95", "4", "4"],
        ["gpt-5.6-luna", "90%", "0.90", "6", "3"],
        ["gemini-3.8-flash", "87%", "1.05", "5", "8"],
        ["qwen3.8-27b", "83%", "0.78", "10", "0"],
    ]
    table(s, rows, 0.92, 1.50, 6.55, 2.25, [2.15, 0.95, 1.70, 0.95, 0.80],
          head_size=10, body_size=10, row_h=0.32)

    card(s, 7.80, 1.50, 4.60, 2.25, "35B-A3B 不只分數最高，形態也最健康", [
        "零多叫、零踩禁止工具。",
        "Gemini 87% 但多叫 8 次 —— 傾向「不確定就先叫工具」。",
        "在會轉真人、會查圖卡的情境，每次多叫都是一張真人工單或一次影像辨識費用。",
    ], heading_size=11.5, body_size=9.5)

    text(s, 0.92, 4.02, 11.48, 0.30, "依情境類型的選對率", size=13, color=BLUE, bold=True)
    rows2 = [
        ["情境", "qwen3.6-35b-a3b", "gpt-5.6-terra", "gpt-5.6-luna",
         "gemini-3.8-flash", "qwen3.8-27b"],
        ["邊界（該不該叫的灰色地帶）", "100%", "75%", "50%", "75%", "50%"],
        ["多工具串接", "67%", "100%", "100%", "67%", "100%"],
        ["多輪承接", "100%", "92%", "100%", "75%", "92%"],
        ["不該叫工具", "100%", "100%", "100%", "100%", "100%"],
    ]
    table(s, rows2, 0.92, 4.42, 11.48, 1.55, [3.08, 1.78, 1.62, 1.62, 1.76, 1.62],
          head_size=9.5, body_size=10, row_h=0.30)

    text(s, 0.92, 6.20, 11.48, 0.34,
         [("地端強在克制，雲端強在串接。　", {"bold": True, "color": INK}),
          ("多工具串接只有 3 個情境，樣本小，該格結論保留。"
           "27B「該叫沒叫」10 次 —— 傾向自己回答而不查工具。", {})],
         size=10.5, color=BODY)
    return s


def slide_perf(prs):
    s = content_slide(prs, "效能")
    rows = [
        ["模型", "首字回應", "總時間（中位數）", "生成速度"],
        ["gpt-5.6-luna", "0.97 秒", "1.77 秒", "122 字/秒"],
        ["gpt-5.6-terra", "1.03 秒", "1.79 秒", "123 字/秒"],
        ["gemini-3.8-flash", "1.30 秒", "1.80 秒", "442 字/秒"],
        ["qwen3.6-35b-a3b", "1.17 秒", "2.20 秒", "112 字/秒"],
        ["qwen3.8-27b", "1.69 秒", "5.50 秒", "30 字/秒"],
    ]
    table(s, rows, 0.92, 1.50, 6.35, 2.25, [2.25, 1.35, 1.70, 1.05],
          body_size=10, row_h=0.32, emphasis={5: RED})

    for i, (label, value, col) in enumerate([
        ("地端最快臂", "2.20 秒", BLUE),
        ("與雲端差距", "＋0.4 秒", GREEN),
        ("27B 總時間", "5.50 秒", RED),
    ]):
        metric(s, 7.75 + i * 1.60, 1.50, 1.50, label, value, value_color=col)

    card(s, 7.75, 2.55, 4.65, 1.20, "管線本身只佔 60 毫秒", [
        "模型佔整體時間的 95–99%。要壓延遲只能換模型或縮短提示，優化檢索沒有空間。",
    ], heading_size=11.5, body_size=10)

    bullets(s, 0.95, 4.05, 11.4, 1.3, [
        ("35B-A3B 只比雲端慢 0.4 秒　",
         "但這個數字綁在 RTX PRO 6000（96GB、單機獨佔）上；公司自架若用不同等級的卡，需重測。"),
        ("Gemini 首字最慢但生成最快　",
         "總時間追平；串流體驗是「等久一點才開始、開始後一口氣出完」。"),
        ("27B 是 dense 架構　",
         "5.5 秒的回應時間在客服場景不可接受，這是它出局的直接原因。"),
    ], size=11, gap=0.46)

    box(s, 0.92, 5.55, 11.48, 1.05, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.68, 11.0, 0.30, "結構化輸出（JSON）", size=12, color=BLUE, bold=True)
    text(s, 1.15, 6.02, 11.0, 0.45,
         "33 輪、五臂全部 100%（可解析／合 schema／status 正確／無需剝除 code fence）。"
         "JSON 契約不是選型差異 —— 連地端 27B 都守得住，3D 展場斷網備案所需的結構化輸出能力，地端已具備。",
         size=10.5, color=INK)
    return s


def slide_cost(prs):
    s = content_slide(prs, "成本")
    text(s, 0.92, 1.48, 11.48, 0.30,
         "以同一工作負載（276 次對話，每次含檢索、防護與生成）依各模型公告牌價計算。",
         size=11, color=BODY)

    rows = [
        ["模型", "牌價（輸入／輸出，每百萬 token）", "本次工作負載", "每輪成本"],
        ["gpt-5.6-terra", "US$2.00 / US$12.00", "US$4.68", "US$0.0170"],
        ["gpt-5.6-luna", "US$0.20 / US$1.20", "US$0.46", "US$0.0017"],
        ["gemini-3.8-flash", "US$0.75 / US$3.75（2027 起翻倍）", "US$1.68", "US$0.0061"],
    ]
    table(s, rows, 0.92, 1.95, 11.48, 1.10, [2.60, 4.60, 2.14, 2.14], row_h=0.34)

    card(s, 0.92, 3.58, 5.60, 1.72, "地端是固定月費，不是每輪計價", [
        "RTX PRO 6000 級 GPU 24×7 租用約 US$1,500／月；L40S 級約 US$720／月。",
        "以 luna 每輪 US$0.0017 換算，月流量要超過約 40–90 萬輪對話，地端才比雲端便宜。",
        "在 POC 流量下地端不省錢 —— 它的價值是資料不出境與延遲可控。",
    ], heading_size=12, body_size=9.5)

    card(s, 6.80, 3.58, 5.60, 1.72, "本次評測實際支出", [
        "地端 GPU 租用（含磁碟）：US$14.68",
        "雲端 API（牌價，三個模型三個題組合計）：US$6.82",
        "合計約 US$21.5 —— 原規劃預算為 US$80–120。",
    ], heading_size=12, body_size=9.5)

    box(s, 0.92, 5.52, 11.48, 1.15, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.65, 11.0, 0.30, "成本面的關鍵取捨", size=12, color=BLUE, bold=True)
    text(s, 1.15, 6.00, 11.0, 0.60,
         "luna 的品質與 terra 相同（5.83 vs 5.85，差距在雜訊內），但每輪成本只有十分之一 —— "
         "這是本次評測在成本面最直接可執行的結論。\n"
         "Gemini 2027 年起牌價翻倍，若要長期依賴需重新評估。",
         size=10.5, color=INK)
    return s


def slide_recommend(prs):
    s = content_slide(prs, "選型建議")
    rows = [
        ["情境", "建議", "理由"],
        ["不要求資料落地", "gpt-5.6-luna",
         "品質與 terra 相同（5.83 vs 5.85），牌價十分之一"],
        ["要求資料不出境／客戶內網", "qwen3.6-35b-a3b ＋ 三道護欄",
         "延遲可接受、工具最準、JSON 沒問題；弱點是難題的清單與計數"],
        ["—", "不建議 qwen3.8-27b", "回應時間 5.5 秒出局，品質沒有換到"],
        ["—", "gemini-3.8-flash 當備援",
         "覆蓋率最高、吞吐最快，但補充過多、工具多叫，且 2027 年起牌價翻倍"],
    ]
    table(s, rows, 0.92, 1.50, 11.48, 1.75, [3.05, 3.30, 5.13], row_h=0.38)

    text(s, 0.92, 3.62, 11.48, 0.30, "地端上線的三道護欄",
         size=13, color=BLUE, bold=True)
    for i, (h, b) in enumerate([
        ("清單與計數題走結構化路徑",
         "門市清單、家數、交集這類題目改由工具查表輸出，不讓模型自己數。"),
        ("提示收緊「不得補充」",
         "五臂共同的失分模式是補充參考答案以外的內容；用提示約束比換模型便宜。"),
        ("難題層人工抽檢",
         "上線初期對「比較」「交集」「條件分支」類問題抽檢，這是地端與雲端唯一有實質差距的地方。"),
    ]):
        x = 0.92 + i * 3.90
        card(s, x, 4.02, 3.66, 1.58, f"{i + 1}　{h}", [b],
             heading_size=11.5, body_size=10)

    box(s, 0.92, 5.70, 11.48, 0.95, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.83, 11.0, 0.30, "這份評測沒有涵蓋的", size=12, color=BLUE, bold=True)
    text(s, 1.15, 6.17, 11.0, 0.34,
         "地端延遲只在一張高階卡上量過，換卡需重測　｜　多工具串接情境只有 3 個，該格結論保留　｜　"
         "沒有做真實流量回放，題目來自 FAQ 與 DM",
         size=10.5, color=INK)
    return s


def slide_credibility(prs):
    s = content_slide(prs, "資料可信度")
    text(s, 0.92, 1.48, 11.48, 0.32,
         "正式量測前，前導測試發現三個會讓模型分數失真的平台問題。"
         "全部修正並上線後才重跑所有數據 —— 本報告的每一個數字都來自修正後的量測。",
         size=11, color=BODY)

    rows = [
        ["發現的問題", "若沒有修，會得到的錯誤結論"],
        ["多輪對話時檢索內容被丟棄（只影響 Gemini）",
         "Gemini 覆蓋率 41%、多輪一路崩，會被淘汰 —— 實際上它是覆蓋率第一"],
        ["Gemini 綁定工具時呼叫必定失敗",
         "Gemini 的工具題無法納入比較"],
        ["防護攔截時回純文字、破壞 JSON 契約",
         "JSON 表五臂分數完全相同，看起來像模型都一樣差 —— 實際上是攔截回合模型根本沒被呼叫"],
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
    box(s, 0.92, 1.50, 11.48, 1.55, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.30, 1.72, 10.8, 1.15,
         [("雲端 GPT-5.6 luna 是目前最合理的預設選擇 —— 品質與 terra 相同，成本只有十分之一。",
           {"bold": True, "color": INK, "size": 13}),
          ("需要資料不出境時，地端 qwen3.6-35b-a3b 已可用：延遲只慢 0.4 秒、工具最準、"
           "結構化輸出無虞；代價是難題的清單與計數要靠護欄補強。",
           {"color": BODY, "size": 12, "space_before": 8})],
         spacing=1.35)

    text(s, 0.92, 3.28, 11.48, 0.30, "下一步", size=13, color=BLUE, bold=True)
    bullets(s, 0.95, 3.70, 11.4, 1.8, [
        ("補足多工具串接樣本　",
         "情境從 3 個增加到 8–10 個，才能支撐「雲端強在串接」這個結論。"),
        ("換一張接近自架配置的 GPU 重測延遲　",
         "目前的「只慢 0.4 秒」綁在單機獨佔的高階卡上。"),
        ("導入地端前先做三道護欄　",
         "清單題走結構化、提示收緊、難題抽檢，三者缺一不可。"),
        ("平台端持續監控　",
         "「五臂一致性掃描」已內建，未來評測先跑它再看排名。"),
    ], size=11, gap=0.46)

    box(s, 0.92, 5.70, 11.48, 0.95, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
        fill=CARD, radius=0.08)
    text(s, 1.15, 5.83, 11.0, 0.30, "評測資產（可重複使用）", size=12, color=BLUE, bold=True)
    text(s, 1.15, 6.17, 11.0, 0.34,
         "92 輪題組與標準答案　｜　六張機械指標表的產生器（換模型只改設定）　｜　"
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
    slide_summary(prs)
    slide_design(prs)
    slide_blind(prs)
    slide_errors(prs)
    slide_tools(prs)
    slide_perf(prs)
    slide_cost(prs)
    slide_recommend(prs)
    slide_credibility(prs)
    slide_next(prs)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print(f"已產出 {out}（{len(prs.slides._sldIdLst)} 張）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
