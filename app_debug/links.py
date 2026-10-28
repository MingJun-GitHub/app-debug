"""URL normalization and link resolution independent of HTTP transport."""

from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


WEB_TO_DEEP_HOST = {
    "bloomchic.com": "app",
    "bloomchic.co.uk": "app.uk",
    "au.bloomchic.com": "app.au",
    "bloomchic.au": "app.au",
    "eu.bloomchic.com": "app.eu",
    "bloomchic.eu": "app.eu",
    "de.bloomchic.com": "app.de",
    "bloomchic.de": "app.de",
    "fr.bloomchic.com": "app.fr",
    "bloomchic.fr": "app.fr",
    "bloom-chic-dev.myshopify.com": "app",
}

DEEP_TO_WEB_HOST = {
    "app": "https://bloomchic.com",
    "app.uk": "https://bloomchic.co.uk",
    "app.au": "https://au.bloomchic.com",
    "app.eu": "https://eu.bloomchic.com",
    "app.de": "https://bloomchic.de",
    "app.fr": "https://bloomchic.fr",
}

LINK_AGGREGATORS = {
    "bloomchic.onelink.me",
    "bloomchic.page.link",
}


def normalize_link_url(value):
    """Validate and normalize a URL intended for the installed app."""
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("链接不能为空")
    if len(raw) > 8192:
        raise ValueError("链接过长")
    if not re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", raw):
        raw = f"https://{raw}"
    try:
        parsed = urlsplit(raw)
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()
    except ValueError as exc:
        raise ValueError(f"链接格式无效: {exc}") from exc
    if scheme not in {"http", "https", "bloomchic"}:
        raise ValueError("仅支持 http、https 或 bloomchic 链接")
    if not hostname:
        raise ValueError("链接缺少域名或 host")
    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def resolve_page_links(value):
    """Build H5, Universal Link and App Deep Link variants from one URL."""
    normalized = normalize_link_url(value)
    parsed = urlsplit(normalized)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()
    normalized_host = hostname.removeprefix("www.")
    warning = ""

    if scheme in {"http", "https"}:
        h5_url = normalized
        universal_url = normalized
        if normalized_host in LINK_AGGREGATORS:
            deep_url = ""
            deep_host = ""
            warning = "聚合短链不能直接转换为 App Deep Link，请使用 Universal Link。"
        else:
            deep_host = WEB_TO_DEEP_HOST.get(normalized_host, "app")
            if normalized_host not in WEB_TO_DEEP_HOST and not normalized_host.endswith(".myshopify.com"):
                warning = "未识别的 H5 域名，Deep Link 将使用默认 bloomchic://app。"
            path = parsed.path
            if path == "/":
                path = ""
            deep_url = urlunsplit(("bloomchic", deep_host, path, parsed.query, parsed.fragment))
        web_host = normalized_host
    else:
        deep_url = normalized
        deep_host = hostname
        web_base = DEEP_TO_WEB_HOST.get(hostname)
        if web_base:
            base = urlsplit(web_base)
            universal_url = urlunsplit((
                base.scheme,
                base.netloc,
                parsed.path or base.path,
                parsed.query,
                parsed.fragment,
            ))
            h5_url = universal_url
            web_host = base.netloc.removeprefix("www.")
        else:
            universal_url = ""
            h5_url = ""
            web_host = ""
            warning = "未识别的 App host，无法反推 H5 / Universal Link。"

    recognized_universal = bool(
        web_host
        and (
            web_host in WEB_TO_DEEP_HOST
            or web_host in LINK_AGGREGATORS
            or web_host.endswith(".bloomchic.com")
            or web_host.endswith(".bloomchic.co.uk")
            or web_host.endswith(".myshopify.com")
        )
    )

    targets = []
    if h5_url:
        targets.append({
            "kind": "h5",
            "label": "H5 页面",
            "description": "浏览器直接访问的网页地址",
            "value": h5_url,
        })
    if universal_url:
        targets.append({
            "kind": "universal",
            "label": "Universal Link",
            "description": "扫码或从系统打开时，由 iOS / Android 决定进入 App 或浏览器",
            "value": universal_url,
        })
    if deep_url:
        targets.append({
            "kind": "deeplink",
            "label": "App Deep Link",
            "description": "直接交给当前 App 的路由处理",
            "value": deep_url,
        })

    return {
        "input": str(value or "").strip(),
        "normalized": normalized,
        "siteHost": web_host,
        "deepLinkHost": deep_host,
        "recognizedUniversal": recognized_universal,
        "warning": warning,
        "targets": targets,
    }

