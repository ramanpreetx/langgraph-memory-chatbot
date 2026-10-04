import os
import uuid
from typing import Literal, Optional
import psycopg
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.messages.utils import count_tokens_approximately
from prompt import MEMORY_EXTRACTION_PROMPT, MEMORY_RESOLUTION_PROMPT
import logging
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

load_dotenv()

DB_URI = os.getenv("POSTGRES_URI")

if not DB_URI:
    raise RuntimeError("POSTGRES_URI is not set (see .env.example)")

ltm_metadata_pool = ConnectionPool(
    conninfo=DB_URI,
    min_size=1,
    max_size=5,
    check=ConnectionPool.check_connection,
)

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMS = 384
MEMORY_MODEL = "openai/gpt-oss-20b"

MAX_LTM_MESSAGE_TOKENS = 2000
MAX_LTM_INPUT_TOKENS = 5000


# Store

def create_embedding_config():

    return {
        "dims": EMBEDDING_DIMS,
        "embed": HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL
        ),
        "fields": ["text"],
    }


# LTM Processing State Management

def create_ltm_metadata_table():

    with ltm_metadata_pool.connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS ltm_metadata (
                thread_id TEXT PRIMARY KEY,
                processed_message_count INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.commit()


def get_ltm_processed_count(thread_id: str) -> int:

    with ltm_metadata_pool.connection() as conn:
        row = conn.execute(
            """
            SELECT processed_message_count
            FROM ltm_metadata
            WHERE thread_id = %s
            """,
            (thread_id,)
        ).fetchone()

    return row[0] if row else 0


def update_ltm_processed_count(thread_id: str, count: int):

    with ltm_metadata_pool.connection() as conn:
        conn.execute(
            """
            INSERT INTO ltm_metadata (thread_id, processed_message_count)
            VALUES (%s, %s)
            ON CONFLICT (thread_id)
            DO UPDATE SET processed_message_count = EXCLUDED.processed_message_count
            """,
            (thread_id, count)
        )
        conn.commit()

# Schemas

class Memory(BaseModel):
    memory: str = Field(description="A durable piece of information about the user")
    type: Literal["preference", "goal", "project", "fact"]


class MemoryExtraction(BaseModel):
    memories: list[Memory]


class MemoryDecision(BaseModel):

    operation: Literal["ADD", "UPDATE", "DELETE", "NOOP"]

    target_memory_id: Optional[str] = Field(
        default=None,
        description="ID of the existing memory affected by UPDATE or DELETE"
    )

    final_text: Optional[str] = Field(
        default=None,
        description="Final memory text to store for ADD or UPDATE"
    )

    justification: str


class MemoryResolution(BaseModel):

    decisions: list[MemoryDecision]

# LLMs

llm = ChatGroq(model=MEMORY_MODEL, temperature=0, timeout=60)

memory_extractor = llm.with_structured_output(
    MemoryExtraction,
    method="json_schema"
    )

memory_resolver = llm.with_structured_output(
    MemoryResolution,
    method="json_schema"
)

# Memory Extraction

def extract_memories(messages: list[BaseMessage]) -> list[Memory]:

    user_messages = [
        message
        for message in messages
        if message.type == "human"
    ]

    if not user_messages:
        return []
    
    conversation = "\n".join(
        f"{message.type}: {message.content}"
        for message in user_messages
    )

    prompt = MEMORY_EXTRACTION_PROMPT.format(
        conversation=conversation
    )

    response = memory_extractor.invoke(prompt)

    return response.memories

# Memory Resolution

def resolve_memory(candidate: Memory, existing_memories) -> MemoryResolution:

    if existing_memories:

        existing_text = "\n".join(
            f"""
            ID: {memory.key}
            Memory: {memory.value["text"]}
            """
            for memory in existing_memories
        )

    else:
        existing_text = "(No existing memories found.)"

    prompt = MEMORY_RESOLUTION_PROMPT.format(
        candidate=candidate.memory,
        candidate_type=candidate.type,
        existing_memories=existing_text
    )

    return memory_resolver.invoke(prompt)

# Apply Memory Decision

def apply_memory_decision(store, user_id: str, candidate: Memory, decision: MemoryDecision, source_thread_id: str):

    namespace = (user_id, "memories")

    # NOOP

    if decision.operation == "NOOP":
        return

    # ADD

    if decision.operation == "ADD":

        memory_id = str(uuid.uuid4())

        store.put(
            namespace,
            memory_id,
            {
                "text": decision.final_text or candidate.memory,
                "type": candidate.type,
                "status": "active",
                "version": 1,
                "source_thread_id": source_thread_id,
            }
        )

        return

    # UPDATE / DELETE

    if decision.operation in ["UPDATE", "DELETE"]:

        target_id = decision.target_memory_id

        if not target_id:

            logger.error("UPDATE/DELETE requires target_memory_id")

            return


        existing = store.get(namespace, target_id)

        if existing is None:

            logger.error(f"Memory {target_id} does not exist.")

            return

        # DELETE

        if decision.operation == "DELETE":

            old_value = dict(existing.value)

            old_value["status"] = "archived"

            store.put(namespace, target_id, old_value)

            return

        # UPDATE

        if decision.operation == "UPDATE":

            old_value = dict(existing.value)

            old_version = old_value.get("version", 1)

            new_memory_id = str(uuid.uuid4())

            # Create new memory

            store.put(
                namespace,
                new_memory_id,
                {
                    "text": (
                        decision.final_text
                        or candidate.memory
                    ),
                    "type": candidate.type,
                    "status": "active",
                    "version": old_version + 1,
                    "supersedes": target_id,
                    "source_thread_id": source_thread_id,
                }
            )

            # Archive old memory
            
            old_value["status"] = "archived"
            
            old_value["superseded_by"] = (new_memory_id)
            
            store.put(namespace, target_id, old_value)

            return

def retrieve_relevant_memories(store, user_id: str, query: str, k: int = 5, score_threshold: float = 0.20):

    namespace = (user_id, "memories")

    results = store.search(
        namespace,
        query=query,
        limit=k,
        filter={"status": "active"},
    )

    relevant = [
        memory
        for memory in results
        if (memory.score or 0) >= score_threshold
    ]

    me_mory = [
        memory.value["text"]
        for memory in relevant
    ]

    return me_mory

def get_user_memories(store, user_id: str):

    namespace = (user_id, "memories")

    return store.search(
        namespace,
        query="",
        limit=100,
        filter={"status": "active"},
    )


def delete_user_memory(store, user_id: str, memory_id: str):

    namespace = (user_id, "memories")

    existing = store.get(namespace, memory_id)

    if existing is None:
        return

    value = dict(existing.value)
    value["status"] = "archived"

    store.put(namespace, memory_id, value)

def clear_user_memories(store, user_id: str):

    namespace = (user_id, "memories")

    memories = store.search(
        namespace,
        query="",
        limit=1000,
        filter={"status": "active"},
    )

    for memory in memories:

        value = dict(memory.value)
        value["status"] = "archived"

        store.put(namespace, memory.key, value)


def select_ltm_messages(messages: list[BaseMessage], start_index: int,):

    selected_messages = []
    total_tokens = 0
    advance_to = start_index

    for offset, message in enumerate(messages):

        # LTM extraction uses only user messages
        if message.type != "human":
            continue

        message_tokens = count_tokens_approximately([message])

        # Oversized individual message:
        # skip it and consider it handled for automatic LTM processing.
        if message_tokens > MAX_LTM_MESSAGE_TOKENS:
            logger.warning(
                "Skipping oversized user message from LTM extraction "
                "(~%s tokens)",
                message_tokens,
            )

            advance_to = start_index + offset + 1
            continue

        # Aggregate input limit reached.
        # Do NOT advance past this message.
        if total_tokens + message_tokens > MAX_LTM_INPUT_TOKENS:
            break

        selected_messages.append(message)
        total_tokens += message_tokens

        # Cursor moves only through messages that were actually considered.
        advance_to = start_index + offset + 1

    logger.info(
        "Selected %d user messages for LTM extraction (~%d tokens). "
        "Cursor: %d -> %d",
        len(selected_messages),
        total_tokens,
        start_index,
        advance_to,
    )

    return selected_messages, advance_to

# Run Memory Pipeline

def run_memory_pipeline(store, user_id: str, thread_id: str, messages, start_index: int, summary: str = "", apply_decisions: bool = True, eval_results=None):
    """Run the LTM extraction, retrieval, resolution, and update pipeline.

    Returns:
        (True, advance_to) in normal mode.
        (eval_results, advance_to) in evaluation mode.
        ([], advance_to) in evaluation mode when no messages or memories
        are available to process.
    """
    
    # Select a bounded LTM batch
    selected_messages, advance_to = select_ltm_messages(
        messages,
        start_index,
    )

    # Nothing eligible to process
    if not selected_messages:
        logger.info("No eligible messages selected for LTM extraction.")
        if apply_decisions:
            return True, advance_to

        return [], advance_to

    # Extract candidates
    extraction = extract_memories(selected_messages)

    if not extraction:
        logger.info("No memories extracted.")
        if apply_decisions:
            return True, advance_to

        return [], advance_to

    if eval_results is not None:
        eval_results["extraction_result"] = []

    # Resolve each candidate

    namespace = (user_id, "memories")

    for candidate in extraction:

        existing_memories = store.search(namespace, query=candidate.memory, limit=5, filter={"status": "active"})

        retrieval_result = [
            memory.key
            for memory in existing_memories
        ]

        resolution = resolve_memory(candidate, existing_memories,)

        if not resolution.decisions:
            logger.warning("Memory resolution returned no decisions for candidate: %s", candidate.memory)
            continue

        if eval_results is not None:
            eval_results["extraction_result"].append(
                {
                    "memory": candidate.memory,
                    "type": candidate.type,
                    "retrieval_result": retrieval_result,
                    "resolution_result": {
                        "operation": resolution.decisions[0].operation,
                        "target_memory_id": resolution.decisions[0].target_memory_id,
                    },
                }
            )

        decision = resolution.decisions[0]

        logger.info(
            "Memory operation: %s",
            decision.operation
        )

        # 3. Apply or collect decision
        if apply_decisions:
            apply_memory_decision(
                store=store,
                user_id=user_id,
                candidate=candidate,
                decision=decision,
                source_thread_id=thread_id,
            )

    if apply_decisions:
        return True, advance_to

    return eval_results, advance_to