"""
SandBase API Client for MiniMax M3.1 Flash.
Target model: minimax/minimax-m3.1-flash
Endpoint: https://api.sandbase.ai/v1/chat/completions

Enforces MASTER_PLAN.md rules:
- Key read from .env or environment only.
- No mocks in real runs: stops and reports if key missing or API unreachable.
- Explicit effort required per stage (no default).
- Logs every model call to runs.jsonl: timestamp, stage, scene_id, reasoning_effort,
  max_tokens, HTTP status, latency, usage (including reasoning_tokens), output file path.
- Retries twice on 429/5xx/timeout with backoff (10s, 40s). Does not retry 4xx other than 429.
- JSON schema validation with one repair turn on failure.
- Full assistant message preserved (including reasoning_content and tool_calls).
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import jsonschema
from dotenv import load_dotenv

load_dotenv()

RUNS_LOG_PATH = Path("runs.jsonl")
VALID_REASONING_EFFORTS = {"low", "medium", "high", "xhigh", "max"}


def strip_markdown_fences(text: str) -> str:
    """Strip markdown code block fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def log_model_call(
    stage: str,
    scene_id: Optional[str],
    effort: str,
    max_tokens: int,
    status_code: Optional[int],
    latency: float,
    usage: Dict[str, Any],
    output_file_path: Optional[str] = None,
    error: Optional[str] = None,
) -> None:
    """Log an M3.1 model call to runs.jsonl as specified in MASTER_PLAN.md §0.5."""
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "type": "model_call",
        "stage": stage,
        "scene_id": scene_id,
        "reasoning_effort": effort,
        "max_tokens": max_tokens,
        "status_code": status_code,
        "latency_seconds": round(latency, 3),
        "usage": usage,
        "output_file": output_file_path,
        "error": error,
    }
    with open(RUNS_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class SandBaseClient:
    API_URL = "https://api.sandbase.ai/v1/chat/completions"
    MODEL = "minimax/minimax-m3.1-flash"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("SANDBASE_API_KEY")

    def _require_api_key(self) -> str:
        key = self.api_key or os.environ.get("SANDBASE_API_KEY")
        if not key or key.strip() == "":
            raise RuntimeError(
                "SANDBASE_API_KEY is not set in environment or .env file.\n"
                "Please add your key to .env (e.g. SANDBASE_API_KEY=sk-...) to proceed."
            )
        self.api_key = key.strip()
        return self.api_key

    def chat(
        self,
        stage: str,
        messages: List[Dict[str, Any]],
        effort: str,
        max_tokens: int,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Union[str, Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, Any]] = None,
        scene_id: Optional[str] = None,
        output_file_path: Optional[str] = None,
        schema_path: Optional[Union[str, Path]] = None,
        timeout_seconds: int = 900,
    ) -> Dict[str, Any]:
        """
        Execute a chat completion request with MiniMax M3.1 Flash.
        
        Rules:
        - effort is required (no default).
        - retries twice on 429/5xx/timeout with backoff (10s, 40s).
        - validates against schema_path if provided, sends one repair turn on failure.
        - returns choice message dictionary preserving reasoning_content and tool_calls.
        """
        if not effort or effort not in VALID_REASONING_EFFORTS:
            raise ValueError(
                f"CRITICAL: reasoning effort must be explicitly set to one of {sorted(VALID_REASONING_EFFORTS)}. Got: '{effort}'"
            )

        api_key = self._require_api_key()

        payload: Dict[str, Any] = {
            "model": self.MODEL,
            "messages": messages,
            "reasoning_effort": effort,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = tool_choice or "auto"
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "city-remix-pipeline/1.0",
        }

        retry_delays = [10, 40]
        attempts = 1 + len(retry_delays)
        last_error = None
        response_json: Dict[str, Any] = {}
        status_code: Optional[int] = None

        for attempt in range(attempts):
            start_time = time.time()
            try:
                resp = requests.post(
                    self.API_URL,
                    json=payload,
                    headers=headers,
                    timeout=timeout_seconds,
                )
                status_code = resp.status_code
                latency = time.time() - start_time

                if status_code == 200:
                    response_json = resp.json()
                    usage = response_json.get("usage", {})
                    log_model_call(
                        stage=stage,
                        scene_id=scene_id,
                        effort=effort,
                        max_tokens=max_tokens,
                        status_code=status_code,
                        latency=latency,
                        usage=usage,
                        output_file_path=output_file_path,
                    )
                    break

                # Handle HTTP errors
                error_body = resp.text
                if status_code == 429 or status_code >= 500:
                    last_error = f"HTTP {status_code}: {error_body}"
                    if attempt < len(retry_delays):
                        delay = retry_delays[attempt]
                        print(
                            f"[SandBaseClient] {last_error} on attempt {attempt+1}. Retrying in {delay}s...",
                            file=sys.stderr,
                        )
                        time.sleep(delay)
                        continue
                else:
                    # 4xx error (other than 429): do not retry
                    last_error = f"HTTP {status_code}: {error_body}"
                    log_model_call(
                        stage=stage,
                        scene_id=scene_id,
                        effort=effort,
                        max_tokens=max_tokens,
                        status_code=status_code,
                        latency=latency,
                        usage={},
                        output_file_path=output_file_path,
                        error=last_error,
                    )
                    raise RuntimeError(f"SandBase API returned unrecoverable error: {last_error}")

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                latency = time.time() - start_time
                last_error = f"Network/Timeout error: {str(e)}"
                if attempt < len(retry_delays):
                    delay = retry_delays[attempt]
                    print(
                        f"[SandBaseClient] {last_error} on attempt {attempt+1}. Retrying in {delay}s...",
                        file=sys.stderr,
                    )
                    time.sleep(delay)
                    continue
                else:
                    log_model_call(
                        stage=stage,
                        scene_id=scene_id,
                        effort=effort,
                        max_tokens=max_tokens,
                        status_code=None,
                        latency=latency,
                        usage={},
                        output_file_path=output_file_path,
                        error=last_error,
                    )
                    raise RuntimeError(f"SandBase API failed after retries: {last_error}") from e

        if not response_json or "choices" not in response_json:
            raise RuntimeError(f"Invalid API response received from SandBase: {last_error or 'empty response'}")

        assistant_message = response_json["choices"][0]["message"]

        # Validate against schema if requested
        if schema_path:
            assistant_message = self._validate_and_repair(
                stage=stage,
                messages=messages,
                assistant_message=assistant_message,
                effort=effort,
                max_tokens=max_tokens,
                schema_path=Path(schema_path),
                scene_id=scene_id,
                output_file_path=output_file_path,
            )

        return assistant_message

    def _validate_and_repair(
        self,
        stage: str,
        messages: List[Dict[str, Any]],
        assistant_message: Dict[str, Any],
        effort: str,
        max_tokens: int,
        schema_path: Path,
        scene_id: Optional[str],
        output_file_path: Optional[str],
    ) -> Dict[str, Any]:
        """Validate content against JSON Schema; attempt exactly one repair turn on failure."""
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        content = assistant_message.get("content") or ""
        clean_content = strip_markdown_fences(content)

        validation_error = None
        try:
            parsed = json.loads(clean_content)
            jsonschema.validate(instance=parsed, schema=schema)
            return assistant_message
        except Exception as e:
            validation_error = str(e)
            print(f"[Schema Validation Warning] Output in stage '{stage}' failed validation: {validation_error}")

        # Send one repair turn
        print(f"[Schema Repair] Requesting repair turn from MiniMax M3.1 Flash for stage '{stage}'...")
        repair_messages = list(messages)
        repair_messages.append(assistant_message)
        repair_messages.append({
            "role": "user",
            "content": f"Your output failed validation against the required JSON schema:\n{validation_error}\nReturn corrected, valid JSON only matching the schema.",
        })

        repair_msg = self.chat(
            stage=f"{stage}_repair",
            messages=repair_messages,
            effort=effort,
            max_tokens=max_tokens,
            scene_id=scene_id,
            output_file_path=output_file_path,
            schema_path=None,
        )

        repair_content = strip_markdown_fences(repair_msg.get("content") or "")
        try:
            re_parsed = json.loads(repair_content)
            jsonschema.validate(instance=re_parsed, schema=schema)
            print(f"[Schema Repair] Repair turn succeeded for stage '{stage}'.")
            return repair_msg
        except Exception as e:
            raise RuntimeError(
                f"Stage '{stage}' output failed schema validation after repair turn: {e}\nRaw content:\n{repair_content[:500]}"
            )
