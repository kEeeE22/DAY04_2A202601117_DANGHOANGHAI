from __future__ import annotations

import re
import time
from typing import Any

import requests

from tools._shared import TIMEOUT, err


# ---------------------------------------------------------------------------
# OpenAlex API helpers
# ---------------------------------------------------------------------------
OPENALEX_BASE = "https://api.openalex.org"
_POLITE_EMAIL = "research-agent@ai20k.local"  # polite pool: faster rate limits


def _headers() -> dict[str, str]:
    return {"User-Agent": f"AI20k-Day04-Research-Agent/1.0 (mailto:{_POLITE_EMAIL})"}


def _get(url: str, *, params: dict[str, Any] | None = None) -> requests.Response:
    """GET with simple retry on 429."""
    for attempt in range(3):
        resp = requests.get(url, params=params, headers=_headers(), timeout=TIMEOUT)
        if resp.status_code != 429:
            return resp
        time.sleep(2 * (attempt + 1))
    return resp  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Input normalisation helpers
# ---------------------------------------------------------------------------
_ARXIV_RE = re.compile(r"(\d{4}\.\d{4,5})(?:v\d+)?")
_DOI_RE = re.compile(r"10\.\d{4,}/\S+")


def _clean_arxiv_id(value: str) -> str:
    m = _ARXIV_RE.search(value or "")
    return m.group(1) if m else ""


def _clean_doi(value: str) -> str:
    """Return bare DOI (no https://doi.org/ prefix)."""
    doi = (value or "").strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    return doi.strip()


# ---------------------------------------------------------------------------
# Work -> structured result
# ---------------------------------------------------------------------------

def _authorships_to_names(authorships: list[dict]) -> list[str]:
    return [a.get("author", {}).get("display_name", "") for a in authorships if a.get("author")]


def _venue(work: dict) -> str:
    loc = work.get("primary_location") or {}
    src = loc.get("source") or {}
    return src.get("display_name") or ""


def _make_bibtex(work: dict, authors: list[str]) -> str:
    """Build a minimal BibTeX entry from OpenAlex metadata."""
    title = work.get("title") or ""
    year = work.get("publication_year") or ""
    doi = (work.get("doi") or "").replace("https://doi.org/", "")
    venue = _venue(work)

    # Derive a citation key like Author2024
    first_author = ""
    if authors:
        parts = authors[0].split()
        first_author = parts[-1] if parts else ""
    key = f"{first_author}{year}" if first_author else f"ref{year}"

    author_str = " and ".join(authors[:8])

    work_type = work.get("type", "article")
    if work_type in ("article", "review", "preprint"):
        bib_type = "article"
        venue_field = f"  journal = {{{venue}}},\n" if venue else ""
    elif work_type in ("proceedings-article", "conference-paper"):
        bib_type = "inproceedings"
        venue_field = f"  booktitle = {{{venue}}},\n" if venue else ""
    else:
        bib_type = "misc"
        venue_field = f"  howpublished = {{{venue}}},\n" if venue else ""

    doi_field = f"  doi = {{{doi}}},\n" if doi else ""

    return (
        f"@{bib_type}{{{key},\n"
        f"  title = {{{title}}},\n"
        f"  author = {{{author_str}}},\n"
        f"  year = {{{year}}},\n"
        + venue_field
        + doi_field
        + "}"
    )


def _fetch_ref_titles(ref_ids: list[str], max_refs: int = 20) -> list[dict[str, str]]:
    """Batch-fetch titles of up to *max_refs* referenced OpenAlex work IDs."""
    ids = ref_ids[:max_refs]
    if not ids:
        return []
    # Extract short IDs like W1234567 from full URLs
    short_ids = [u.split("/")[-1] for u in ids]
    filter_str = "|".join(short_ids)
    try:
        resp = _get(
            f"{OPENALEX_BASE}/works",
            params={
                "filter": f"openalex:{filter_str}",
                "per-page": max_refs,
                "select": "id,title,doi,publication_year",
            },
        )
        if resp.status_code != 200:
            return [{"id": u} for u in ids]
        results = resp.json().get("results", [])
        return [
            {
                "title": r.get("title") or "",
                "doi": (r.get("doi") or "").replace("https://doi.org/", ""),
                "year": r.get("publication_year"),
            }
            for r in results
        ]
    except Exception:
        return [{"id": u} for u in ids]


def _work_to_result(work: dict, *, fetch_refs: bool = True) -> dict[str, Any]:
    authors = _authorships_to_names(work.get("authorships", []))
    ref_ids = work.get("referenced_works", [])
    references = _fetch_ref_titles(ref_ids) if fetch_refs else [{"id": u} for u in ref_ids[:20]]

    return {
        "tool": "citation_lookup",
        "title": work.get("title") or work.get("display_name") or "",
        "authors": authors,
        "venue": _venue(work),
        "year": work.get("publication_year"),
        "doi": (work.get("doi") or "").replace("https://doi.org/", ""),
        "openalex_id": work.get("id", ""),
        "citation_count": work.get("cited_by_count"),
        "referenced_works_count": len(ref_ids),
        "references": references,
        "bibtex": _make_bibtex(work, authors),
        "source": "openalex.org",
    }


# ---------------------------------------------------------------------------
# Lookup strategies
# ---------------------------------------------------------------------------

def _lookup_by_doi(doi: str) -> dict | None:
    """Try direct DOI endpoint (fast path)."""
    full_doi = f"https://doi.org/{doi}"
    resp = _get(f"{OPENALEX_BASE}/works/{full_doi}")
    if resp.status_code == 200:
        try:
            return resp.json()
        except Exception:
            pass
    # Fallback: filter
    resp2 = _get(
        f"{OPENALEX_BASE}/works",
        params={"filter": f"doi:{full_doi}", "per-page": 1},
    )
    if resp2.status_code == 200:
        results = resp2.json().get("results", [])
        if results:
            return results[0]
    return None


def _lookup_by_arxiv(arxiv_id: str) -> dict | None:
    """Resolve arXiv ID via the 10.48550/arxiv.{id} DOI convention."""
    doi = f"10.48550/arxiv.{arxiv_id}"
    work = _lookup_by_doi(doi)
    if work:
        return work
    # Some arXiv papers don't have that DOI in OpenAlex; fall back to title search
    return None


def _lookup_by_title(title: str) -> dict | None:
    """Search by title, return the most-cited match."""
    resp = _get(
        f"{OPENALEX_BASE}/works",
        params={
            "filter": f"title.search:{title}",
            "sort": "cited_by_count:desc",
            "per-page": 5,
        },
    )
    if resp.status_code != 200:
        return None
    results = resp.json().get("results", [])
    if results:
        return results[0]
    return None


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def citation_lookup(
    title: str = "",
    doi: str = "",
    arxiv_id: str = "",
) -> dict[str, Any]:
    """
    Retrieve citation metadata for a research paper using the OpenAlex API.

    Priority: doi > arxiv_id > title.
    Returns structured metadata including authors, venue, year, citation count,
    BibTeX entry, and referenced papers.
    """
    try:
        work: dict | None = None

        # 1. DOI
        clean_doi = _clean_doi(doi)
        if clean_doi:
            work = _lookup_by_doi(clean_doi)

        # 2. arXiv ID
        if work is None:
            clean_arxiv = _clean_arxiv_id(arxiv_id)
            if clean_arxiv:
                work = _lookup_by_arxiv(clean_arxiv)

        # 3. Title search
        if work is None and title:
            work = _lookup_by_title(title.strip())

        if work is None:
            return {
                "tool": "citation_lookup",
                "error": "not_found",
                "message": "No matching paper found in OpenAlex.",
                "inputs": {"title": title, "doi": doi, "arxiv_id": arxiv_id},
            }

        return _work_to_result(work)

    except Exception as exc:
        return err("citation_lookup", exc)
