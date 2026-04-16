"""LINE Flex carousel builder unit tests."""

import pytest

from src.infrastructure.line.flex_image_carousel_builder import (
    LINE_FLEX_CAROUSEL_MAX,
    build_image_carousel,
)


def _src(page: int, url: str = None, snippet: str = "snippet"):
    return {
        "image_url": url or f"https://signed/page_{page}",
        "page_number": page,
        "content_snippet": snippet,
    }


def test_single_image_one_bubble():
    out = build_image_carousel([_src(1)])
    assert out["type"] == "carousel"
    assert len(out["contents"]) == 1


def test_five_images_five_bubbles():
    out = build_image_carousel([_src(i) for i in range(1, 6)])
    assert len(out["contents"]) == 5


def test_caps_at_line_max():
    # 15 → cap 12
    out = build_image_carousel([_src(i) for i in range(1, 16)])
    assert len(out["contents"]) == LINE_FLEX_CAROUSEL_MAX == 12


def test_bubble_structure_complete():
    src = _src(21, url="https://signed/foo", snippet="衛生紙買一送一")
    out = build_image_carousel([src])
    bubble = out["contents"][0]

    # hero with image + uri action
    assert bubble["hero"]["type"] == "image"
    assert bubble["hero"]["url"] == "https://signed/foo"
    assert bubble["hero"]["action"]["uri"] == "https://signed/foo"

    # body with page label + caption
    body_texts = [c["text"] for c in bubble["body"]["contents"]]
    assert "第 21 頁" in body_texts
    assert "衛生紙買一送一" in body_texts

    # footer with button → 同 URL
    footer_btn = bubble["footer"]["contents"][0]
    assert footer_btn["type"] == "button"
    assert footer_btn["action"]["uri"] == "https://signed/foo"
    assert footer_btn["action"]["label"] == "查看原圖"
