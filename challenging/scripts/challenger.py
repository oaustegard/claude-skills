"""
Adversarial review engine for deliverables.

Cross-model review using Gemini (default) or Claude Opus sub-agent.
Self-contained — no dependencies on other skills. Uses requests for API calls.

Inspired by VDD (dollspace.gay) and Grainulation.
"""

import json
import os
import subprocess
from pathlib import Path

try:
    import requests
except ImportError:
    subprocess.check_call(['pip', 'install', 'requests', '-q', '--break-system-packages'])
    import requests

REFERENCES = Path(__file__).parent.parent / 'references'
VALID_PROFILES = ('prose', 'analysis', 'code', 'recommendation')


# ---------------------------------------------------------------------------
# Credential loading
# ---------------------------------------------------------------------------

def _load_env_file(name: str) -> dict:
    """Try to load a .env file from common project locations."""
    for base in ['/mnt/project', os.getcwd(), Path.home()]:
        path = Path(base) / name
        if path.exists():
            env = {}
            for line in path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
            return env
    return {}


def _get_gemini_config() -> tuple:
    """Returns (url, headers) for Gemini API — gateway or direct."""
    # Try Cloudflare AI Gateway first
    proxy = _load_env_file('proxy.env')
    acct = os.environ.get('CF_ACCOUNT_ID') or proxy.get('CF_ACCOUNT_ID')
    gw = os.environ.get('CF_GATEWAY_ID') or proxy.get('CF_GATEWAY_ID')
    token = os.environ.get('CF_API_TOKEN') or proxy.get('CF_API_TOKEN')
    if acct and gw and token:
        url = f'https://gateway.ai.cloudflare.com/v1/{acct}/{gw}/google-ai-studio/v1beta/models/gemini-3.1-pro-preview:generateContent'
        return url, {'Content-Type': 'application/json', 'cf-aig-authorization': f'Bearer {token}'}

    # Direct Google API
    key = os.environ.get('GOOGLE_API_KEY')
    if key:
        url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-pro-preview:generateContent?key={key}'
        return url, {'Content-Type': 'application/json'}

    raise ValueError('No Gemini credentials found. Set CF_ACCOUNT_ID/CF_GATEWAY_ID/CF_API_TOKEN or GOOGLE_API_KEY.')


def _get_claude_config() -> tuple:
    """Returns (api_key) for Claude API."""
    key = os.environ.get('ANTHROPIC_API_KEY')
    if key:
        return key
    claude_env = _load_env_file('claude.env')
    key = claude_env.get('ANTHROPIC_API_KEY') or claude_env.get('API_KEY')
    if key:
        return key
    raise ValueError('No Claude credentials found. Set ANTHROPIC_API_KEY or add claude.env.')


# ---------------------------------------------------------------------------
# Profile loading
# ---------------------------------------------------------------------------

def _load_system_prompt(profile: str) -> str:
    """Load the system prompt from a profile's own file."""
    if profile not in VALID_PROFILES:
        raise ValueError(f"Unknown profile: {profile}. Available: {', '.join(VALID_PROFILES)}")
    text = (REFERENCES / f'{profile}.md').read_text()
    marker = '## System Prompt'
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f"Profile {profile}.md missing ## System Prompt section")
    section = text[idx:]
    start = section.find('```\n') + 4
    end = section.find('\n```', start)
    return section[start:end].strip()


# ---------------------------------------------------------------------------
# Adversary invocation
# ---------------------------------------------------------------------------

def _build_user_prompt(artifact: str, context: str) -> str:
    return f"## Context\n{context}\n\n## Artifact to Review\n{artifact}\n\nRespond ONLY with the JSON object described in your instructions. No preamble, no markdown fences."


def _invoke_gemini(artifact: str, context: str, system_prompt: str) -> dict:
    url, headers = _get_gemini_config()
    body = {
        'system_instruction': {'parts': [{'text': system_prompt}]},
        'contents': [{'role': 'user', 'parts': [{'text': _build_user_prompt(artifact, context)}]}],
        'generationConfig': {'temperature': 0.4, 'maxOutputTokens': 16384}
    }
    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get('candidates', [])
    if not candidates:
        raise ValueError(f"Gemini returned no candidates: {json.dumps(data)[:500]}")
    content = candidates[0].get('content', {})
    parts = content.get('parts', [])
    if not parts:
        finish = candidates[0].get('finishReason', 'UNKNOWN')
        usage = data.get('usageMetadata', {})
        raise ValueError(
            f"Gemini returned no output text (finishReason={finish}). "
            f"Thinking tokens may have consumed the budget. "
            f"Usage: {json.dumps(usage)}"
        )
    text = parts[0].get('text', '')
    return _parse(text)


def _invoke_claude(artifact: str, context: str, system_prompt: str) -> dict:
    api_key = _get_claude_config()
    resp = requests.post(
        'https://api.anthropic.com/v1/messages',
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json={
            'model': 'claude-opus-4-6',
            'max_tokens': 2048,
            'temperature': 0.4,
            'system': system_prompt,
            'messages': [{'role': 'user', 'content': _build_user_prompt(artifact, context)}],
        },
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data['content'][0]['text']
    return _parse(text)


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


# ---------------------------------------------------------------------------
# Confabulation tracking (blocking mode)
# ---------------------------------------------------------------------------

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
        artifact: Content to review
        profile: 'prose' | 'analysis' | 'code' | 'recommendation'
        context: What the artifact is for (audience, purpose, target)
        mode: 'advisory' (single pass) | 'blocking' (loop until clean/confabulation)
        adversary: 'gemini' (default, cross-model) | 'claude' (Opus sub-agent)
        max_iterations: Max passes in blocking mode

    Returns:
        dict: verdict, findings, strengths, summary, [iterations, exit_reason]
    """
    if mode not in ('advisory', 'blocking'):
        raise ValueError(f"Unknown mode: {mode}. Use 'advisory' or 'blocking'.")
    if adversary not in ('gemini', 'claude'):
        raise ValueError(f"Unknown adversary: {adversary}. Use 'gemini' or 'claude'.")
    if max_iterations < 1:
        raise ValueError(f"max_iterations must be >= 1, got {max_iterations}")

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
            'iteration': i, 'verdict': result.get('verdict', 'REVISE'),
            'genuine_count': len(genuine), 'fp_count': len(fp),
            'fp_rate': tracker.latest_rate, 'findings': findings,
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
