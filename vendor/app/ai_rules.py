"""Reviewed AI routing catalogue. No external rules are fetched at runtime."""
from __future__ import annotations

CATALOG_VERSION = "2026-10-22"
AI_GROUP_NAME = "🤖 AI 服务"

# The distinction between DOMAIN and DOMAIN-SUFFIX is intentional. Shared parent
# domains (google.com, github.com, microsoft.com, cloudflare.com, etc.) are absent.
SERVICES = [
    ("OpenAI / ChatGPT / Codex / Sora", ["openai.com", "chatgpt.com", "chat.com", "sora.com", "oaistatic.com", "oaiusercontent.com"], []),
    ("Claude / Anthropic", ["anthropic.com", "claude.ai", "claude.com", "claudeusercontent.com"], []),
    ("Gemini / Google AI Studio", ["gemini.google.com", "aistudio.google.com", "ai.google.dev"], ["generativelanguage.googleapis.com", "alkalimakersuite-pa.clients6.google.com", "proactivebackend-pa.googleapis.com"]),
    ("NotebookLM", ["notebooklm.google.com", "notebooklm.google"], ["notebooklm.googleapis.com", "notebooklm-pa.googleapis.com"]),
    ("Gemini Code Assist", [], ["cloudaicompanion.googleapis.com", "cloudcode-pa.googleapis.com", "daily-cloudcode-pa.googleapis.com"]),
    ("Grok / xAI", ["grok.com", "x.ai", "grok.x.com"], []),
    ("Microsoft Copilot", ["copilot.com", "copilot.microsoft.com", "copilot.cloud.microsoft"], []),
    ("Perplexity", ["perplexity.ai", "perplexity.com", "pplx.ai"], ["ppl-ai-file-upload.s3.amazonaws.com", "pplx-res.cloudinary.com"]),
    ("Poe", ["poe.com", "poecdn.net"], []),
    ("Meta AI", ["meta.ai"], []),
    ("Muse AI", ["muse.ai"], []),
    ("Mistral / Le Chat", ["mistral.ai"], []),
    ("Cohere", ["cohere.com", "cohere.ai"], []),
    ("Groq", ["groq.com"], []),
    ("Cerebras", ["cerebras.ai"], []),
    ("OpenRouter", ["openrouter.ai"], []),
    ("Cursor", ["cursor.com", "cursor.sh", "cursorapi.com", "cursor-cdn.com", "cursorvm.com"], []),
    ("Windsurf / Codeium", ["windsurf.com", "windsurf.build", "codeium.com", "codeiumdata.com"], []),
    ("GitHub Copilot", ["githubcopilot.com"], ["copilot-proxy.githubusercontent.com", "copilot-workspace.githubnext.com", "copilotprodattachments.blob.core.windows.net"]),
    ("Hugging Face", ["huggingface.co", "hf.co", "hf.space"], []),
    ("Midjourney", ["midjourney.com"], []),
    ("ElevenLabs", ["elevenlabs.io", "elevenlabs.com"], []),
    ("Suno", ["suno.com", "suno.ai"], []),
    ("Runway", ["runway.com", "runwayml.com"], []),
]


def catalogue():
    services = [{"name": name, "rules": [{"type": "DOMAIN-SUFFIX", "domain": d} for d in suffixes]
                 + [{"type": "DOMAIN", "domain": d} for d in exact]} for name, suffixes, exact in SERVICES]
    return {"version": CATALOG_VERSION, "group_name": AI_GROUP_NAME, "services": services,
            "service_count": len(services), "rule_count": sum(len(s["rules"]) for s in services)}


def managed_rules(group: str):
    return [f"{rule['type']},{rule['domain']},{group}" for service in catalogue()["services"] for rule in service["rules"]]


def managed_match(kind: str, domain: str):
    """Whether an existing domain rule is wholly covered by the AI preset.

    Narrower exact/subdomain rules are absorbed too, otherwise an old custom
    exception would misleadingly remain visible although the preset wins first.
    Broader rules such as google.com are preserved for non-AI traffic.
    """
    kind, domain = kind.upper(), domain.lower().rstrip(".")
    if kind not in ("DOMAIN", "DOMAIN-SUFFIX"):
        return False
    for _, suffixes, exact in SERVICES:
        if any(domain == suffix or domain.endswith("." + suffix) for suffix in suffixes):
            return True
        if kind == "DOMAIN" and domain in exact:
            return True
    return False
