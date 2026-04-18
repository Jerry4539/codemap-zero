"""AI assistant for codemap - project Q&A via multiple AI providers.

Supports:
  - vedaslab.in  (GPT-4o, GPT-4.1, Gemini 2.5 Pro, Claude Sonnet 4, etc.)
  - OpenAI       (gpt-4o, gpt-4o-mini, etc.)
  - Google Gemini (gemini-2.5-pro, etc.)
  - Anthropic Claude (claude-sonnet-4-20250514, etc.)

Uses the scan results as context to answer project questions.
"""

from __future__ import annotations

import json
from typing import Any

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore

import networkx as nx


# Provider configs
PROVIDERS: dict[str, dict[str, Any]] = {
    "vedaslab": {
        "name": "Vedaslab.in",
        "base_url": "https://api.vedaslab.in/public/api.php?path=chat/completions",
        "models_url": "https://api.vedaslab.in/public/models.php?format=flat",
        "default_model": "gpt-4o",
        "models": [],  # fetched live
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1/chat/completions",
        "default_model": "gpt-4o",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "o3-mini"],
    },
    "gemini": {
        "name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "default_model": "gemini-2.5-pro",
        "models": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
    },
    "claude": {
        "name": "Anthropic Claude",
        "base_url": "https://api.anthropic.com/v1/messages",
        "default_model": "claude-sonnet-4-20250514",
        "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-haiku-20241022"],
    },
}


def fetch_vedaslab_models() -> list[str]:
    """Fetch live model list from Vedaslab.in API."""
    if httpx is None:
        return ["gpt-4o"]
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(PROVIDERS["vedaslab"]["models_url"])
            resp.raise_for_status()
            data = resp.json()
            # Response is {"models": [{"model_id": "...", ...}, ...]}
            if isinstance(data, dict) and "models" in data:
                return [m["model_id"] for m in data["models"] if "model_id" in m]
            if isinstance(data, list):
                out = []
                for item in data:
                    if isinstance(item, str):
                        out.append(item)
                    elif isinstance(item, dict) and "model_id" in item:
                        out.append(item["model_id"])
                return out if out else ["gpt-4o"]
            return ["gpt-4o"]
    except Exception:
        return ["gpt-4o", "gpt-4.1", "gemini-2.5-pro", "claude-sonnet-4"]


def _parse_vedaslab_content(content: Any) -> str:
    """Parse VedasLab response content - handles both string and thinking-model array."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        # Find the 'text' block (skip 'thinking' blocks)
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text", "")
        # Fallback: join all text-like blocks
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", block.get("thinking", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts) if parts else str(content)
    return str(content)


class AIAssistant:
    """Interactive AI assistant for project Q&A - multi-provider."""

    def __init__(
        self,
        api_key: str,
        provider: str = "vedaslab",
        model: str | None = None,
        scan_results: dict[str, Any] | None = None,
    ) -> None:
        if httpx is None:
            raise ImportError("httpx is required. Install with: pip install codemap[ai]")

        self.provider = provider.lower()
        if self.provider not in PROVIDERS:
            raise ValueError(f"Unknown provider '{provider}'. Choose from: {', '.join(PROVIDERS)}")

        prov = PROVIDERS[self.provider]
        self.api_key = api_key
        self.model = model or prov["default_model"]
        self.base_url = prov["base_url"]
        self.scan_results = scan_results or {}
        self._history: list[dict[str, str]] = []
        self._context = self._build_context()

    def _build_context(self) -> str:
        """Build a concise project context string from scan results."""
        parts: list[str] = []
        det = self.scan_results.get("detection", {})
        G: nx.DiGraph | None = self.scan_results.get("G")

        parts.append(f"Project: {det.get('project_name', '?')}")
        parts.append(f"Type: {det.get('project_type', '?')}")
        parts.append(f"Files: {det.get('total_files', 0)}, Lines: {det.get('total_lines', 0)}")

        if det.get("frameworks"):
            parts.append(f"Frameworks: {', '.join(det['frameworks'])}")

        # Communities
        communities = self.scan_results.get("communities", {})
        labels = self.scan_results.get("labels", {})
        if communities:
            comm_strs = []
            for cid, members in sorted(communities.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
                label = labels.get(cid, f"Module {cid}")
                file_nodes = []
                if G:
                    for m in members:
                        if G.nodes.get(m, {}).get("type") == "file":
                            file_nodes.append(m)
                count = len(file_nodes) if file_nodes else len(members)
                comm_strs.append(f"  {label} ({count} nodes)")
            parts.append("Communities:\n" + "\n".join(comm_strs))

        # God objects
        gods = self.scan_results.get("gods", [])
        if gods:
            god_strs = [f"  {g.get('label', g.get('node', '?'))} - {g.get('reason', '')}"
                        for g in gods[:8]]
            parts.append("Key components:\n" + "\n".join(god_strs))

        # Entry points
        entry_points = self.scan_results.get("entry_points", [])
        if entry_points:
            ep_strs = [f"  {ep.get('label', '')}" for ep in entry_points[:5]]
            parts.append("Entry points:\n" + "\n".join(ep_strs))

        # Architecture
        arch = self.scan_results.get("architecture", [])
        if arch:
            parts.append(f"Architecture patterns: {', '.join(arch)}")

        # Graph summary
        if G:
            parts.append(f"Graph: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")

        return "\n".join(parts)

    def ask(self, question: str) -> str:
        """Send a question to the AI and return the response."""
        self._history.append({"role": "user", "content": question})

        system_prompt = (
            "You are an AI assistant helping a developer understand their codebase. "
            "You have access to a project analysis. Answer questions concisely and accurately. "
            "If you don't know something specific, say so.\n\n"
            f"PROJECT CONTEXT:\n{self._context}"
        )

        messages = [{"role": "system", "content": system_prompt}]
        # Keep last 10 exchanges for context
        messages.extend(self._history[-20:])

        try:
            if self.provider == "vedaslab":
                answer = self._ask_vedaslab(messages)
            elif self.provider == "claude":
                answer = self._ask_claude(system_prompt, messages[1:])
            else:
                answer = self._ask_openai_compat(messages)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            body = e.response.text[:300]
            if code == 401:
                answer = f"**Authentication failed** - your API key is invalid or expired for {PROVIDERS[self.provider]['name']}. Please check and re-enter it."
            elif code == 403:
                # Check for MODEL_DISABLED
                try:
                    err_data = e.response.json()
                    if err_data.get("code") == "MODEL_DISABLED":
                        answer = f"**Model disabled** - `{self.model}` is currently disabled. Falling back to gpt-4o..."
                        self.model = "gpt-4o"
                        self._history.pop()  # remove the user msg, will re-add on retry
                        return self.ask(question)
                except Exception:
                    pass
                answer = f"**Access denied** - your API key doesn't have permission for model `{self.model}` on {PROVIDERS[self.provider]['name']}. It may require a premium tier."
            elif code == 429:
                answer = f"**Rate limited** - too many requests to {PROVIDERS[self.provider]['name']}. Wait a moment and try again."
            elif code == 404:
                answer = f"**Model not found** - `{self.model}` is not available on {PROVIDERS[self.provider]['name']}. Try a different model."
            else:
                answer = f"**API error {code}** from {PROVIDERS[self.provider]['name']}: {body}"
        except httpx.ConnectError:
            answer = f"**Connection failed** - could not reach {PROVIDERS[self.provider]['name']} API. Check your internet connection."
        except (httpx.ReadError, httpx.RemoteProtocolError, ConnectionResetError, ConnectionAbortedError, OSError) as e:
            answer = (
                f"**Connection lost** - {PROVIDERS[self.provider]['name']} closed the connection. "
                f"This usually means your API key is invalid or the provider rejected the request. "
                f"Please verify your API key and try again."
            )
        except httpx.TimeoutException:
            answer = f"**Request timed out** - {PROVIDERS[self.provider]['name']} took too long to respond. Try again or use a faster model."
        except Exception as e:
            answer = f"**Unexpected error**: {type(e).__name__}: {e}"

        self._history.append({"role": "assistant", "content": answer})
        return answer

    def _ask_vedaslab(self, messages: list[dict]) -> str:
        """Send via VedasLab.in gateway with X-My-API-Key auth."""
        headers = {
            "X-My-API-Key": self.api_key,
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                self.base_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "max_tokens": 4096,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return _parse_vedaslab_content(content)

    def _ask_openai_compat(self, messages: list[dict]) -> str:
        """Send via OpenAI-compatible endpoint (openai, gemini)."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                self.base_url,
                headers=headers,
                json={
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 2048,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _ask_claude(self, system_prompt: str, messages: list[dict]) -> str:
        """Send via Anthropic Messages API."""
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(
                self.base_url,
                headers=headers,
                json={
                    "model": self.model,
                    "system": system_prompt,
                    "messages": messages,
                    "max_tokens": 2048,
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"]
