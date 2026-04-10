"""
Adversarial review engine for Muninn deliverables.

Uses cross-model review (Gemini default, Claude Opus alternate) to challenge
artifacts before delivery. Inspired by VDD (dollspace.gay) and Grainulation.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, '/mnt/skills/user/invoking-gemini/scripts')
sys.path.insert(0, '/mnt/skills/user/orchestrating-agents/scripts')

REFERENCES = Path(__file__).parent.parent / 'references'
VALID_PROFILES = ('prose', 'analysis', 'code', 'recommendation')


def _load_system_prompt(profile: str) -> str:
    """Load the system prompt from a profile's own file."""
    if profile not in VALID_PROFILES:
        raise ValueError(f"Unknown profile: {profile}. Available: {', '.join(VALID_PROFILES)}")

    text = (REFERENCES / f'{profile}.md').read_text()

    # Extract content between ``` fences after "## System Prompt"
    marker = '## System Prompt'
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f"Profile {profile}.md missing ## System Prompt section")
    section = text[idx:]
    start = section.find('```\n') + 4
    end = section.find('\n```', start)
    return section[start:end].strip()


def _invoke_gemini(artifact: str, context: str, system_prompt: str) -> dict:
    from gemini_client import invoke_gemini
    raw = invoke_gemini(
        prompt=f"## Context\n{context}\n\n## Artifact to Review\n{artifact}\n\nRespond ONLY with the JSON object described in your instructions. No preamble, no markdown fences.",
        system=system_prompt,
        model='pro',
        temperature=0.4,
    )
    return _parse(raw)


def _invoke_claude(artifact: str, context: str, system_prompt: str) -> dict:
    from claude_client import invoke_claude
    raw = invoke_claude(
        prompt=f"## Context\n{context}\n\n## Artifact to Review\n{artifact}\n\nRespond ONLY with the JSON object described in your instructions. No preamble, no markdown fences.",
        system=system_prompt,
        model='claude-opus-4-6',
        max_tokens=2048,
        temperature=0.4,
    )
    return _parse(raw)


def _parse(raw: str) -> dict:
    """Parse adversary JSON, tolerating markdown fences."""
    s = raw.strip()
    if s.startswith('```'):
        s = s[s.find('\n') + 1:]
        if s.endswith('```'):
            s = s[:-3].strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        # Find outermost braces
        a, b = s.find('{'), s.rfind('}')
        if a >= 0 and b > a:
            try:
                return json.loads(s[a:b + 1])
            except json.JSONDecodeError:
                pass
        return {
            'verdict': 'REVISE',
            'findings': [{'severity': 'medium', 'description': 'Adversary response not parseable', 'reasoning': raw[:500]}],
            'strengths': [],
            'summary': 'Unparseable adversary output — manual review recommended'
        }


class ConfabulationTracker:
    """Detects when adversary starts inventing problems (VDD pattern).

    When FP rate exceeds threshold after min_iterations, the artifact is clean.
    """
    def __init__(self, threshold: float = 0.75, min_iterations: int = 2):
        self.threshold = threshold
        self.min_iterations = min_iterations
        self.history: list[float] = []

    def record(self, genuine: int, false_positives: int):
        total = genuine + false_positives
        self.history.append(false_positives / total if total > 0 else 1.0)

    def should_terminate(self) -> bool:
        return len(self.history) >= self.min_iterations and self.history[-1] >= self.threshold

    @property
    def latest_rate(self) -> float:
        return self.history[-1] if self.history else 0.0


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
        artifact: Content to review
        profile: 'prose' | 'analysis' | 'code' | 'recommendation'
        context: What the artifact is for (audience, purpose, target)
        mode: 'advisory' (single pass) | 'blocking' (loop until clean/confabulation)
        adversary: 'gemini' (default, cross-model) | 'claude' (Opus sub-agent)
        max_iterations: Max passes in blocking mode

    Returns:
        dict: verdict, findings, strengths, summary, [iterations, exit_reason]
    """
    system_prompt = _load_system_prompt(profile)
    invoke = _invoke_gemini if adversary == 'gemini' else _invoke_claude

    if mode == 'advisory':
        result = invoke(artifact, context, system_prompt)
        result.setdefault('verdict', 'REVISE')
        result.setdefault('findings', [])
        result.setdefault('strengths', [])
        result.setdefault('summary', '')
        return result

    # Blocking mode
    tracker = ConfabulationTracker()
    iterations = []

    for i in range(1, max_iterations + 1):
        result = invoke(artifact, context, system_prompt)
        findings = result.get('findings', [])
        genuine = [f for f in findings if f.get('severity', 'medium') in ('critical', 'high', 'medium')]
        fp = [f for f in findings if f.get('severity') == 'low']
        tracker.record(len(genuine), len(fp))

        iterations.append({
            'iteration': i,
            'verdict': result.get('verdict', 'REVISE'),
            'genuine_count': len(genuine),
            'fp_count': len(fp),
            'fp_rate': tracker.latest_rate,
            'findings': findings,
        })

        if len(genuine) == 0:
            return {
                'verdict': 'SHIP', 'findings': [], 'strengths': result.get('strengths', []),
                'summary': 'Clean pass — no genuine issues.',
                'iterations': iterations, 'exit_reason': f'clean_pass_iteration_{i}',
            }

        if tracker.should_terminate():
            return {
                'verdict': 'SHIP', 'findings': fp, 'strengths': result.get('strengths', []),
                'summary': f'Confabulation threshold at iteration {i} ({tracker.latest_rate:.0%} FP). Artifact is clean.',
                'iterations': iterations, 'exit_reason': 'confabulation_threshold',
            }

    return {
        'verdict': result.get('verdict', 'REVISE'),
        'findings': result.get('findings', []),
        'strengths': result.get('strengths', []),
        'summary': result.get('summary', f'Max iterations ({max_iterations}) reached.'),
        'iterations': iterations, 'exit_reason': 'max_iterations',
    }


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description='Adversarial review')
    p.add_argument('file')
    p.add_argument('--profile', default='prose', choices=list(VALID_PROFILES))
    p.add_argument('--context', default='')
    p.add_argument('--mode', default='advisory', choices=['advisory', 'blocking'])
    p.add_argument('--adversary', default='gemini', choices=['gemini', 'claude'])
    a = p.parse_args()
    print(json.dumps(challenge(Path(a.file).read_text(), a.profile, a.context, a.mode, a.adversary), indent=2))
