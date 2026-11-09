"""Proposer and writer prompts.

The focus axes are SwarmEvolve's (Jiang and Karniadakis, arXiv 2611.08483,
Supplementary Table 4): 14 aspects for refining and combining programs, 14
perspectives for exploring and starting fresh. The paper names two of its nine
thinking styles; the other seven here are this skill's own.
"""

from __future__ import annotations

ASPECTS = [
    "The starting point of the solution", "The optimization or solution algorithm",
    "Global exploration, restarts, and annealing", "Symmetries and structure of good solutions",
    "Feasibility, tolerances, and a final repair step", "The use of the time limit",
    "The largest source of the remaining error", "A smoother surrogate or a penalty formulation",
    "The weakest part of the current solution", "What the best programs in the field do differently",
    "Bugs, wasted computation, and silent failures", "Simpler and more robust methods",
    "The numbers in the program", "The formulation and its free variables",
]
PERSPECTIVES = [
    "The standard textbook method", "A fundamentally different algorithm",
    "A known construction from the literature", "A physics-inspired method",
    "A parametrization that satisfies the constraints", "Many cheap starts of one fast local optimizer",
    "A symmetry that forces structure", "A coarse-to-fine or incremental construction",
    "A greedy construction with local improvement", "Linear or convex programming for convex parts",
    "An exact or analytical treatment", "Sparsity, separability, or low rank",
    "A higher-order or adaptive method", "An idea that nobody would try first",
]
STYLES = [
    "Reason from first principles.", "Question one assumption the program makes.",
    "Work backwards from what an optimal answer must look like.",
    "Look for the single change with the largest expected gain.",
    "Reason by analogy to a related problem you know well.",
    "Look for where the program fails or wastes its effort.",
    "Estimate the size of the gain before you propose it.",
    "Remove or simplify something rather than add something.",
    "Combine two ideas that are already in the program.",
]


def program_block(p: dict, label: str, show: list[str]) -> str:
    """A parent program as the models see it: score, chosen metrics, any error, code."""
    m = p.get("metrics") or {}
    lines = [f"### {label}", f"score: {p.get('score', 0.0):.6f}"]
    lines += [f"{k}: {m[k]}" for k in show if k in m]
    if m.get("error"):
        lines.append(f"error: {str(m['error'])[:800]}")
    lines += ["```python", p["code"].rstrip(), "```"]
    return "\n".join(lines)


def proposer_system(problem: str, interface: str, parent: dict | None, show: list[str]) -> str:
    head = ("You are one member of a research team improving a program. Teammates each propose one "
            "idea from a different angle; a lead programmer then writes the next version from the "
            "ideas.\n\n## Problem\n" + problem.strip() + "\n\n" + interface.strip())
    if parent is None:
        return head + "\n\nThere is no program for you to read: propose from the problem alone."
    return head + "\n\n## Program\n" + program_block(parent, "Current program", show)


def proposer_user(phrase: str, focus: str, style: str, words: int) -> str:
    return (f"{phrase} {focus.lower()}. {style}\n\nPropose ONE concrete change that would raise the "
            f"score. Reply with the idea only, in at most {words} words: no code, no preamble.")


def writer_system(problem: str, interface: str, parents: list[dict], show: list[str]) -> str:
    s = ("You are the lead programmer of a research team improving a program.\n\n## Problem\n"
         + problem.strip() + "\n\n" + interface.strip())
    if parents:
        s += "\n\n## Programs\n" + "\n\n".join(
            program_block(p, f"Program {chr(65 + i)}", show) for i, p in enumerate(parents))
    return s


def writer_user(ideas: list[str], n_parents: int, entry: str) -> str:
    if ideas:
        body = ("Your teammates proposed these ideas:\n\n" + "\n".join(f"{i + 1}. {t}" for i, t in enumerate(ideas))
                + "\n\nChoose the most promising ideas, combine them where they fit, and write the next version.")
    else:
        body = "Write the next version of the program, improving its score."
    if n_parents > 1:
        body += " Draw on the best parts of each program above."
    return (body + "\n\nReply with at most two sentences describing your direction, then the complete "
            f"program in a single ```python block. The program must define {entry}() as specified.")
