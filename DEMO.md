# Demo — one question, end to end

For the ODSC × Nebius Hackathon submission (due November 20, 2026).
Runtime target: about 3 minutes. The point of the demo is not that the
agent answers — it's *how* it answers: only from evidence it just gathered,
with a citation on every claim, and a plainly admitted gap when the
evidence runs out.

## Before you start

- `.env` holds a Tavily key and a Nebius Token Factory key (see README).
- Terminal open in the repo root.

## The walk-through

**1. Ask a question with a checkable answer (live mode)**

```bash
python3 research_agent.py "What is the Nebius Token Factory API base URL, and how is it authorized?"
```

Say: "Watch the shape of the answer, not just the content. Every sentence
that states a fact ends with a bracketed number. Those numbers are the
evidence pack the agent built from live Tavily results for this exact
question, seconds ago. The Sources list at the bottom is the audit trail."

**2. Show the evidence rule biting (ask something the web can't settle)**

Ask a question whose answer is not in the gathered evidence — something
hyper-specific or not yet public. The answer comes back starting with
`Gap:`, naming what the evidence didn't contain.

Say: "This is the Jack rule, and it's the whole product: no source, no
claim. A research agent that admits a gap is one you can build on. One
that fills gaps smoothly is a liability with good grammar."

**3. Show the offline guarantee (no keys, no network)**

```bash
python3 research_agent.py "What does the hackathon ask participants to build?" \
    --fixture tests/fixture_sources.json
python3 -m unittest discover -s tests -v
```

Say: "Same plumbing, frozen evidence. The citation checker is mechanical —
invent a citation in a test and it fails. The evidence rules aren't a
prompt suggestion; they're enforced in code."

## The one-liner to close on

"Jack spent its life making sure a crew never gets an answer the evidence
can't back. This fork points the same discipline at the open web."
