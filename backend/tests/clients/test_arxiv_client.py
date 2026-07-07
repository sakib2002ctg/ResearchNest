import httpx

from app.clients.arxiv_client import ArxivClient
from app.schemas.external_paper import ExternalPaperSearchResponse


class MockResponse:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        pass


class MockAuthor:
    def __init__(self, name: str):
        self.name = name


class MockEntry:
    def __init__(self):
        self.title = "Attention Is All You Need"
        self.summary = "Transformer architecture"
        self.link = "https://arxiv.org/abs/1706.03762"
        self.authors = [
            MockAuthor("Ashish Vaswani"),
        ]


class MockFeed:
    def __init__(self):
        self.entries = [
            MockEntry(),
        ]


def test_search_returns_response(monkeypatch):
    def mock_get(*args, **kwargs):
        return MockResponse("<xml></xml>")

    def mock_parse(text):
        return MockFeed()

    monkeypatch.setattr(httpx, "get", mock_get)

    import feedparser

    monkeypatch.setattr(feedparser, "parse", mock_parse)

    client = ArxivClient()

    result = client.search("transformer")

    assert isinstance(
        result,
        ExternalPaperSearchResponse,
    )

    assert result.total == 1


def test_search_returns_paper(monkeypatch):
    def mock_get(*args, **kwargs):
        return MockResponse("<xml></xml>")

    def mock_parse(text):
        return MockFeed()

    monkeypatch.setattr(httpx, "get", mock_get)

    import feedparser

    monkeypatch.setattr(feedparser, "parse", mock_parse)

    client = ArxivClient()

    result = client.search("transformer")

    paper = result.papers[0]

    assert paper.title == "Attention Is All You Need"
    assert paper.abstract == "Transformer architecture"
    assert paper.source == "arXiv"


def test_search_returns_authors(monkeypatch):
    def mock_get(*args, **kwargs):
        return MockResponse("<xml></xml>")

    def mock_parse(text):
        return MockFeed()

    monkeypatch.setattr(httpx, "get", mock_get)

    import feedparser

    monkeypatch.setattr(feedparser, "parse", mock_parse)

    client = ArxivClient()

    result = client.search("transformer")

    assert result.papers[0].authors == [
        "Ashish Vaswani"
    ]


def test_search_empty_results(monkeypatch):
    class EmptyFeed:
        entries = []

    def mock_get(*args, **kwargs):
        return MockResponse("<xml></xml>")

    def mock_parse(text):
        return EmptyFeed()

    monkeypatch.setattr(httpx, "get", mock_get)

    import feedparser

    monkeypatch.setattr(feedparser, "parse", mock_parse)

    client = ArxivClient()

    result = client.search("unknown-paper")

    assert result.total == 0
    assert result.papers == []


def test_http_error(monkeypatch):
    def mock_get(*args, **kwargs):
        raise httpx.HTTPStatusError(
            "Server Error",
            request=None,
            response=None,
        )

    monkeypatch.setattr(httpx, "get", mock_get)

    client = ArxivClient()

    try:
        client.search("transformer")
        assert False
    except httpx.HTTPStatusError:
        assert True