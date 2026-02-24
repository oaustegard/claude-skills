#!/usr/bin/env python3
"""
Tiling Tree — exhaustive MECE problem space exploration via parallel subagents.

Implements the MIT Synthetic Neurobiology "tiling tree" method.
Depends on: orchestrating-agents skill

Usage:
    python3 tiling_tree.py "How can we generate energy?"
    python3 tiling_tree.py "How can we record neural activity?" --depth 3 --criteria "impact,feasibility,novelty"
"""

import sys, json, argparse
from dataclasses import dataclass, field
from typing import Optional

# ── Dependency setup ──────────────────────────────────────────────────────────

sys.path.insert(0, '/mnt/skills/user/orchestrating-agents/scripts')

try:
    import claude_client as cc
    from claude_client import invoke_claude, invoke_parallel
except ImportError as e:
    print(f"ERROR: orchestrating-agents skill not found at /mnt/skills/user/orchestrating-agents/\n{e}")
    sys.exit(1)

# Apply key shim if needed (workaround until issue #311 is resolved)
try:
    sys.path.insert(0, '/home/claude')
    from muninn_utils.orchestrating_agents_shim import patch_orchestrating_agents
    patch_orchestrating_agents(cc)
except ImportError:
    pass  # Shim not available; assume ANTHROPIC_API_KEY is set in environment


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Node:
    id: str
    label: str
    definition: str
    parent_id: Optional[str]
    depth: int
    split_criterion: str = ""
    children: list = field(default_factory=list)
    is_leaf: bool = False
    exclusions: str = ""
    evaluation: dict = field(default_factory=dict)


# ── JSON parsing (workaround for issue #312) ──────────────────────────────────

def _parse_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON. Workaround until orchestrating-agents
    exposes parse_json_response() (issue #312)."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0]
    return json.loads(raw.strip())


# ── Prompts ───────────────────────────────────────────────────────────────────

SPLITTER_SYSTEM = """You are a rigorous analyst applying the "tiling tree" method from MIT's Synthetic Neurobiology group. Your job: partition a problem space into MECE subsets (Mutually Exclusive, Collectively Exhaustive).

Rules:
1. Define your split criterion PRECISELY before naming branches. Vague criteria produce overlapping branches.
2. Branches must not overlap. State explicitly what each branch EXCLUDES to verify this.
3. Branches together must cover the entire parent set.
4. Prefer physics/math/logical splits — they tend to be genuinely exhaustive.
5. Look for the "third option" — what falls outside an obvious binary split?
6. A branch is a LEAF when it represents a single concrete, actionable approach (not a category).
7. Aim for 2-4 branches per split.

Respond ONLY with valid JSON."""

EVALUATOR_SYSTEM = """You evaluate candidate approaches against specified criteria. Be calibrated: reserve high scores for genuinely strong candidates. Respond ONLY with valid JSON."""


def _splitter_prompt(label: str, definition: str, depth: int, max_depth: int) -> str:
    leaf_instruction = (
        "Mark branches as leaves (is_leaf: true) if they represent a single concrete approach."
        if depth < max_depth
        else "Final level — mark ALL branches as leaves (is_leaf: true)."
    )
    return f"""Problem space to partition: "{label}"
Definition: {definition}
Current depth: {depth}/{max_depth}

{leaf_instruction}

Respond with JSON:
{{
  "split_criterion": "Precise property used to split this space (a definition, not a question)",
  "branches": [
    {{
      "label": "Short name",
      "definition": "Precise definition of what belongs here",
      "exclusions": "What this branch explicitly does NOT include",
      "is_leaf": false,
      "leaf_idea": ""
    }}
  ],
  "coverage_check": "One sentence confirming branches together cover the full parent space"
}}"""


def _evaluator_prompt(leaves: list, criteria: list[str]) -> str:
    descriptions = "\n".join(
        f'- [{l.id}] {l.label}: {l.definition}' for l in leaves
    )
    score_template = ", ".join(f'"{c}": 1-5' for c in criteria)
    return f"""Evaluate these candidate approaches:

{descriptions}

Criteria: {', '.join(criteria)}

Respond with JSON:
{{
  "evaluations": [
    {{
      "id": "node_id",
      "scores": {{{score_template}}},
      "rationale": "One sentence on the most important trade-off",
      "overall": 1-5
    }}
  ]
}}"""


# ── Tree construction ─────────────────────────────────────────────────────────

def build_tree(problem: str, max_depth: int = 2) -> Node:
    root = Node(
        id="root",
        label=problem,
        definition=f"The complete set of all possible approaches to: {problem}",
        parent_id=None,
        depth=0,
    )

    frontier = [root]

    for level in range(max_depth):
        to_split = [n for n in frontier if not n.is_leaf]
        if not to_split:
            break

        print(f"  Level {level + 1}: splitting {len(to_split)} node(s) in parallel...")

        prompts = [
            {
                "prompt": _splitter_prompt(n.label, n.definition, n.depth + 1, max_depth),
                "system": SPLITTER_SYSTEM,
                "temperature": 1.0,
            }
            for n in to_split
        ]

        raw_results = invoke_parallel(
            prompts,
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048
        )

        next_frontier = []
        for node, raw in zip(to_split, raw_results):
            try:
                data = _parse_json(raw)
            except (json.JSONDecodeError, Exception) as e:
                print(f"  ✗ Parse failed for '{node.label}': {e}", file=sys.stderr)
                node.is_leaf = True
                continue

            node.split_criterion = data.get("split_criterion", "")
            print(f"  ✓ '{node.label[:40]}' → {node.split_criterion[:60]}...")

            for i, b in enumerate(data.get("branches", [])):
                child = Node(
                    id=f"{node.id}_{i}",
                    label=b["label"],
                    definition=b.get("leaf_idea") or b["definition"],
                    parent_id=node.id,
                    depth=node.depth + 1,
                    is_leaf=b.get("is_leaf", node.depth + 1 >= max_depth),
                    exclusions=b.get("exclusions", ""),
                )
                node.children.append(child)
                if not child.is_leaf:
                    next_frontier.append(child)

        frontier = next_frontier

    return root


def collect_leaves(node: Node) -> list:
    if node.is_leaf:
        return [node]
    return [leaf for child in node.children for leaf in collect_leaves(child)]


def evaluate_leaves(leaves: list, criteria: list[str]) -> None:
    print(f"  Evaluating {len(leaves)} leaves against: {', '.join(criteria)}...")
    try:
        raw = invoke_claude(
            prompt=_evaluator_prompt(leaves, criteria),
            system=EVALUATOR_SYSTEM,
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            temperature=0.8,
        )
        data = _parse_json(raw)
        leaf_map = {l.id: l for l in leaves}
        for ev in data.get("evaluations", []):
            node = leaf_map.get(ev["id"])
            if node:
                node.evaluation = ev
    except Exception as e:
        print(f"  ✗ Evaluation failed: {e}", file=sys.stderr)


# ── Rendering ─────────────────────────────────────────────────────────────────

def _count_nodes(node: Node) -> int:
    return 1 + sum(_count_nodes(c) for c in node.children)


def render_tree(node: Node, prefix: str = "", is_last: bool = True) -> str:
    lines = []

    if node.depth == 0:
        lines.append(f"◆ {node.label}")
    else:
        connector = "└── " if is_last else "├── "
        tag = " [LEAF]" if node.is_leaf else ""
        lines.append(f"{prefix}{connector}{node.label}{tag}")
        if node.is_leaf and node.evaluation:
            sub = "    " if is_last else "│   "
            ev = node.evaluation
            score_str = "  ".join(f"{k}:{v}" for k, v in ev.get("scores", {}).items())
            lines.append(f"{prefix}{sub}  ↳ {score_str}  overall:{ev.get('overall', '?')}")
            lines.append(f"{prefix}{sub}  ↳ {ev.get('rationale', '')}")

    if node.split_criterion and node.children:
        sub = "    " if (is_last or node.depth == 0) else "│   "
        lines.append(f"{prefix}{sub}[split: {node.split_criterion[:72]}]")

    child_prefix = prefix + ("    " if is_last else "│   ")
    for i, child in enumerate(node.children):
        lines.append(render_tree(child, child_prefix, i == len(node.children) - 1))

    return "\n".join(lines)


def render_markdown(root: Node, problem: str, criteria: list[str]) -> str:
    leaves = collect_leaves(root)
    ranked = sorted(leaves, key=lambda l: l.evaluation.get("overall", 0), reverse=True)
    node_count = _count_nodes(root)

    md = [f"# Tiling Tree: {problem}\n"]
    md.append("## Tree\n```")
    md.append(render_tree(root))
    md.append("```\n")

    if criteria and any(l.evaluation for l in leaves):
        md.append(f"## Ranked Leaves ({', '.join(criteria)})\n")
        for rank, leaf in enumerate(ranked, 1):
            ev = leaf.evaluation
            scores = ev.get("scores", {})
            score_str = " | ".join(f"**{k}**: {v}/5" for k, v in scores.items())
            md.append(f"### {rank}. {leaf.label}  *(overall {ev.get('overall', '?')}/5)*")
            md.append(f"{score_str}\n")
            md.append(f"> {leaf.definition}\n")
            md.append(f"{ev.get('rationale', '')}\n")

    md.append(f"---\n*{len(leaves)} leaf ideas across {node_count} total nodes.*")
    return "\n".join(md)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Tiling Tree — exhaustive MECE problem space exploration"
    )
    parser.add_argument("problem", help="The problem to tile")
    parser.add_argument("--depth", type=int, default=2,
                        help="Max tree depth (default: 2, yields ~16 leaves)")
    parser.add_argument("--criteria", default="impact,novelty,feasibility",
                        help="Comma-separated evaluation criteria")
    parser.add_argument("--output", default="/mnt/user-data/outputs/tiling_tree.md",
                        help="Output markdown path")
    args = parser.parse_args()

    criteria = [c.strip() for c in args.criteria.split(",")]

    print(f"\n◆ Tiling Tree: {args.problem}")
    print(f"  Depth: {args.depth} | Criteria: {', '.join(criteria)}\n")

    root = build_tree(args.problem, max_depth=args.depth)
    leaves = collect_leaves(root)
    print(f"\n  Tree complete: {len(leaves)} leaves\n")

    if criteria:
        evaluate_leaves(leaves, criteria)

    print("\n" + render_tree(root))

    md = render_markdown(root, args.problem, criteria)
    with open(args.output, "w") as f:
        f.write(md)
    print(f"\n  Saved: {args.output}")


if __name__ == "__main__":
    main()
