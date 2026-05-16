import json
import os
import re
from typing import Any

from app.config import AI_ENABLED, LLM_FALLBACK_MODELS, LLM_MODEL, LLM_TIMEOUT_SECONDS
from app.services.redaction import redact_value


class AIClient:
    """Provider-agnostic RCA client.

    LiteLLM is used when installed and configured. If no provider is available,
    this class returns the deterministic rule-based analysis it was given.
    """

    def __init__(
        self,
        model: str | None = None,
        fallback_models: list[str] | None = None,
        enabled: bool = AI_ENABLED,
    ) -> None:
        self.model = model or LLM_MODEL
        self.fallback_models = fallback_models if fallback_models is not None else LLM_FALLBACK_MODELS
        self.enabled = enabled

    def provider_status(self) -> dict[str, Any]:
        models = [self.model, *self.fallback_models]
        return {
            "enabled": self.enabled,
            "default_model": self.model,
            "fallback_models": self.fallback_models,
            "models": [
                {
                    "model": model,
                    "configured": self._model_configured(model),
                    "provider": self._provider_name(model),
                }
                for model in models
            ],
        }

    def generate_rca(
        self,
        incident: dict[str, Any],
        collected: dict[str, Any],
        rag_context: list[dict[str, Any]],
        heuristic: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.enabled:
            return self._fallback(heuristic, rag_context, "AI disabled")

        try:
            from litellm import completion
        except Exception:
            return self._fallback(heuristic, rag_context, "litellm is not installed")

        models = [self.model, *self.fallback_models]
        skipped: list[str] = []
        last_error: str | None = None
        for model in models:
            if not self._model_configured(model):
                skipped.append(f"{model}: missing credentials or disabled")
                continue
            try:
                response = completion(
                    model=model,
                    messages=self._messages(incident, collected, rag_context, heuristic),
                    temperature=0.1,
                    timeout=LLM_TIMEOUT_SECONDS,
                )
                content = response.choices[0].message.content
                parsed = self._parse_json(content)
                return self._normalize(parsed, heuristic, rag_context, model)
            except Exception as exc:
                last_error = f"{model}: {exc}"

        reason = last_error or "; ".join(skipped) or "no configured models"
        return self._fallback(heuristic, rag_context, reason)

    def _messages(
        self,
        incident: dict[str, Any],
        collected: dict[str, Any],
        rag_context: list[dict[str, Any]],
        heuristic: dict[str, Any],
    ) -> list[dict[str, str]]:
        safe_payload = redact_value(
            {
                "incident": incident,
                "logs": collected.get("logs", []),
                "rag_context": rag_context,
                "rule_based_analysis": heuristic,
            }
        )
        return [
            {
                "role": "system",
                "content": (
                    "You are a DevOps incident responder. Return only JSON with keys "
                    "issue, root_cause, mitigations, evidence, confidence. "
                    "Mitigations and evidence must be arrays of short strings."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(safe_payload, indent=2),
            },
        ]

    def _parse_json(self, content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except Exception:
            match = re.search(r"\{.*\}", content or "", flags=re.S)
            if not match:
                raise ValueError("model did not return JSON")
            return json.loads(match.group(0))

    def _normalize(
        self,
        parsed: dict[str, Any],
        heuristic: dict[str, Any],
        rag_context: list[dict[str, Any]],
        model: str,
    ) -> dict[str, Any]:
        mitigations = parsed.get("mitigations") or heuristic.get("mitigations") or []
        evidence = parsed.get("evidence") or heuristic.get("evidence") or []
        if isinstance(mitigations, str):
            mitigations = [mitigations]
        if isinstance(evidence, str):
            evidence = [evidence]
        return {
            "issue": parsed.get("issue") or heuristic.get("issue") or "Unknown",
            "root_cause": parsed.get("root_cause") or heuristic.get("root_cause") or "Inconclusive",
            "mitigations": [str(item) for item in mitigations],
            "evidence": [str(item) for item in evidence],
            "confidence": float(parsed.get("confidence") or heuristic.get("confidence") or 0.35),
            "provider": self._provider_name(model),
            "model": model,
            "fallback_reason": None,
            "rag_context": rag_context,
        }

    def _fallback(
        self,
        heuristic: dict[str, Any],
        rag_context: list[dict[str, Any]],
        reason: str,
    ) -> dict[str, Any]:
        output = dict(heuristic)
        output.setdefault("issue", "Unknown")
        output.setdefault("root_cause", "Inconclusive")
        output.setdefault("mitigations", ["Escalate to on-call", "Gather more logs"])
        output.setdefault("evidence", [])
        output.setdefault("confidence", 0.35)
        output["provider"] = "rules"
        output["model"] = "rule-based-fallback"
        output["fallback_reason"] = reason
        output["rag_context"] = rag_context
        return output

    def _provider_name(self, model: str) -> str:
        return model.split("/", 1)[0] if "/" in model else "unknown"

    def _model_configured(self, model: str) -> bool:
        provider = self._provider_name(model).lower()
        if provider == "gemini":
            return bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
        if provider == "groq":
            return bool(os.getenv("GROQ_API_KEY"))
        if provider in {"huggingface", "hf"}:
            return bool(os.getenv("HUGGINGFACE_API_KEY"))
        if provider == "ollama":
            return os.getenv("OLLAMA_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
        if provider == "openrouter":
            return bool(os.getenv("OPENROUTER_API_KEY"))
        return True
