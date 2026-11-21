"""Jack, forked for research: an evidence-only research agent.

This is the ODSC x Nebius Hackathon fork of Jack's core loop:

    gather sources -> build a numbered evidence pack -> answer ONLY from it

What changed from the jobsite version:
  - Source pool: live web results via Tavily (was: permissioned field memory)
  - Inference: Nebius Token Factory models (OpenAI-compatible API)
  - Voice: researcher-facing instead of crew-facing

What did NOT change (the Jack rules):
  - Every claim in an answer cites a source from the evidence pack, e.g. [2]
  - If the evidence does not answer the question, the agent says so
    explicitly ("Gap: ...") instead of filling the hole from memory
  - No source, no claim. Ever.

Standard library only, so it runs anywhere Python 3.10+ runs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from dataclasses import dataclass, field

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"
DEFAULT_NEBIUS_MODEL = "meta-llama/Llama-3.3-70B-Instruct"

SYSTEM_PROMPT = """You are a research agent built on Jack's evidence-first core.

Rules, in order:
1. Answer ONLY from the numbered evidence provided in the user message.
   Do not use prior knowledge. Do not browse. Do not guess.
2. Every factual claim must end with a citation to the evidence item that
   supports it, written like [1] or [2]. A claim without a citation is a bug.
3. If the evidence does not contain enough to answer the question, say
   exactly what is missing, starting with "Gap:". A partial answer with an
   explicit gap is better than a complete answer with an invented claim.
4. Quote figures, dates, and names exactly as the evidence gives them.
5. End with a "Sources" list repeating the numbers you actually used.
"""


@dataclass
class Source:
    index: int
    title: str
    url: str
    content: str
    published_date: str = ""

    def evidence_line(self) -> str:
        date = f" ({self.published_date})" if self.published_date else ""
        return f"[{self.index}] {self.title}{date}\nURL: {self.url}\n{self.content}"


@dataclass
class Answer:
    text: str
    sources: list[Source] = field(default_factory=list)
    citations_valid: bool = True
    problems: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# HTTP helpers (stdlib only)
# --------------------------------------------------------------------------

def _post_json(url: str, payload: dict, headers: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


# --------------------------------------------------------------------------
# Step 1: gather (Tavily live web results)
# --------------------------------------------------------------------------

def gather(question: str, api_key: str, max_results: int = 5) -> list[Source]:
    """Search the live web for evidence. Returns numbered sources."""
    data = _post_json(
        TAVILY_SEARCH_URL,
        {
            "api_key": api_key,
            "query": question,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        },
        headers={},
    )
    sources: list[Source] = []
    for i, r in enumerate(data.get("results", []), start=1):
        sources.append(
            Source(
                index=i,
                title=(r.get("title") or "Untitled").strip(),
                url=(r.get("url") or "").strip(),
                content=(r.get("content") or "").strip(),
                published_date=(r.get("published_date") or "") or "",
            )
        )
    return [s for s in sources if s.url and s.content]


# --------------------------------------------------------------------------
# Step 2 + 3: answer only from the evidence pack (Nebius Token Factory)
# --------------------------------------------------------------------------

def build_evidence_block(sources: list[Source]) -> str:
    return "\n\n".join(s.evidence_line() for s in sources)


def _chat(messages: list[dict], api_key: str, model: str, base_url: str) -> str:
    data = _post_json(
        f"{base_url.rstrip('/')}/chat/completions",
        {"model": model, "messages": messages, "temperature": 0.1},
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return data["choices"][0]["message"]["content"].strip()


CITATION_RE = re.compile(r"\[(\d+)\]")


def validate_citations(text: str, sources: list[Source]) -> list[str]:
    """Every citation must point at a real source; with sources present,
    an answer with zero citations has broken the core rule."""
    problems: list[str] = []
    valid = {s.index for s in sources}
    cited = {int(n) for n in CITATION_RE.findall(text)}
    for n in sorted(cited - valid):
        problems.append(f"Citation [{n}] has no matching source.")
    if sources and not cited and not text.startswith("Gap:"):
        problems.append("Answer makes claims but cites no sources.")
    return problems


def answer(
    question: str,
    sources: list[Source],
    api_key: str,
    model: str = DEFAULT_NEBIUS_MODEL,
    base_url: str = DEFAULT_NEBIUS_BASE_URL,
) -> Answer:
    """Answer strictly from the evidence pack, or admit the gap."""
    if not sources:
        return Answer(
            text=(
                "Gap: no evidence was gathered for this question, so there is "
                "nothing to answer from. Jack's rule is no source, no claim."
            ),
            sources=[],
        )
    user_msg = (
        f"Question: {question}\n\nEvidence pack:\n{build_evidence_block(sources)}"
    )
    text = _chat(
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        api_key=api_key,
        model=model,
        base_url=base_url,
    )
    problems = validate_citations(text, sources)
    return Answer(
        text=text,
        sources=sources,
        citations_valid=not problems,
        problems=problems,
    )


# --------------------------------------------------------------------------
# Fixture mode: same plumbing, offline evidence (for tests and demos
# without keys). The composer is extractive on purpose: it can only
# restate what the fixture evidence says, with citations attached.
# --------------------------------------------------------------------------

def load_fixture(path: str) -> list[Source]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return [
        Source(
            index=i,
            title=(r.get("title") or "Untitled").strip(),
            url=(r.get("url") or "").strip(),
            content=(r.get("content") or "").strip(),
            published_date=(r.get("published_date") or "") or "",
        )
        for i, r in enumerate(raw, start=1)
    ]


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)
    return parts[0].strip()


def compose_extractive(question: str, sources: list[Source]) -> Answer:
    """Deterministic offline answerer: restates fixture evidence only."""
    usable = [s for s in sources if s.content]
    if not usable:
        return Answer(
            text="Gap: the fixture evidence is empty, so there is nothing to answer from.",
            sources=sources,
        )
    lines = [f"Question: {question}", ""]
    for s in usable[:3]:
        lines.append(f"{_first_sentence(s.content)} [{s.index}]")
    lines.append("")
    lines.append("Sources:")
    for s in usable[:3]:
        lines.append(f"[{s.index}] {s.title} — {s.url}")
    text = "\n".join(lines)
    problems = validate_citations(text, sources)
    return Answer(
        text=text,
        sources=sources,
        citations_valid=not problems,
        problems=problems,
    )


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evidence-only research agent (Jack fork).")
    parser.add_argument("question", help="The research question to answer from live evidence.")
    parser.add_argument("--fixture", help="Offline mode: load evidence from a JSON fixture file.")
    parser.add_argument("--max-results", type=int, default=5)
    args = parser.parse_args(argv)

    _load_dotenv()

    if args.fixture:
        sources = load_fixture(args.fixture)
        result = compose_extractive(args.question, sources)
        print(result.text)
        if result.problems:
            print("\nCitation problems: " + "; ".join(result.problems), file=sys.stderr)
            return 1
        return 0

    tavily_key = os.environ.get("TAVILY_API_KEY", "")
    nebius_key = os.environ.get("NEBIUS_API_KEY", "")
    missing = [
        name
        for name, val in (("TAVILY_API_KEY", tavily_key), ("NEBIUS_API_KEY", nebius_key))
        if not val
    ]
    if missing:
        print(
            "Gap: live evidence gathering is not configured — missing "
            + ", ".join(missing)
            + ". Copy .env.example to .env, add your own keys, and rerun. "
            "Until then there are no sources, so there is no answer."
        )
        return 2

    sources = gather(args.question, tavily_key, max_results=args.max_results)
    result = answer(
        args.question,
        sources,
        api_key=nebius_key,
        model=os.environ.get("NEBIUS_MODEL", DEFAULT_NEBIUS_MODEL),
        base_url=os.environ.get("NEBIUS_BASE_URL", DEFAULT_NEBIUS_BASE_URL),
    )
    print(result.text)
    if result.problems:
        print("\nCitation problems: " + "; ".join(result.problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
