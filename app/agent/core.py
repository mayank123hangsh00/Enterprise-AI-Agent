"""Core agent loop — Reason → Act → Observe → Respond.

Uses prompt-based routing for maximum model compatibility (avoids tool_use_failed
errors on models that partially support function calling).
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import List

from openai import OpenAI

from app.agent.memory import memory
from app.agent.prompts import RAG_CONTEXT_TEMPLATE, SYSTEM_PROMPT
from app.agent.tools import execute_tool
from app.config import get_settings

logger = logging.getLogger(__name__)

MAX_TOOL_ITERATIONS = 3  # Safety: stop after N tool calls in a single turn

# ── Routing prompt injected into the system prompt ────────────────────────────
ROUTING_INSTRUCTION = """

When a question requires looking up company-specific information (policies, leave, IT guidelines, remote work, product FAQ, handbook), you MUST respond with ONLY this JSON on the first line before your answer:
TOOL_CALL: {"tool": "search_documents", "query": "<focused search phrase>"}

Otherwise answer directly without any TOOL_CALL prefix.
"""


@dataclass
class AgentResponse:
    answer: str
    source: List[str] = field(default_factory=list)
    session_id: str = ""


def _get_client():
    settings = get_settings()
    return OpenAI(
        api_key=settings.groq_api_key,
        base_url="https://api.groq.com/openai/v1"
    )


def _parse_tool_call(text: str):
    """Extract tool call JSON if present on first line, else return None."""
    match = re.match(r"TOOL_CALL:\s*(\{.*?\})", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


class Agent:
    """Agentic reasoning loop with prompt-based routing and session memory."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.client = _get_client()

    def run(self, query: str, session_id: str | None = None) -> AgentResponse:
        sid = session_id or str(uuid.uuid4())

        # Build messages
        system = SYSTEM_PROMPT + ROUTING_INSTRUCTION
        messages = [{"role": "system", "content": system}]
        messages.extend(memory.get_history(sid))
        messages.append({"role": "user", "content": query})

        accumulated_sources: List[str] = []

        for iteration in range(1, MAX_TOOL_ITERATIONS + 1):
            logger.info("Agent iteration %d for session %s", iteration, sid)

            response = self.client.chat.completions.create(
                model=self.settings.llm_model,
                messages=messages,
                temperature=0.2,
            )
            reply = response.choices[0].message.content or ""

            # Check if the model wants to call a tool
            tool_data = _parse_tool_call(reply)

            if not tool_data:
                # Final answer — clean up any leftover TOOL_CALL lines
                answer = re.sub(r"^TOOL_CALL:.*$", "", reply, flags=re.MULTILINE).strip()
                memory.add_message(sid, "user", query)
                memory.add_message(sid, "assistant", answer)
                logger.info("Agent answered after %d iteration(s)", iteration)
                return AgentResponse(
                    answer=answer,
                    source=list(dict.fromkeys(accumulated_sources)),
                    session_id=sid,
                )

            # Execute the tool
            tool_name = tool_data.get("tool", "search_documents")
            tool_query = tool_data.get("query", query)
            logger.info("Tool call: %s('%s')", tool_name, tool_query)

            result_text, sources = execute_tool(
                tool_name, json.dumps({"query": tool_query})
            )
            accumulated_sources.extend(sources)

            # Inject context back into the conversation
            context_msg = RAG_CONTEXT_TEMPLATE.format(context=result_text)
            messages.append({"role": "assistant", "content": reply})
            messages.append({"role": "user", "content": context_msg})

        # Fallback: ask for direct answer after max iterations
        messages.append({"role": "user", "content": "Please summarise your best answer based on the context above."})
        final = self.client.chat.completions.create(
            model=self.settings.llm_model,
            messages=messages,
            temperature=0.2,
        )
        answer = final.choices[0].message.content or "I was unable to generate an answer."
        memory.add_message(sid, "user", query)
        memory.add_message(sid, "assistant", answer)
        return AgentResponse(
            answer=answer,
            source=list(dict.fromkeys(accumulated_sources)),
            session_id=sid,
        )


# Module-level singleton
agent = Agent()
