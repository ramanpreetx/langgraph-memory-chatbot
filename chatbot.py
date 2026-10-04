from langchain_core.messages import trim_messages
from langchain_core.messages.utils import count_tokens_approximately
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from prompt import STM_UPDATE_PROMPT, STM_INITIAL_PROMPT, CHAT_PROMPT
from dotenv import load_dotenv
from memory import run_memory_pipeline, retrieve_relevant_memories, create_embedding_config, create_ltm_metadata_table, get_ltm_processed_count, update_ltm_processed_count, select_ltm_messages
from langgraph.runtime import Runtime
import streamlit as st
import os
from concurrent.futures import ThreadPoolExecutor
import threading
from langchain_core.runnables import RunnableConfig
from psycopg_pool import ConnectionPool
from groq import BadRequestError
from langchain_core.exceptions import OutputParserException
import logging

logger = logging.getLogger(__name__)

ltm_executor = ThreadPoolExecutor(max_workers=1)

_ltm_lock = threading.Lock()
_users_processing_ltm = set()
_ltm_failures = {}
LTM_MAX_FAILURES = 3

load_dotenv()

DB_URI = os.getenv("POSTGRES_URI")

class State(MessagesState):
    summary: str
    summary_message_count: int


llm = ChatGroq(model="openai/gpt-oss-120b", timeout=60)

STM_TRIGGER_TOKENS = 3000
STM_RECENT_TOKENS = 1000
CHAT_CONTEXT_TOKENS = 3000
LTM_TRIGGER_MESSAGES = 10
MAX_EXPLICIT_LTM_TOKENS = 2000

def summary(state: State) -> State:

    messages = state["messages"]

    existing_summary = state.get("summary", "")
    summary_message_count = state.get("summary_message_count", 0)

    completed_messages = messages[:-1]

    unsummarized_messages = completed_messages[summary_message_count:]

    if count_tokens_approximately(unsummarized_messages) < STM_TRIGGER_TOKENS:
        return {}

    logger.info("STM summarization triggered")

    recent_for_stm = trim_messages(
    unsummarized_messages,
    max_tokens=STM_RECENT_TOKENS,
    strategy="last",
    token_counter=count_tokens_approximately,
    allow_partial=False,
)

    recent_ids = {message.id for message in recent_for_stm}

    messages_to_summarize = [
        message
        for message in unsummarized_messages
        if message.id not in recent_ids
    ]

    old_text = "\n".join(
        f"{message.type}: {str(message.content)[:6000]}"
        for message in messages_to_summarize
        )

    existing_summary = state.get("summary", "")

    if existing_summary:
        prompt = STM_UPDATE_PROMPT.format(
            existing_summary=existing_summary,
            old_text=old_text
        )

    else:
        prompt = STM_INITIAL_PROMPT.format(
            old_text=old_text
        )

    try:
        summary_response = llm.invoke(prompt)
    except Exception:
        logger.exception("STM summary generation failed")
        return {}

    if not summary_response.content or not summary_response.content.strip():
        logger.warning("STM summary came back empty; keeping existing summary")
        return {}

    new_summary_message_count = (
        summary_message_count + len(messages_to_summarize)
    )

    return {"summary": summary_response.content, "summary_message_count": new_summary_message_count}


def trigger_ltm(state: State, config: RunnableConfig, runtime: Runtime) -> State:

    thread_id = config["configurable"]["thread_id"]

    user_id = config["configurable"]["user_id"]

    messages = state["messages"]

    try:
        processed_count = get_ltm_processed_count(thread_id)
    except Exception:
        logger.exception("Could not read LTM cursor for thread %s; skipping LTM this turn", thread_id)
        return {}

    unprocessed_messages = messages[processed_count:]

    # 1. Explicit memory trigger

    current_message = next(
        message for message in reversed(messages)
        if message.type == "human"
    )

    if (current_message.type == "human" and "remember" in current_message.content.lower()):

        if count_tokens_approximately([current_message]) > MAX_EXPLICIT_LTM_TOKENS:
            logger.warning(
                "Explicit LTM request skipped because the message is too large "
                "for safe memory extraction."
            )
            return {}

        existing_summary = state.get("summary", "")

        logger.info("Explicit LTM processing started for thread %s", thread_id)

        future = ltm_executor.submit(
            run_memory_pipeline,
            runtime.store,
            user_id,
            thread_id,
            [current_message],
            0,
            existing_summary ,
        )

        def _on_explicit_done(f, thread_id=thread_id,):

            try:
                success, _ = f.result()

                if success:
                    logger.info("Explicit LTM processing completed for thread %s", thread_id)

            except Exception:
                logger.exception("Explicit LTM pipeline failed for thread %s", thread_id)

        future.add_done_callback(_on_explicit_done)

        return {}

    # 2. Normal 10-message trigger
    
    if len(unprocessed_messages) < LTM_TRIGGER_MESSAGES:
        return {}

    with _ltm_lock:

        if user_id in _users_processing_ltm:
            return {}

        _users_processing_ltm.add(user_id)

    summary = state.get("summary", "")

    logger.info("LTM processing started for thread %s", thread_id)

    future = ltm_executor.submit(
        run_memory_pipeline,
        runtime.store,
        user_id,
        thread_id,
        unprocessed_messages,
        processed_count,
        summary,
    )

    def _on_done(f, thread_id=thread_id, user_id=user_id):

        try:
            success, advance_to = f.result()

            if success:

                _ltm_failures.pop(thread_id, None)

                update_ltm_processed_count(thread_id, advance_to)

                logger.info("LTM processing completed for thread %s", thread_id)

        except (BadRequestError, OutputParserException):

            n = _ltm_failures[thread_id] = _ltm_failures.get(thread_id, 0) + 1

            logger.exception("LTM batch rejected (%d/%d) for thread %s", n, LTM_MAX_FAILURES, thread_id)

            if n >= LTM_MAX_FAILURES:

                _, skip_to = select_ltm_messages(unprocessed_messages, processed_count)

                update_ltm_processed_count(thread_id, skip_to)

                _ltm_failures.pop(thread_id, None)

                logger.error("Skipping poisoned LTM batch for thread %s", thread_id)

        except Exception:
            logger.exception("LTM pipeline failed for thread %s", thread_id)

        finally:
            with _ltm_lock:
                _users_processing_ltm.discard(user_id)

    future.add_done_callback(_on_done)

    return {}

def chat(state: State, config: RunnableConfig, runtime: Runtime) -> State:

    messages = state["messages"]

    existing_summary = state.get("summary", "")

    summary_message_count = state.get("summary_message_count", 0)

    user_id = config["configurable"]["user_id"]

    # Retrieve LTM

    try:
        ltm_memories = retrieve_relevant_memories(
            runtime.store,
            user_id,
            messages[-1].content,
        )
    except Exception:
        logger.exception("LTM retrieval failed")
        ltm_memories = []

    recent_messages = trim_messages(messages[summary_message_count:],
    max_tokens=CHAT_CONTEXT_TOKENS,
    strategy="last",
    token_counter=count_tokens_approximately,
    allow_partial=False,
    )

    if not recent_messages and messages:
        recent_messages = [messages[-1]]

    messages_text = "\n".join(
    f"{message.type}: {message.content}"
    for message in recent_messages
    )

    # LTM text

    ltm_text = "\n".join(
        f"- {memory}"
        for memory in ltm_memories
    )

    if not ltm_text:
        ltm_text = "(No relevant long-term memories.)"

    prompt = CHAT_PROMPT.format(
        messages=messages_text,
        summary=existing_summary,
        memories=ltm_text
    )

    response = llm.invoke(prompt)

    return {"messages": [response]}

@st.cache_resource
def create_chatbot():

    create_ltm_metadata_table()

    # Use connection pools instead of single connections so multiple threads/users
    # can safely access PostgreSQL concurrently without sharing one connection.

    checkpointer_pool = ConnectionPool(
    conninfo=DB_URI,
    min_size=1,
    max_size=5,
    kwargs={"autocommit": True},
    check=ConnectionPool.check_connection,
    )

    # STM / conversation persistence
    checkpointer = PostgresSaver(checkpointer_pool)

    checkpointer.setup()

    store_pool = ConnectionPool(
    conninfo=DB_URI,
    min_size=1,
    max_size=5,
    kwargs={"autocommit": True},
    check=ConnectionPool.check_connection,
    )

    # LTM / cross-conversation persistence
    store = PostgresStore(
    store_pool,
    index=create_embedding_config()
    )

    store.setup()

    graph = StateGraph(State)

    graph.add_node("chat", chat)
    graph.add_node("summarize", summary)
    graph.add_node("trigger_ltm", trigger_ltm)

    graph.add_edge(START, "summarize")
    graph.add_edge("summarize", "chat")
    graph.add_edge("chat", "trigger_ltm")
    graph.add_edge("trigger_ltm", END)

    chatbot = graph.compile(checkpointer=checkpointer, store=store)

    return chatbot
