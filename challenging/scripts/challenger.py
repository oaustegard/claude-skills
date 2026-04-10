"""
Adversarial review engine for Muninn deliverables.

Uses cross-model review (Gemini default, Claude Opus alternate) to challenge
artifacts before delivery. Inspired by VDD (dollspace.gay) and Grainulation.
"""

import json
import os
import sys
from pathlib import Path

# Sibling skills
sys.path.insert(0, '/mnt/skills/user/invoking-gemini/scripts')
sys.path.insert(0, '/mnt/skills/user/orchestrating-agents/scripts')

PROFILES_PATH = Path(__file__).parent.parent / 'references' / 'profiles.md'

# ---------------------------------------------------------------------------
# Profile system prompt extraction
# ---------------------------------------------------------------------------

def _load_profile_prompt(profile: str) -> str:
    """Extract the system prompt for a profile from profiles.md."""
    text = PROFILES_PATH.read_text()
    # Find the profile section
    marker = f"## {profile.capitalize()} Profile"
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f"Unknown profile: {profile}. Available: prose, analysis, code, recommendation")

    # Extract the system prompt block (between ```  ``` after "### System Prompt")
    section = text[idx:]
    prompt_start = section.find("### System Prompt")
    if prompt_start == -1:
        raise ValueError(f"Profile {profile} has no system prompt section")

    section = section[prompt_start:]
    code_start = section.find("```\n") + 4
    code_end = section.find("\n```", code_start)
    return section[code_start:code_end].strip()


# ---------------------------------------------------------------------------
# Adversary invocation
# ---------------------------------------------------------------------------

def _invoke_gemini_adversary(artifact: str, context: str, system_prompt: str) -> dict:
    """Send artifact to Gemini for adversarial review."""
    from gemini_client import invoke_gemini

    user_prompt = f"""## Context
{context}

## Artifact to Review
{artifact}

Respond ONLY with the JSON object described in your instructions. No preamble, no markdown fences."""

    response = invoke_gemini(
        prompt=user_prompt,
        system=system_prompt,
        model='pro',
        temperature=0.4,  # Low temp for analytical precision
    )
    return _parse_response(response)


def _invoke_claude_adversary(artifact: str, context: str, system_prompt: str) -> dict:
    """Send artifact to Claude Opus sub-agent for adversarial review."""
    from claude_client import invoke_claude

    user_prompt = f"""## Context
{context}

## Artifact to Review
{artifact}

Respond ONLY with the JSON object described in your instructions. No preamble, no markdown fences."""

    response = invoke_claude(
        prompt=user_prompt,
        system=system_prompt,
        model='claude-opus-4-6',
        max_tokens=2048,
        temperature=0.4,
    )
    return _parse_response(response)


def _parse_response(raw: str) -> dict:
    """Parse adversary JSON response, tolerating markdown fences."""
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        # Strip ```json ... ```
        first_newline = cleaned.find('\n')
        cleaned = cleaned[first_newline + 1:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        brace_start = cleaned.find('{')
        brace_end = cleaned.rfind('}')
        if brace_start >= 0 and brace_end > brace_start:
            try:
                return json.loads(cleaned[brace_start:brace_end + 1])
            except json.JSONDecodeError:
                pass
        return {
            "verdict": "REVISE",
            "findings": [{"severity": "medium", "description": "Adversary response was not parseable JSON", "reasoning": raw[:500]}],
            "strengths": [],
            "summary": "Review produced unparseable output — manual review recommended"
        }


# ---------------------------------------------------------------------------
# Confabulation tracking (for blocking mode)
# ---------------------------------------------------------------------------

class ConfabulationTracker:
    """Track false-positive rate across adversarial iterations.

    Adapted from OpenClaudia's VDD engine. When the adversary's FP rate
    exceeds threshold, it's inventing problems — the artifact is clean.
    """

    def __init__(self, threshold: float = 0.75, min_iterations: int = 2):
        self.threshold = threshold
        self.min_iterations = min_iterations
        self.history: list[float] = []

    def record(self, genuine: int, false_positives: int):
        total = genuine + false_positives
        rate = false_positives / total if total > 0 else 1.0
        self.history.append(rate)

    def should_terminate(self) -> bool:
        if len(self.history) < self.min_iterations:
            return False
        return self.history[-1] >= self.threshold

    @property
    def latest_rate(self) -> float:
        return self.history[-1] if self.history else 0.0


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def challenge(
    artifact: str,
    profile: str = 'prose',
    context: str = '',
    mode: str = 'advisory',
    adversary: str = 'gemini',
    max_iterations: int = 3,
) -> dict:
    """Run adversarial review on an artifact.

    Args:
        artifact: The content to review (text, code, etc.)
        profile: Review profile — 'prose', 'analysis', 'code', 'recommendation'
        context: What this artifact is for (audience, purpose, publication target)
        mode: 'advisory' (single pass) or 'blocking' (loop until clean/confabulation)
        adversary: 'gemini' (default, cross-model) or 'claude' (Opus sub-agent)
        max_iterations: Max passes in blocking mode (default: 3)

    Returns:
        dict with keys: verdict, findings, strengths, summary,
              and optionally: iterations (blocking mode), exit_reason
    """
    system_prompt = _load_profile_prompt(profile)

    invoke = _invoke_gemini_adversary if adversary == 'gemini' else _invoke_claude_adversary

    if mode == 'advisory':
        result = invoke(artifact, context, system_prompt)
        result.setdefault('verdict', 'REVISE')
        result.setdefault('findings', [])
        result.setdefault('strengths', [])
        result.setdefault('summary', '')
        return result

    # Blocking mode: iterate until clean or confabulation
    tracker = ConfabulationTracker()
    all_iterations = []

    for i in range(1, max_iterations + 1):
        result = invoke(artifact, context, system_prompt)
        findings = result.get('findings', [])

        # Classify: anything severity 'low' or with hedging language is likely FP
        genuine = [f for f in findings if f.get('severity', 'medium') in ('critical', 'high', 'medium')]
        possible_fp = [f for f in findings if f.get('severity', 'low') == 'low']

        tracker.record(len(genuine), len(possible_fp))

        all_iterations.append({
            'iteration': i,
            'verdict': result.get('verdict', 'REVISE'),
            'genuine_count': len(genuine),
            'fp_count': len(possible_fp),
            'fp_rate': tracker.latest_rate,
            'findings': findings,
        })

        # Exit: clean pass
        if len(genuine) == 0:
            return {
                'verdict': 'SHIP',
                'findings': [],
                'strengths': result.get('strengths', []),
                'summary': 'Clean pass — no genuine issues found.',
                'iterations': all_iterations,
                'exit_reason': f'clean_pass_iteration_{i}',
            }

        # Exit: confabulation threshold
        if tracker.should_terminate():
            return {
                'verdict': 'SHIP',
                'findings': possible_fp,  # Only FPs remain
                'strengths': result.get('strengths', []),
                'summary': f'Confabulation threshold reached at iteration {i} ({tracker.latest_rate:.0%} FP rate). Artifact is clean.',
                'iterations': all_iterations,
                'exit_reason': 'confabulation_threshold',
            }

    # Max iterations without convergence — return latest findings
    last = all_iterations[-1]
    return {
        'verdict': result.get('verdict', 'REVISE'),
        'findings': result.get('findings', []),
        'strengths': result.get('strengths', []),
        'summary': result.get('summary', f'Max iterations ({max_iterations}) reached without convergence.'),
        'iterations': all_iterations,
        'exit_reason': 'max_iterations',
    }


# ---------------------------------------------------------------------------
# CLI for testing
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Adversarial review')
    parser.add_argument('file', help='File to review')
    parser.add_argument('--profile', default='prose', choices=['prose', 'analysis', 'code', 'recommendation'])
    parser.add_argument('--context', default='')
    parser.add_argument('--mode', default='advisory', choices=['advisory', 'blocking'])
    parser.add_argument('--adversary', default='gemini', choices=['gemini', 'claude'])
    args = parser.parse_args()

    content = Path(args.file).read_text()
    result = challenge(content, profile=args.profile, context=args.context,
                       mode=args.mode, adversary=args.adversary)
    print(json.dumps(result, indent=2))
