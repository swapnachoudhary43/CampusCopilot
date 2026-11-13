"""Fetch allowlisted official pages and index them with the existing RAG store.

Student questions do not start a crawl. An administrator starts one run.
A later run skips a page whose extracted text hash has not changed.
"""

import logging
import re
import ssl
import threading
import time
from collections import deque
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import CrawlRecord, Document, OfficialSite
from app.services.crawl.allowlist import OFFICIAL_SITES, SEED_URLS, department_for, host_allowed
from app.services.crawl.extract import extract_html, looks_like_script_shell
from app.services.crawl.robots import disallowed_prefixes, path_allowed
from app.services.rag.ingest import DocumentProcessError, rebuild_from_database, store_pdf, upsert_text_source
from app.utils.time import utcnow

logger = logging.getLogger("campuscopilot.crawl")

USER_AGENT = "CampusCopilotAcademicCrawler/1.0"
_SKIP = re.compile(
    r"(roll.?list|result|merit|photograph|gallery|wp-admin|facebook|instagram|youtube|twitter|linkedin|drive\.google|\.jpg|\.jpeg|\.png|\.zip)",
    re.IGNORECASE,
)
_PRIORITY = (
    "library", "hostel", "sport", "admission", "exam", "contact", "facilit",
    "about", "department", "student", "calendar", "notice", "placement", "address", "school",
)
_USEFUL_PDF = (
    "hostel", "library", "admission", "fee", "calendar", "sport", "laborator",
    "contact", "warden", "ordinance", "prospectus", "brochure", "placement", "address",
)
_state_lock = threading.Lock()
_state = {"running": False, "started_at": None, "finished_at": None, "last_error": None, "indexed": 0, "failed": 0}


def crawl_status() -> dict:
    return dict(_state)


def start_crawl_background(
    session_factory,
    *,
    max_pages: int = 25,
    max_pdfs: int = 6,
    owner_id: int | None = None,
    seeds: list[str] | None = None,
) -> bool:
    if not _state_lock.acquire(blocking=False):
        return False
    _state.update(running=True, started_at=utcnow().isoformat(), finished_at=None, last_error=None, indexed=0, failed=0)

    def _run():
        db = session_factory()
        try:
            summary = crawl_official_sites(
                db, max_pages=max_pages, max_pdfs=max_pdfs, owner_id=owner_id, seeds=seeds
            )
            _state["indexed"] = summary["indexed"]
            _state["failed"] = summary["failed"]
        except Exception as exc:
            logger.exception("Official-site crawl failed")
            _state["last_error"] = "The crawl stopped because of an internal error."
            logger.error("Crawl error type %s", type(exc).__name__)
        finally:
            db.close()
            _state["running"] = False
            _state["finished_at"] = utcnow().isoformat()
            _state_lock.release()

    threading.Thread(target=_run, daemon=True).start()
    return True


def _record(db: Session, url: str, status: str, **fields) -> None:
    row = db.query(CrawlRecord).filter(CrawlRecord.url == url[:700]).one_or_none()
    if row is None:
        row = CrawlRecord(url=url[:700], status=status)
        db.add(row)
    row.status = status
    row.fetched_at = utcnow()
    for key, value in fields.items():
        setattr(row, key, value)
    db.commit()


def register_known_sites(db: Session) -> None:
    for site in OFFICIAL_SITES:
        row = db.query(OfficialSite).filter(OfficialSite.url == site["url"]).one_or_none()
        if row is None:
            db.add(OfficialSite(name=site["name"], url=site["url"], category=site["category"], parent=site["parent"]))
        else:
            row.name = site["name"]
            row.category = site["category"]
            row.parent = site["parent"]
    db.commit()


def refresh_site_counts(db: Session) -> None:
    for site in db.query(OfficialSite).all():
        host = urlparse(site.url).hostname or ""
        indexed = (
            db.query(Document)
            .filter(Document.source_url.contains(host), Document.status == "processed")
            .count()
        )
        failed = (
            db.query(CrawlRecord)
            .filter(CrawlRecord.url.contains(host), CrawlRecord.status.in_(("failed", "needs_render")))
            .count()
        )
        site.pages_indexed = indexed
        site.last_crawled = utcnow()
        if indexed:
            site.status = "indexed"
            site.error = None
        elif failed:
            site.status = "unavailable"
            site.error = "Pages from this host could not be fetched or had no readable text."
    db.commit()


def _priority(url: str) -> int:
    lowered = url.lower()
    return 0 if any(word in lowered for word in _PRIORITY) else 1


def crawl_official_sites(
    db: Session,
    *,
    client: httpx.Client | None = None,
    seeds: list[str] | None = None,
    max_pages: int = 25,
    max_pdfs: int = 6,
    owner_id: int | None = None,
    pause_seconds: float = 0.4,
) -> dict:
    register_known_sites(db)
    owns_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=25.0,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
            verify=ssl.create_default_context(),
        )
    robots_cache: dict[str, list[str]] = {}
    queue: deque[tuple[int, str]] = deque()
    for seed in seeds or list(SEED_URLS):
        queue.append((0, seed))
    seen: set[str] = set()
    pages = 0
    pdfs = 0
    indexed = 0
    unchanged = 0
    failed = 0
    try:
        while queue and (pages < max_pages or pdfs < max_pdfs):
            depth, url = queue.popleft()
            if url in seen or not host_allowed(url) or _SKIP.search(url):
                if url not in seen and not host_allowed(url):
                    _record(db, url, "skipped_off_allowlist")
                seen.add(url)
                continue
            seen.add(url)
            if not _robots_allow(client, robots_cache, url):
                _record(db, url, "skipped_robots")
                continue
            is_pdf = url.lower().split("?")[0].endswith(".pdf")
            if is_pdf and not any(word in url.lower() for word in _USEFUL_PDF):
                _record(db, url, "skipped_low_value", error="PDF path is outside the facility and regulation set for this run.")
                continue
            if is_pdf and pdfs >= max_pdfs:
                continue
            if not is_pdf and pages >= max_pages:
                continue
            if pause_seconds:
                time.sleep(pause_seconds)
            try:
                response = client.get(url)
            except httpx.HTTPError as exc:
                failed += 1
                _record(db, url, "failed", error=type(exc).__name__, http_status=None)
                logger.warning("Crawl fetch failed for %s: %s", url, type(exc).__name__)
                continue
            final_url = str(response.url)
            if not host_allowed(final_url):
                _record(db, url, "skipped_off_allowlist", http_status=response.status_code)
                continue
            if response.status_code >= 400:
                failed += 1
                _record(db, url, "failed", http_status=response.status_code, error=f"HTTP {response.status_code}")
                continue
            content_type = response.headers.get("content-type", "")
            if is_pdf or "pdf" in content_type.lower() or response.content.startswith(b"%PDF"):
                outcome = _store_pdf(db, response, final_url, owner_id)
                pdfs += 1
            else:
                outcome, discovered = _store_html(db, response, final_url, owner_id)
                pages += 1
                if depth < 2:
                    for link in sorted(set(discovered), key=_priority):
                        if not host_allowed(link):
                            _record(db, link, "skipped_off_allowlist")
                            continue
                        if _SKIP.search(link) or link in seen:
                            continue
                        queue.append((depth + 1, link))
            if outcome == "indexed":
                indexed += 1
            elif outcome == "unchanged":
                unchanged += 1
            elif outcome == "failed":
                failed += 1
            _state["indexed"] = indexed
            _state["failed"] = failed
        if indexed:
            rebuild_from_database(db)
        refresh_site_counts(db)
    finally:
        if owns_client:
            client.close()
    return {"indexed": indexed, "unchanged": unchanged, "failed": failed, "fetched": len(seen)}


def _robots_allow(client: httpx.Client, cache: dict[str, list[str]], url: str) -> bool:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in cache:
        try:
            response = client.get(origin + "/robots.txt")
            cache[origin] = disallowed_prefixes(response.text) if response.status_code == 200 else []
        except httpx.HTTPError:
            cache[origin] = []
            logger.warning("Could not read robots.txt for %s", origin)
    return path_allowed(parsed.path or "/", cache[origin])


def _store_pdf(db: Session, response: httpx.Response, url: str, owner_id: int | None) -> str:
    payload = response.content
    limit = get_settings().max_upload_mb * 1024 * 1024
    if len(payload) > limit:
        _record(db, url, "failed", http_status=response.status_code, error="PDF exceeds the upload limit")
        return "failed"
    title = urlparse(url).path.rsplit("/", 1)[-1] or "Official PDF"
    try:
        document = store_pdf(
            db,
            owner_id=owner_id,
            title=title[:200],
            category="Circular",
            description="Downloaded from an allowlisted official site.",
            original_filename=title[:255],
            payload=payload,
            source_url=url[:500],
            provenance="official_pdf",
            department=department_for(url),
            last_modified=response.headers.get("last-modified"),
            rebuild=False,
        )
    except DocumentProcessError as exc:
        status = "duplicate" if exc.status_code == 409 else "failed"
        _record(db, url, status, http_status=response.status_code, error=exc.message[:300], content_type="application/pdf")
        return "unchanged" if status == "duplicate" else "failed"
    _record(
        db,
        url,
        "indexed" if document.status == "processed" else document.status,
        title=document.title,
        document_id=document.id,
        content_hash=document.content_hash,
        http_status=response.status_code,
        content_type="application/pdf",
        error=None if document.status == "processed" else document.status_message,
    )
    return "indexed" if document.status == "processed" else "failed"


def _store_html(db: Session, response: httpx.Response, url: str, owner_id: int | None) -> tuple[str, list[str]]:
    html = response.text
    title, text, links = extract_html(html, url)
    slug = urlparse(url).path.strip("/").split("/")[-1].replace("-", " ")
    if slug and slug.lower() not in (title or "").lower():
        title = f"{slug} — {title}".strip()
    if looks_like_script_shell(html, text):
        _record(
            db,
            url,
            "needs_render",
            title=title or None,
            http_status=response.status_code,
            content_type="text/html",
            error="The page is a script shell and its text could not be extracted.",
        )
        return "failed", [link for link in links if host_allowed(link)]
    document, outcome = upsert_text_source(
        db,
        title=title or url,
        category="Other",
        text=text,
        source_url=url,
        provenance="official_webpage",
        document_type="official_webpage",
        department=department_for(url),
        last_modified=response.headers.get("last-modified"),
        owner_id=owner_id,
        rebuild=False,
    )
    _record(
        db,
        url,
        outcome if outcome != "extraction_failed" else "extraction_failed",
        title=document.title,
        document_id=document.id,
        content_hash=document.content_hash,
        http_status=response.status_code,
        content_type="text/html",
        error=None if outcome != "extraction_failed" else document.status_message,
    )
    return outcome, links
