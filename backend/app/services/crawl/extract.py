"""Turn a public HTML page into text and followable links."""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class PageText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts: list[str] = []
        self.links: list[str] = []
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        attributes = {key.lower(): value for key, value in attrs}
        if tag in {"script", "style", "noscript", "svg", "nav", "footer"}:
            self.skip += 1
        if tag == "title":
            self._in_title = True
        href = attributes.get("href")
        if tag == "a" and href:
            self.links.append(href)
        if tag in {"h1", "h2", "h3"}:
            self.parts.append(f"\nHeading: ")
        if tag == "li":
            self.parts.append("\n- ")
        if tag in {"p", "tr", "br", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg", "nav", "footer"} and self.skip:
            self.skip -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title_parts.append(data)
        if self.skip:
            return
        text = " ".join(data.split())
        if text:
            self.parts.append(text + " ")


def extract_html(html: str, page_url: str) -> tuple[str, str, list[str]]:
    parser = PageText()
    parser.feed(html or "")
    title = " ".join(" ".join(parser.title_parts).split())[:300]
    text = "\n".join(line.strip() for line in "".join(parser.parts).splitlines() if line.strip())
    links = []
    for href in parser.links:
        absolute = urljoin(page_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        links.append(absolute.split("#")[0])
    return title, text, links


def looks_like_script_shell(html: str, text: str) -> bool:
    """A JavaScript application shell has almost no readable text."""
    if len(" ".join(text.split())) >= 180:
        return False
    lowered = (html or "").lower()
    return 'id="root"' in lowered or "id='root'" in lowered or "react" in lowered
