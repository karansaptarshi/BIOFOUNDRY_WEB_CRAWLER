
from __future__ import annotations
from pathlib import Path
from typing import List
import os, yaml, textwrap
from typing import List



def load_seed(path: str | None = None) -> tuple[str, int]:
    if path is None:
        here = Path(__file__).resolve()                 # .../src/crew/broaden.py
        cfg_path = here.parent.parent / "config" / "queries.yaml"  # .../src/config/queries.yaml
    else:
        cfg_path = Path(path)
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    seed = cfg["seed_topic"]
    target = int(cfg.get("target_count", 80))
    return seed, target

def build_prompt(seed: str, target: int) -> str:
    return textwrap.dedent(f"""\
   Expand the following scholarly search seed into exactly {target} concise and distinct search queries
suitable for locating open-access scientific papers. Do not mention any specific repository.

Seed topic: "{seed}"

Rules:

Output only queries, one per line, with no numbering.

Each query must contain 2–7 words.

Keep all queries scientifically centered on the seed; avoid unrelated domains.

Use formal research terminology; no years, dates, punctuation, operators, or symbols.

Queries should remain clear and not overly complex, avoiding unnecessary jargon or multi-clause phrasing.

Broadening guidelines:

Draw from: general topic terms; mechanistic or method terms; protocols or workflows; design or engineering concepts; high-throughput approaches; computational or ML tools; reviews or standards; and relevant substrates, products, or functional contexts.

Use only concepts that are genuinely related to the seed.

Ensure all queries are distinct and nonredundant.

Produce a diverse, domain-appropriate set of search phrases based on these principles
    """)


def call_groq(prompt: str, model: str = "llama-3.1-8b-instant") -> str:
    # Minimal Groq chat completion call
    from groq import Groq
    import os

    api_key = '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'
    if not api_key:
        raise RuntimeError("GROQ_API_KEY not set")

    client = Groq(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": "You expand concise scholarly search queries for OA sources."},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content or ""




def parse_lines(text: str, cap: int) -> List[str]:
    lines = [ln.strip("•- \t") for ln in text.splitlines()]
    lines = [ln for ln in lines if len(ln.split()) >= 2]
    seen, out = set(), []
    for ln in lines:
        key = " ".join(ln.lower().split())
        if key not in seen:
            seen.add(key); out.append(ln)
        if len(out) >= cap:
            break
    return out

def broaden(cfg_path: str | None = None) -> List[str]:
    seed, target = load_seed() if cfg_path is None else load_seed(cfg_path)
    prompt = build_prompt(seed, target)
    raw = call_groq(prompt)
    return parse_lines(raw, target)

    # --- CLI runner ---
if __name__ == "__main__":
    try:
        qs = broaden()  # reads src/config/queries.yaml via load_seed()
        print(f"Expanded queries: {len(qs)}")
        for q in qs[:20]:
            print(q)
    except Exception as e:
        # helpful in case env var or YAML path is wrong
        print("Error:", type(e).__name__, str(e))
