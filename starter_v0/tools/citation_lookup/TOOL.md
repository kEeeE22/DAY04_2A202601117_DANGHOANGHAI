---
name: citation_lookup
track: bonus
kind: live_api
provider: Semantic Scholar API
requires_env: [SEMANTIC_SCHOLAR_API_KEY]
inputs: [title, doi, arxiv_id]
outputs: [title, authors, venue, year, doi, citation_count, bibtex, references]
side_effect: false
---

# citation_lookup

Retrieves citation metadata for a research paper using the Semantic Scholar API.

The tool accepts a paper title, DOI, or arXiv ID and returns structured citation
information including authors, publication venue, publication year, citation
count, DOI, BibTeX entry (if available), and referenced papers.

If multiple papers match the query, the most relevant result is returned.
The tool is read-only and performs no external side effects.