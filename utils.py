import uuid
import os
from langchain_groq import ChatGroq
import psycopg
import logging
import streamlit as st
from prompt import TITLE_PROMPT
from dotenv import load_dotenv
import re

logger = logging.getLogger(__name__)

load_dotenv()

DB_URI = os.getenv("POSTGRES_URI")

llm = ChatGroq(model="openai/gpt-oss-120b", timeout=60)


def generate_id():

    thread_id = str(uuid.uuid4())

    return thread_id


def generate_title(user_input, ai_response):

    try:
        prompt = TITLE_PROMPT.format(
            user_input=user_input,
            ai_response=ai_response
        )

        response = llm.invoke(prompt)

        return response.content.strip() or "New Conversation"

    except Exception:
        logger.exception("Title generation failed")
        return "New Conversation"


def fetch_user_threads(user_id):

    with psycopg.connect(DB_URI) as conn:

        rows = conn.execute(
            """
            SELECT thread_id
            FROM chat_titles
            WHERE user_id = %s
            """,
            (user_id,)
        ).fetchall()

    return [row[0] for row in rows]

@st.cache_resource
def create_title_table():

    with psycopg.connect(DB_URI) as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_titles (
                thread_id TEXT PRIMARY KEY,
                title TEXT,
                user_id TEXT
            )
        """)

        conn.commit()


def save_title(thread_id, title, user_id):

    with psycopg.connect(DB_URI) as conn:

        conn.execute(
            """
            INSERT INTO chat_titles (thread_id, title, user_id)
            VALUES (%s, %s, %s)
            """,
            (thread_id, title, user_id)
        )

        conn.commit()


def fetch_titles(user_id):

    with psycopg.connect(DB_URI) as conn:

        rows = conn.execute(
            """
            SELECT thread_id, title
            FROM chat_titles
            WHERE user_id = %s
            """,
            (user_id,)
        ).fetchall()

    return dict(rows)


def delete_title(thread_id, user_id):

    with psycopg.connect(DB_URI) as conn:

        conn.execute(
            """
            DELETE FROM chat_titles
            WHERE thread_id = %s AND user_id = %s
            """,
            (thread_id, user_id)
        )

        conn.commit()

def delete_thread(checkpointer, thread_id):

    checkpointer.delete_thread(thread_id)

def normalize_math(text: str) -> str:
    """Normalize common LLM math delimiters without modifying code blocks."""

    code_blocks = []

    def protect_code(match):
        code_blocks.append(match.group(0))
        return f"__CODE_BLOCK_{len(code_blocks) - 1}__"

    text = re.sub(
        r"```[\s\S]*?```",
        protect_code,
        text,
    )

    # Display math: \[ ... \] → $$ ... $$
    text = re.sub(
        r"\\\[\s*([\s\S]*?)\s*\\\]",
        lambda m: f"$$\n{m.group(1).strip()}\n$$",
        text,
    )

    # Inline math: \( ... \) → $ ... $
    text = re.sub(
        r"\\\(\s*([\s\S]*?)\s*\\\)",
        lambda m: f"${m.group(1).strip()}$",
        text,
    )

    # Restore code blocks unchanged.
    for i, block in enumerate(code_blocks):
        text = text.replace(f"__CODE_BLOCK_{i}__", block)

    return text