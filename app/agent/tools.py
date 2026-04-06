"""Tool definitions for the AI agent using OpenAI function calling format."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.rag.retriever import format_context, retrieve

logger = logging.getLogger(__name__)

# ── OpenAI tool schema ────────────────────────────────────────────────────────

TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "search_documents",
            "description": (
                "Search Acme Corporation's internal documents (policies, handbook, "
                "product FAQ, IT guidelines, remote work rules) to find relevant information "
                "that answers the user's question. Use this whenever the question seems to be "
                "about company-specific policies, procedures, or product details."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "A focused search query describing what information to look for. "
                            "Be specific — e.g. 'annual leave entitlement days' rather than 'leave'."
                        ),
                    },
                },
                "required": ["query"],
            },
        },
    }
]


# ── Tool executor ─────────────────────────────────────────────────────────────

def execute_tool(tool_name: str, arguments: str) -> tuple[str, List[str]]:
    """
    Execute a tool call by name and return (result_text, source_documents).
    *arguments* is the raw JSON string from the LLM tool call.
    """
    try:
        args = json.loads(arguments)
    except json.JSONDecodeError:
        logger.error("Invalid tool arguments JSON: %s", arguments)
        return "Error: could not parse tool arguments.", []

    if tool_name == "search_documents":
        query = args.get("query", "")
        logger.info("Tool search_documents called with query: '%s'", query)

        chunks = retrieve(query)
        if not chunks:
            return "No relevant documents were found for this query.", []

        # Deduplicate sources
        sources = list(dict.fromkeys(c.source for c in chunks))
        context_text = format_context(chunks)
        logger.info("Retrieved %d chunks from sources: %s", len(chunks), sources)
        return context_text, sources

    logger.warning("Unknown tool: %s", tool_name)
    return f"Unknown tool: {tool_name}", []
