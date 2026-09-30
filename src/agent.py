"""
agent.py — OpenRouter-powered agent for natural language scraping queries.

Flow:
  1. parse_question(question)  → {"fields": [...], "limit": N, "reasoning": "..."}
  2. <caller scrapes with the returned fields>
  3. answer_question(question, data) → plain-English answer string

The caller (frontend.py) drives these two steps so it can show progress between them.
"""

import json
import os
from typing import Generator
from dotenv import load_dotenv
from openai import OpenAI

# ── OpenRouter client ──────────────────────────────────────────────────────────
MODEL = "openai/gpt-4o-mini"   # fast & cheap; change to any OpenRouter model

load_dotenv()

def _load_api_key() -> str:
    """
    Read the OpenRouter API key.
    Priority:
      1. Streamlit secrets  (.streamlit/secrets.toml  →  OPENROUTER_API_KEY)
      2. Environment variable  OPENROUTER_API_KEY
    """
    # load_dotenv()
    # try:
    #     import streamlit as st
    #     key = st.secrets.get("OPENROUTER_API_KEY", "")
    #     if key and key != "sk-or-your-key-here":
    #         return key
    # except Exception:
    #     return os.getenv("OPENROUTER_API_KEY")
    return os.getenv("OPENROUTER_API_KEY")


def _get_client() -> OpenAI:
    api_key = _load_api_key()
    if not api_key or api_key == "sk-or-your-key-here":
        raise ValueError(
            "OpenRouter API key is not configured.\n"
            "Edit  .streamlit/secrets.toml  and replace the placeholder:\n\n"
            '    OPENROUTER_API_KEY = "sk-or-...your-real-key..."\n\n'
            "Then restart Streamlit."
        )
    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )


# ── Available fields the scraper can collect ──────────────────────────────────
AVAILABLE_FIELDS = {
    "name":        "The full title of the book",
    "price":       "Price as a string with currency symbol, e.g. '£12.99'",
    "rating":      "Star rating as an integer 1-5",
}


# ── Step 1: parse the question into a scraping plan ───────────────────────────
PARSE_SYSTEM_PROMPT = f"""You are a planning agent for a book scraper.
The scraper can collect any combination of these fields from books.toscrape.com:

{json.dumps(AVAILABLE_FIELDS, indent=2)}

Given the user's question, reply with ONLY a valid JSON object (no markdown fences) like:
{{
  "fields": ["name", "price"],   // which fields to collect; always include "name"
  "limit": 30,                   // how many books to scrape (1-100, default 30)
  "reasoning": "short one-line explanation of why you chose these fields"
}}

Rules:
- Always include "name" in fields.
- If the question mentions price or cost, include "price".
- If the question mentions rating, stars, or quality, include "rating".
- If unclear, include all three fields.
- Keep limit between 10 and 100; default to 30 unless the user specifies otherwise.
""".strip()


def parse_question(question: str) -> dict:
    """
    Ask the LLM what fields to scrape and how many books.

    Returns:
        {
          "fields": ["name", "price", "rating"],
          "limit": 30,
          "reasoning": "..."
        }
    """
    client = _get_client()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": PARSE_SYSTEM_PROMPT},
            {"role": "user",   "content": question},
        ],
        temperature=0,
        max_tokens=256,
    )

    raw = response.choices[0].message.content.strip()

    # Strip any accidental markdown fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    plan = json.loads(raw)

    # Sanitise: ensure "name" is always present
    fields = plan.get("fields", list(AVAILABLE_FIELDS.keys()))
    if "name" not in fields:
        fields.insert(0, "name")
    # Drop any fields the scraper doesn't know about
    plan["fields"] = [f for f in fields if f in AVAILABLE_FIELDS]
    plan["limit"]  = max(1, min(100, int(plan.get("limit", 30))))

    return plan


# ── Step 2: answer the question given the scraped data ────────────────────────
ANSWER_SYSTEM_PROMPT = """You are a helpful data analyst.
You will be given a user question and a JSON array of book records scraped from books.toscrape.com.
Answer the question clearly and concisely using only the data provided.
If the data is insufficient to answer fully, say so.
Format numbers and lists nicely. Do NOT include raw JSON in your answer.
""".strip()


def answer_question(question: str, data: list[dict]) -> Generator[str, None, None]:
    """
    Stream an answer to the user's question using the scraped data.

    Yields chunks of text as they arrive from the model.
    """
    client = _get_client()

    data_json = json.dumps(data, ensure_ascii=False, indent=2)

    stream = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": ANSWER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Scraped data ({len(data)} books):\n{data_json}"
                ),
            },
        ],
        temperature=0.3,
        max_tokens=1024,
        stream=True,
    )

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta
