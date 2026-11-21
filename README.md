# Jack, Forked for Research

An evidence-only research agent, built for the **ODSC × Nebius Hackathon**
("Build a research agent that brings its sources", submission due
November 20, 2026).

This is a fork of **Jack** — Torch Labs' field-intelligence platform for
skilled-trades crews — with its setting swapped from the jobsite to the open
web. Jack's core loop survives the fork intact:

```
gather sources  →  build a numbered evidence pack  →  answer ONLY from it
```

## What changed, what didn't

| Layer | Jack (jobsite) | This fork (research) |
|---|---|---|
| Source pool | Permissioned field knowledge ("Living Memory") | Live web results via **Tavily** |
| Inference | Production model stack | **Nebius Token Factory** models (OpenAI-compatible API) |
| Voice | Crew-facing, jobsite plain | Researcher-facing |
| Evidence rules | Cited, source-backed answers; admit gaps | **Unchanged. Non-negotiable.** |

## The evidence rules

1. **No source, no claim.** The agent answers only from the evidence pack it
   gathered for that question — never from the model's prior knowledge.
2. **Every claim carries a citation**, like `[2]`, pointing at a numbered
   item in the evidence pack. Answers are machine-checked: a citation that
   doesn't match a real source, or a claim with no citation, fails the run.
3. **Gaps are admitted out loud.** If the evidence doesn't answer the
   question, the answer starts with `Gap:` and says exactly what's missing.
   A partial answer with an honest gap beats a smooth answer with an
   invented claim — every time.

## Setup

You need two accounts, both free to start, both yours to create:

- **Tavily** — live web search: https://tavily.com
- **Nebius Token Factory** — inference: https://tokenfactory.nebius.com

```bash
cp .env.example .env
# edit .env and add your own keys (never commit .env)
```

Keys are read from the environment (`.env` supported). They are never
printed, logged, or committed.

## Run it

```bash
# Live mode: gather real evidence, then answer from it
python3 research_agent.py "What changed in the latest Nebius Token Factory model lineup?"

# Offline plumbing test (no keys needed): answers extractively from a
# small fixture evidence pack, with the same citation rules enforced
python3 research_agent.py "What does the hackathon ask participants to build?" \
    --fixture tests/fixture_sources.json

# Tests (offline, no keys, no network)
python3 -m unittest discover -s tests -v
```

Standard library only. Python 3.10+. No dependencies to install.

## How it works

- `gather()` sends the question to Tavily and numbers the results — that
  numbering is the evidence pack's backbone; citations refer to it.
- `answer()` hands the question and the evidence pack to a Token Factory
  model under a system prompt that forbids outside knowledge, requires a
  citation per claim, and requires an explicit `Gap:` when the evidence
  runs out.
- `validate_citations()` then checks the answer mechanically: every `[n]`
  must resolve to a real source, and an answer built on sources must cite
  at least one.

## Layout

```
research_agent.py          the whole agent: gather → evidence → answer → verify
tests/test_agent.py        offline tests for the evidence rules
tests/fixture_sources.json a tiny frozen evidence pack for offline runs
DEMO.md                    the submission demo, walked end to end
.env.example               the two keys you bring
```

## Status

Runnable prototype for a hackathon submission — not a product. The
offline path (fixture mode + tests) runs anywhere, keys or not.

**Verified live, November 20, 2026** — real Tavily search + real Nebius
Token Factory inference (model `Qwen/Qwen3-235B-A22B-Instruct-2507`):

```
$ python3 research_agent.py "What is the Nebius Token Factory API base URL, and how is it authorized?"
The Nebius Token Factory API base URL is `https://tokenfactory.nebius.com/v1` [2].
It is authorized by including an API key in the `Authorization` header using
the Bearer scheme, formatted as `Authorization: Bearer <your API key>` [3].

$ python3 research_agent.py "What is the exact internal codename of Nebius Token Factory's unreleased 2027 flagship model?"
Gap: The evidence provided does not contain the internal codename of
Nebius Token Factory's unreleased 2027 flagship model.
```

First run: answered from evidence gathered seconds earlier, citations
machine-validated. Second run: the evidence ran out, so the agent said
so — that admission is the feature.
