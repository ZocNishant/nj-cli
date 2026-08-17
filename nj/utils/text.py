from __future__ import annotations

import re


def clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, max_chars: int = 2500) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


# Sequential str.replace() over these corrupts its own output: escaping "\" to
# "\textbackslash{}" injects braces that the later "{" and "}" rules escape
# again. One regex pass over the original string avoids that.
_LATEX_SPECIALS = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}
_LATEX_RE = re.compile("|".join(re.escape(c) for c in _LATEX_SPECIALS))


def escape_latex(text: str) -> str:
    r"""Escape LaTeX metacharacters in untrusted content.

    Everything reaching the .tex template must pass through here. CV bullets are
    written by the model from scraped job descriptions, so an unescaped bullet is
    an injection path into the document: control sequences such as \input can
    pull local files into the PDF that then gets emailed out.
    """
    if not text:
        return ""
    return _LATEX_RE.sub(lambda m: _LATEX_SPECIALS[m.group()], str(text))
