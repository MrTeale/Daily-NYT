import base64
import json
import logging
import time
import traceback
from datetime import datetime, timedelta
from io import BytesIO
from zoneinfo import ZoneInfo

import requests
from pdf2image import convert_from_bytes
from pdf2image.exceptions import PDFPageCountError, PDFSyntaxError, PDFInfoNotInstalledError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

NYT_TZ = ZoneInfo("America/New_York")
NYT_URL = "https://static01.nyt.com/images/{y}/{m}/{d}/nytfrontpage/scan.pdf"
# How many days back to look when today's scan hasn't been published yet.
# (NYT typically uploads the new day's scan ~01:00-01:30 ET.)
MAX_LOOKBACK_DAYS = 2
# (connect, read) seconds per attempt. Lambda timeout is 30 s total and rendering
# takes ~2.5 s, so all fetch attempts together must stay well under that.
REQUEST_TIMEOUT = (3, 10)
FETCH_BUDGET_SECONDS = 20


class ScanNotAvailable(Exception):
    """The front-page scan for a given date is not (yet) available."""


def _response(status, body, content_type, extra_headers=None, is_base64=False):
    headers = {"Content-Type": content_type, "Access-Control-Allow-Origin": "*"}
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": status,
        "headers": headers,
        "body": body,
        "isBase64Encoded": is_base64,
    }


def get_pdf_scan(date_value):
    url = NYT_URL.format(
        y=date_value.strftime("%Y"), m=date_value.strftime("%m"), d=date_value.strftime("%d")
    )
    started = time.monotonic()
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        # Transient (timeout / connection error). Caller falls back but logs loudly.
        logger.warning(json.dumps({"event": "fetch_error", "url": url, "error": repr(exc)}))
        raise ScanNotAvailable(f"{url} -> {type(exc).__name__}") from exc

    content = response.content
    content_type = response.headers.get("Content-Type", "")
    logger.info(json.dumps({
        "event": "fetch", "url": url, "status": response.status_code,
        "content_type": content_type, "bytes": len(content),
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }))

    # NYT's S3-backed CDN answers 403 AccessDenied (not 404) for a day that
    # hasn't been published yet, so treat *any* non-2xx as "not available".
    if not response.ok:
        raise ScanNotAvailable(f"{url} -> HTTP {response.status_code}")

    # Make sure we actually got a (complete) PDF before handing it to poppler.
    if b"%PDF" not in content[:1024]:
        logger.warning(json.dumps({"event": "non_pdf_body", "url": url, "content_type": content_type}))
        raise ScanNotAvailable(f"{url} -> non-PDF body")
    declared = response.headers.get("Content-Length")
    if declared and declared.isdigit() and int(declared) != len(content):
        logger.warning(json.dumps({"event": "truncated_body", "url": url,
                                   "declared": int(declared), "received": len(content)}))
        raise ScanNotAvailable(f"{url} -> truncated body")

    return content


def fetch_latest_scan(now):
    """Try today, then previous days, returning (date, pdf_bytes)."""
    deadline = time.monotonic() + FETCH_BUDGET_SECONDS
    for days_back in range(MAX_LOOKBACK_DAYS + 1):
        if time.monotonic() > deadline:
            logger.warning(json.dumps({"event": "fetch_budget_exhausted", "days_tried": days_back}))
            break
        day = now - timedelta(days=days_back)
        try:
            return day, get_pdf_scan(day)
        except ScanNotAvailable as exc:
            logger.info(json.dumps({"event": "scan_unavailable", "date": str(day.date()), "reason": str(exc)}))
    raise ScanNotAvailable(f"no scan found in the last {MAX_LOOKBACK_DAYS + 1} days")


def render_jpeg(pdf_scan):
    """Rasterise page 1 to a 1440x2560 grayscale JPEG and return the bytes."""
    # Lossless PPM out of poppler, then a single JPEG encode (the old code
    # lossy-encoded twice: pdftoppm -> JPEG -> PIL -> JPEG, and its quality=100
    # jpegopt dict was never actually passed, so output was default q75).
    image = convert_from_bytes(
        pdf_scan,
        use_cropbox=True,
        grayscale=True,
        fmt="ppm",
        size=(1440, 2560),
    )[0]
    buf = BytesIO()
    image.convert("L").save(buf, "JPEG", quality=85, optimize=True)
    return buf.getvalue()


def main(event, context):
    now = datetime.now(NYT_TZ)

    try:
        day, pdf_scan = fetch_latest_scan(now)
    except ScanNotAvailable as exc:
        logger.error(json.dumps({"event": "no_scan_available", "reason": str(exc)}))
        return _response(
            503,
            "NYT front page not available yet, try again shortly",
            "text/plain",
            {"Retry-After": "900", "Cache-Control": "no-store"},
        )

    try:
        jpeg = render_jpeg(pdf_scan)
    except (PDFPageCountError, PDFSyntaxError, PDFInfoNotInstalledError, OSError, IndexError, ValueError) as exc:
        logger.error(json.dumps({"event": "render_failed", "date": str(day.date()),
                                 "error": repr(exc), "traceback": traceback.format_exc()}))
        return _response(
            500,
            json.dumps({"error": "Failed to convert NYT front page", "date": str(day.date())}),
            "application/json",
            {"Cache-Control": "no-store"},
        )

    fallback_days = (now.date() - day.date()).days
    logger.info(json.dumps({"event": "served", "date": str(day.date()),
                            "fallback_days": fallback_days, "jpeg_bytes": len(jpeg)}))
    return _response(
        200,
        base64.b64encode(jpeg).decode("ascii"),
        "image/jpeg",
        {
            # A given day's page rarely changes; let browsers/CloudFront cache it for 30 min.
            "Cache-Control": "public, max-age=1800",
            # Which edition was actually served (today vs. a fallback day).
            "X-NYT-Date": str(day.date()),
        },
        is_base64=True,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    r = main({}, None)
    print(r["statusCode"], {k: v for k, v in r["headers"].items()})
