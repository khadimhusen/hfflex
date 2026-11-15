"""Rich text for the agenda and minutes (written in the browser's editor).

The editor produces HTML, and other people read it, so nothing the user (or a
pasted web page) sends is trusted: `clean_html` keeps a short list of
formatting tags and throws away everything else -- scripts, styles, event
handlers, inline styles, unsafe links. It needs no outside library.

Older meetings were typed as plain text; `rich_html` shows those correctly too.
`html_to_flowables` turns the same HTML into PDF paragraphs."""
import re
from html import escape, unescape
from html.parser import HTMLParser

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph

ALLOWED_TAGS = {
    'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'del', 'br', 'p', 'div', 'ul', 'ol', 'li',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre', 'code', 'a', 'font',
}
VOID_TAGS = {'br'}
# Tags whose contents are dropped along with the tag.
DROP_WITH_CONTENT = {'script', 'style', 'iframe', 'object', 'embed', 'template', 'noscript', 'textarea', 'title',
                     'head', 'svg', 'math', 'applet', 'frameset', 'select'}
SAFE_LINK = re.compile(r'^(https?:|mailto:|tel:)', re.IGNORECASE)
LOOKS_LIKE_HTML = re.compile(
    r'<\s*/?\s*(p|div|br|b|strong|i|em|u|s|strike|del|ul|ol|li|h[1-6]|blockquote|pre|code|a|font)\b[^>]*>', re.IGNORECASE)


def _safe_href(value):
    # Browsers ignore tabs, newlines and spaces inside a scheme ("java\tscript:"), so remove them first.
    compact = re.sub(r'[\x00-\x20]+', '', value or '')
    return compact if SAFE_LINK.match(compact) else None


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.open = []              # allowed tags currently open, innermost last
        self.skipping = 0           # inside a dropped tag such as <script>

    def handle_starttag(self, tag, attrs):
        if tag in DROP_WITH_CONTENT:
            self.skipping += 1
            return
        if self.skipping or tag not in ALLOWED_TAGS:
            return
        if tag == 'a':
            href = _safe_href(dict(attrs).get('href'))
            self.out.append(f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">'
                            if href else '<a>')
        elif tag == 'font':
            # only the size survives (the editor's 1-7 scale); colours, faces and the rest are dropped
            size = (dict(attrs).get('size') or '').strip()
            self.out.append(f'<font size="{size}">' if re.fullmatch(r'[1-7]', size) else '<font>')
        elif tag in VOID_TAGS:
            self.out.append(f'<{tag}>')
            return
        else:
            self.out.append(f'<{tag}>')
        self.open.append(tag)

    def handle_startendtag(self, tag, attrs):
        if tag in VOID_TAGS:
            self.handle_starttag(tag, attrs)
        # any other self-closing tag (<script/>, <div/>) opens nothing

    def handle_endtag(self, tag):
        if tag in DROP_WITH_CONTENT:
            self.skipping = max(0, self.skipping - 1)
            return
        if self.skipping or tag not in self.open:
            return
        while self.open:                       # close anything left open inside it, then it
            top = self.open.pop()
            self.out.append(f'</{top}>')
            if top == tag:
                break

    def handle_data(self, data):
        if not self.skipping:
            self.out.append(escape(data, quote=False))

    def result(self):
        while self.open:
            self.out.append(f'</{self.open.pop()}>')
        return ''.join(self.out)


def clean_html(value):
    parser = _Cleaner()
    parser.feed(value or '')
    parser.close()
    return parser.result()


def plain_text(html):
    """The words in some HTML, tags removed (for "is it empty?" checks)."""
    return unescape(re.sub(r'<[^>]*>', ' ', html or '')).replace('\xa0', ' ').strip()


def is_blank(value):
    return not plain_text(value)


def rich_html(value):
    """Safe HTML for display. '' when there is nothing written; plain text
    from before the editor existed keeps its line breaks."""
    if is_blank(value):
        return ''
    if not LOOKS_LIKE_HTML.search(value):
        # One <div> per line, the shape the editor itself produces (so the result always has tags
        # and is never mistaken for plain text again).
        return ''.join(f'<div>{escape(line, quote=False) or "<br>"}</div>' for line in value.strip().splitlines())
    return clean_html(value)


# ---- PDF ------------------------------------------------------------------------

_INLINE = {'b': 'b', 'strong': 'b', 'i': 'i', 'em': 'i', 'u': 'u', 's': 'strike', 'strike': 'strike', 'del': 'strike'}
_BLOCKS = {'p', 'div', 'li', 'blockquote', 'pre', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}
# The editor's sizes 1-7 (browser scale, 3 is normal) as PDF points, relative to 9.5pt body text.
_FONT_POINTS = {'1': 6.5, '2': 8, '3': 9.5, '4': 11, '5': 14.5, '6': 19, '7': 28}
_HEADING_SIZE = {'h1': 14, 'h2': 12.5, 'h3': 11, 'h4': 10.5, 'h5': 10, 'h6': 9.5}


class _Blocks(HTMLParser):
    """Cleaned HTML -> a list of (markup, kind, depth, bullet): one entry per
    paragraph, list item or heading, in the PDF library's inline markup."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks = []
        self.inline = []            # PDF-markup tags open right now, e.g. ['b', 'i']
        self.cur = []
        self.has_text = False
        self.kind = 'p'
        self.lists = []             # [kind, count] for each list we are inside
        self.bullet = None

    def _reopen(self):
        self.cur = [f'<{t}>' for t in self.inline]

    def flush(self):
        if self.has_text:
            markup = ''.join(self.cur) + ''.join(f'</{t}>' for t in reversed(self.inline))
            self.blocks.append((markup, self.kind, len(self.lists), self.bullet))
            self.bullet = None
        self.has_text = False
        self.kind = 'p'
        self._reopen()

    def handle_starttag(self, tag, attrs):
        if tag in ('ul', 'ol'):
            self.flush()
            self.lists.append([tag, 0])
        elif tag in _BLOCKS:
            self.flush()
            self.kind = tag
            if tag == 'li' and self.lists:
                self.lists[-1][1] += 1
                kind, count = self.lists[-1]
                self.bullet = f'{count}.' if kind == 'ol' else '•'
        elif tag == 'br':
            self.cur.append('<br/>')          # a lone <br> is not text, so it makes no paragraph by itself
        elif tag in _INLINE:
            self.inline.append(_INLINE[tag])
            self.cur.append(f'<{_INLINE[tag]}>')
        elif tag == 'font':
            size = _FONT_POINTS.get(dict(attrs).get('size'))
            self.inline.append('font')
            self.cur.append(f'<font size="{size}">' if size else '<font>')
        elif tag == 'code':
            self.inline.append('font')
            self.cur.append('<font face="Courier">')
        elif tag == 'a':
            href = dict(attrs).get('href')
            self.inline.append('a' if href else 'font')
            self.cur.append(f'<a href="{escape(href, quote=True)}" color="#1a56a8">' if href else '<font>')

    def handle_endtag(self, tag):
        if tag in ('ul', 'ol'):
            self.flush()
            if self.lists:
                self.lists.pop()
        elif tag in _BLOCKS:
            self.flush()
        elif tag in _INLINE or tag in ('code', 'a', 'font'):
            if self.inline:
                closed = self.inline.pop()
                self.cur.append(f'</{closed}>')

    def handle_data(self, data):
        text = re.sub(r'\s+', ' ', data)
        if text.strip():
            self.has_text = True
        if text:
            self.cur.append(escape(text, quote=False))

    def close(self):
        super().close()
        self.flush()


def html_to_flowables(value, body, bold_font='Helvetica-Bold'):
    """Agenda or minutes (HTML or old plain text) -> PDF paragraphs. `body` is
    the paragraph style to build on."""
    html = rich_html(value)
    if not html:
        return []
    parser = _Blocks()
    parser.feed(html)
    parser.close()
    # Text sitting loose between blocks is flushed by close(); a leading <br> alone yields nothing.
    flowables = []
    for markup, kind, depth, bullet in parser.blocks:
        markup = re.sub(r'^(<br/>)+|(<br/>)+$', '', markup.strip())
        style_args = {'parent': body, 'spaceAfter': 2, 'autoLeading': 'max'}     # lines grow with bigger text
        if kind in _HEADING_SIZE:
            style_args.update(fontName=bold_font, fontSize=_HEADING_SIZE[kind], leading=_HEADING_SIZE[kind] + 3,
                              spaceBefore=3)
        if kind == 'blockquote':
            style_args.update(leftIndent=8 * mm, textColor=colors.HexColor('#555555'))
        if kind == 'pre':
            style_args.update(fontName='Courier', fontSize=8.5, leading=11)
        if depth:
            indent = 6 * mm * depth
            style_args.update(leftIndent=style_args.get('leftIndent', 0) + indent, bulletIndent=indent - 4 * mm,
                              spaceAfter=1)
        style = ParagraphStyle(f'rt-{kind}-{depth}', **style_args)
        flowables.append(Paragraph(markup, style, bulletText=bullet) if bullet else Paragraph(markup, style))
    return flowables
