# -*- coding: utf-8 -*-
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Site:
    name: str
    url: str
    pick: str  # top or bottom
    retry: int = 2
    cache_bust: bool = False
    confirm: bool = False
    api_url: str | None = None
    name_anchors: tuple[str, ...] = field(default_factory=tuple)
    section_keywords: tuple[str, ...] = field(default_factory=tuple)
    document_sources: tuple[str, ...] = field(default_factory=tuple)
    custom_parser: str | None = None
    section_scope: bool = False
    allow_insecure: bool = False

class ArticleRecordError(ValueError):
    pass

class ArticlePayloadUnavailableError(ArticleRecordError):
    pass

class ArticleDocumentList(list[str]):
    def __init__(self) -> None:
        super().__init__()
        self.article_audit: list[dict[str, object]] = []
        self.document_metadata: list[dict[str, object]] = []

    def append_document(self, text: str, metadata: dict[str, object] | None = None) -> None:
        self.append(text)
        self.document_metadata.append(dict(metadata or {}))

@dataclass(frozen=True)
class Candidate:
    issue: int
    issue_text: str
    value: str
    title: str
    snippet: str
    score: int
    order: int
    position: int
    source_url: str | None = None
    document_type: str = "unknown"
    document_id: str | None = None
    block_id: str | None = None
    anchor: str | None = None
    raw_block: str = ""
    source_title: str = ""

@dataclass(frozen=True)
class SiteResult:
    index: int
    site: Site
    matches: list[Candidate]
    fail_line: str | None
    status: str
    issue_reasons: dict[int, str] = field(default_factory=dict)
    cache_record: dict[str, object] | None = None
