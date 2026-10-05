# LangGraph Chatbot with Short-Term and Long-Term Memory

A chatbot built with LangGraph and Streamlit. It uses Groq-hosted models for the replies and PostgreSQL for conversation state, titles, long-term memories, and LTM processing metadata. It has two kinds of memory:

- Short-term memory (STM): a running summary of the current conversation, so older messages don't have to stay in the prompt.
- Long-term memory (LTM): short facts about the user (preferences, goals, projects, personal facts) that are saved from conversations and reused in later ones.

Chat replies, STM summaries and conversation titles come from `openai/gpt-oss-120b`. LTM extraction and resolution use `openai/gpt-oss-20b` at temperature 0. Embeddings come from `sentence-transformers/all-MiniLM-L6-v2` and are stored in PostgreSQL.

## What it does

- Conversations are listed in the sidebar. A new thread is created when you send the first message of a new chat, and after the first reply, `gpt-oss-120b` is asked for a 2 to 5 word title based on the first user message and that reply (the length comes from the prompt and isn't checked in code). Hovering over a conversation shows a delete button, which removes its saved state and title. Memories created from it stay.
- Replies are streamed into the page as they are generated. Opening an old conversation reloads its full message history from PostgreSQL.
- Each conversation has its own STM summary. Each user has one set of LTM memories shared across all of their conversations.
- LTM is filled in two ways: automatically once a thread has 10 or more messages that haven't been processed yet, and immediately when a message contains the word "remember".
- The Memory button in the sidebar opens a dialog that lists the saved memories. You can delete them one at a time or clear all of them.
- LaTeX written as `\( ... \)` or `\[ ... \]` in model output is converted to `$ ... $` and `$$ ... $$` before rendering, and code blocks are left alone. The chat prompt also tells the model to use the dollar-sign form.
- There is no login. The first time a browser opens the app, a random UUID is stored in a cookie (`chatbot_user_id`, 5 year expiry) and used as the user ID. Threads and memories are tied to that ID.

## How a message flows

The LangGraph graph has three nodes in a straight line:

```
START -> summarize -> chat -> trigger_ltm -> END
```

The graph state is LangGraph's `MessagesState` plus two extra fields: `summary` (text) and `summary_message_count` (an integer). The config passed on every call carries a `thread_id` and a `user_id`.

1. `summarize` checks whether the part of the conversation that is not yet summarized has grown too large. If it has, it folds the older part into the summary. Details are in the next section.
2. `chat` looks up long-term memories related to the latest message, builds one prompt out of the summary, those memories and the recent messages, and calls the model. The reply is added to the message list.
3. `trigger_ltm` decides whether to start long-term memory processing. It does not do the processing itself. It hands the work to a background thread and returns right away, so the response is not delayed.

`app.py` streams the graph with `stream_mode="messages"` and only shows chunks coming from the `chat` node, so the summarizer's output never appears in the UI.

## Short-term memory

STM lives in the graph state, which the checkpointer saves per thread. The `summarize` node runs before every reply:

1. It takes all messages except the last one (the message that was just sent) and skips the first `summary_message_count` of them, since those are already covered by the summary.
2. If the remaining messages are under 3000 tokens, it does nothing.
3. Otherwise it keeps the most recent 1000 tokens of those messages as they are and summarizes everything older than that. Whole messages only, no partial ones. Each message is cut to its first 6000 characters before being sent to the summarizer.
4. If a summary already exists, the older messages are merged into it (`PROMPT` in `prompt.py`). If not, a first summary is written (`PROMPT1`).
5. The node saves the new summary and increases `summary_message_count` by the number of messages it just summarized.

If the summarizer call fails, or returns empty text, the node returns nothing and the state stays as it was. The unsummarized messages are still over the limit, so it tries again on a later turn.

Messages are never removed from the state. The full history stays in the checkpoint and is what the UI displays. The summary is a context-management mechanism; it does not replace or delete the stored message history. `summary_message_count` only tells the `chat` node where to start reading.

The prompt that the `chat` node builds (`PROMPT2`) has three parts:

- the summary,
- the retrieved long-term memories, one per line, or `(No relevant long-term memories.)` if there are none,
- the recent messages: everything from `summary_message_count` onward, trimmed to the last 3000 tokens, written as `human: ...` / `ai: ...` lines. If nothing fits in the limit, only the latest message is used.

This is sent to the model as a single prompt string, not as a list of chat messages.

Token counts come from `count_tokens_approximately` in `langchain-core`. They are rough estimates, not the model's own tokenizer.

## Long-term memory

Memories are stored in the `PostgresStore` under the namespace `(user_id, "memories")`. Each one has:

- `text`: the memory itself, written as "User prefers ...", "User's goal is ...", etc.
- `type`: one of `preference`, `goal`, `project`, `fact`.
- `status`: `active` or `archived`.
- `version` and `source_thread_id`. Memories created by an UPDATE also get `supersedes`, and the old one gets `superseded_by`.

The pipeline is:

```
user messages -> extraction -> retrieval of similar existing memories
              -> resolution -> ADD / UPDATE / DELETE / NOOP -> PostgreSQL
```

Batch selection. Only user messages are used. A message over about 2000 tokens is skipped. Messages are added to the batch until it reaches about 5000 tokens. If something doesn't fit, it is left for the next batch. The position reached is saved so the same messages aren't processed again (see `ltm_metadata` below).

Extraction. `extract_memories` sends the user messages of the batch to the 20b model with `MEMORY_EXTRACTION_PROMPT`. The prompt is deliberately conservative: it only wants durable preferences, concrete goals, ongoing projects and personal facts that the user stated explicitly, one memory per subject, and it says to return nothing when unsure. The model answers with structured output (a JSON schema backed by Pydantic classes), and the result is a list of candidate memories, which can be empty. Assistant messages and the STM summary are not part of the extraction input.

Retrieval before resolution. For each candidate, the user's active memories are searched with the candidate text and the top 5 are returned, with no score cutoff. The resolver model can't see the whole memory table, so these 5 are what it compares the candidate against. Each one is given to the resolver with its ID, which is how the model points at a specific record for UPDATE or DELETE. If nothing is found, the prompt says `(No existing memories found.)`.

Resolution. The resolver gets `MEMORY_RESOLUTION_PROMPT`, the candidate, its type, and the retrieved memories. The prompt tells the model to choose exactly one operation, and the schema for a decision has `operation`, an optional `target_memory_id`, an optional `final_text` and a `justification`. The schema allows a list of decisions, but the code only uses the first one. If the list is empty, a warning is logged and that candidate is skipped.

Candidates are resolved one at a time, and each decision is applied before the next candidate is searched. A later candidate in the same batch can therefore see (and update) what an earlier one just wrote.

### Operations

- ADD: writes a new memory with a new UUID as its key. Text is `final_text`, or the candidate text if that is empty. Status `active`, version 1.
- UPDATE: writes a new active memory with a new UUID, version one higher than the old one, and `supersedes` pointing at the old one. The old record is then marked `archived` and gets `superseded_by`. Nothing is edited in place.
- DELETE: marks the target memory `archived`. No new memory is written.
- NOOP: does nothing.

UPDATE and DELETE need a `target_memory_id` that exists in the user's namespace. If it is missing or not found, an error is logged and nothing is changed.

Deleting is a soft delete. The record stays in PostgreSQL and only its `status` changes. Everything that reads memories filters on `status = active`, so archived ones are not retrieved or shown. The delete button and "Clear all memories" in the UI work the same way: they set `status` to `archived` and don't remove rows.

### Memory retrieval for replies

In the `chat` node, the content of the latest message is used as the search query against the user's active memories, with `limit=5`. Results with a score below 0.20 are dropped, and the text of the rest goes into the prompt. If retrieval throws an error, it is logged and the reply is generated without memories.

The search is a similarity search over the `text` field of each memory:

- Embedding model: `sentence-transformers/all-MiniLM-L6-v2`, loaded through `langchain-huggingface`
- Dimensions: 384
- Index: configured on the `PostgresStore` through `create_embedding_config()`, on the `text` field of each memory

The resolver's lookup uses the same store, filter and embeddings. The differences are the query text (the candidate instead of the latest message) and that it has no score cutoff.

### Explicit "remember" requests

In `trigger_ltm`, if the latest user message contains the text `remember` (case-insensitive, so it also matches words like "remembered"), the message is handled right away instead of waiting for the 10-message trigger.

For something like "remember that I prefer PyTorch over TensorFlow", this is what happens:

1. The `chat` node answers first, as with any message. The new memory doesn't exist yet at that point, so the reply is generated without it.
2. `trigger_ltm` submits that single message to the background worker and returns. The 10-message check is skipped for this turn.
3. In the background it goes through the same pipeline as above: extraction, retrieval, resolution, then ADD, UPDATE, DELETE or NOOP.

The word "remember" does not force anything to be saved. The extractor still applies its usual rules, and its prompt includes an example where "Remember to explain this concept in simple terms." produces no memory. A message over 2000 tokens is skipped with a warning.

This path does not read or change the processed-message counter in `ltm_metadata`.

The chat shows no confirmation. If a memory is saved, it appears in the memory dialog once the job finishes.

### Automatic extraction

For other messages, `trigger_ltm` reads how many messages of the thread were already processed (`ltm_metadata.processed_message_count`). When at least 10 messages (user and assistant together) are past that point, a batch is sent to the background worker. That is roughly every 5 user/assistant exchanges. After a successful run, the counter moves to the position the batch reached.

## Background processing

LTM processing means one extraction call per batch plus one resolution call per candidate memory, so it runs outside the request. `chatbot.py` creates a `ThreadPoolExecutor(max_workers=1)`, so there is one worker thread and jobs run one after another. Streamlit and the graph don't wait for it.

For the automatic path, an in-memory set tracks which users currently have a batch running. If a user's batch is still running when the next trigger comes, the trigger is skipped. The set entry is removed when the job finishes, whether it succeeded or not.

When a job finishes, a callback handles the result:

- Success: the failure count for the thread is cleared and the processed-message counter is updated.
- `BadRequestError` (from Groq) or `OutputParserException`: these mean the batch itself is probably the problem. A per-thread failure count goes up. After 3 failures, the batch is skipped by moving the counter past it, and the count is reset. The count lives in process memory, so it resets if the app restarts.
- Any other exception: it is logged. The counter doesn't move, so the same messages are tried again the next time the trigger fires.

Explicit "remember" jobs only log success or failure. They have no retry or skip logic.

Failures elsewhere don't stop the conversation. A failed STM summary leaves the state unchanged, a failed memory lookup gives a reply without memories, and a failed title generation falls back to "New Conversation". If the chat model call itself fails, the UI shows an error message, and if it was the first message of a new chat, that thread is not added to the sidebar.

## Database

Application state and persistent memory are stored in one PostgreSQL database.

| What | Created by | Notes |
|---|---|---|
| Conversation state (messages, `summary`, `summary_message_count`) | `PostgresSaver(...).setup()` | LangGraph checkpoint tables. State is keyed by `thread_id`. |
| Long-term memories and their embeddings | `PostgresStore(..., index=...).setup()` | Namespace `(user_id, "memories")`. Embeddings are 384 dimensions. |
| `chat_titles` (`thread_id`, `title`, `user_id`) | `create_title_table()` in `utils.py`, called at the top of `app.py` | Sidebar titles, and which threads belong to which user. |
| `ltm_metadata` (`thread_id`, `processed_message_count`) | `create_ltm_metadata_table()` in `memory.py`, called from `create_chatbot()` | How far into each thread automatic LTM has already processed. |

These are created automatically on startup.

Connection handling:

- `create_chatbot()` creates two separate `psycopg_pool.ConnectionPool`s, one for the checkpointer and one for the store (1 to 5 connections each, autocommit on).
- `memory.py` has a third pool (1 to 5 connections) for the `ltm_metadata` queries. It is created when the module is imported.
- The functions in `utils.py` that read and write `chat_titles` open a short `psycopg.connect(...)` per call.
- `create_chatbot()` is wrapped in `st.cache_resource`, so the graph and its pools are created once per Streamlit server process.

## Project structure

```
.
├── app.py              Streamlit UI: sidebar, chat, memory dialog
├── chatbot.py          LangGraph graph: summarize, chat, trigger_ltm; DB pools; background LTM worker
├── memory.py           LTM pipeline: extraction, resolution, applying decisions, retrieval, ltm_metadata
├── prompt.py           All prompts (STM summary, chat, extraction, resolution, title)
├── utils.py            Title generation and chat_titles queries, thread deletion, math delimiter conversion
├── identity.py         Cookie-based user ID
├── logging_config.py   Logging setup (console + logs/chatbot.log)
├── docker-compose.yml  PostgreSQL with pgvector
├── requirements.txt
├── .env.example
└── evaluation/         Scripts and data for testing the memory pipeline
```

`logs/` is created automatically the first time the app starts and is in `.gitignore`. Logging is at INFO level. The log file rotates at 5 MB and keeps 5 old files.

## Setup

You need Python 3.10+ for local development, Docker with Docker Compose for PostgreSQL, and a Groq API key from https://console.groq.com.


```bash
git clone <repo-url>
cd <repo-folder>

python -m venv venv

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

Create your `.env` file from the example:

```bash
# Linux / macOS
cp .env.example .env
# Windows
copy .env.example .env
```

Then open `.env` and put your Groq key in it (see the next section). Start PostgreSQL:

```bash
docker compose up -d
```

Give the database a few seconds to start, then run the app from the project root:

```bash
streamlit run app.py
```

On the first run the app creates the tables. The embedding model is loaded by name through `HuggingFaceEmbeddings`, so the first start also downloads it.

## Environment variables

A `.env` file in the project root is loaded with `load_dotenv()` (python-dotenv).

| Variable | Needed for | Notes |
|---|---|---|
| `GROQ_API_KEY` | All LLM calls | Not read anywhere in this repo's code. `ChatGroq` picks it up from the environment. |
| `POSTGRES_URI` | All database access | Must match the database started by `docker-compose.yml`. `memory.py` raises an error at import time if it is missing. |

`.env.example` contains:

```
GROQ_API_KEY=your_groq_api_key_here
POSTGRES_URI=postgresql://postgres:postgres@localhost:5432/chatbot
```

The `POSTGRES_URI` in the example matches the values in `docker-compose.yml`. If you change the user, password, database name or port in the compose file, change the URI to match. `.env` is in `.gitignore` and should not be committed.

## Docker / PostgreSQL

There are two ways to run the application:

1. **Local development** — install the Python dependencies and use `docker compose` for PostgreSQL.
2. **Docker image** — run the pre-built chatbot image without cloning the project or installing Python dependencies locally.

### Local PostgreSQL with Docker Compose

The included `docker-compose.yml` starts PostgreSQL 17 with the pgvector extension:

* Image: `pgvector/pgvector:pg17`
* Container name: `chatbot-postgres`
* Database: `chatbot`
* User: `postgres`
* Port: `127.0.0.1:5432`
* Data: stored in the named Docker volume `postgres_data`

Start it with:

```bash
docker compose up -d
```

Then run the Streamlit application normally:

```bash
streamlit run app.py
```

### Run the Pre-built Docker Image

The chatbot image is available on Docker Hub:

`ramanpreet931/langgraph-chatbot:latest`

You do **not** need the project source code, Python, a virtual environment, or `requirements.txt` to use the image.

Docker will automatically pull an image from Docker Hub when it is not already available locally.

#### 1. Start PostgreSQL

Run:

```powershell
docker run -d --name chatbot-postgres `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=chatbot `
  pgvector/pgvector:pg17
```

If the PostgreSQL image is not already on your machine, Docker pulls it automatically.

#### 2. Start the chatbot

Run:

```powershell
docker run --name langgraph-chatbot `
  --link chatbot-postgres:postgres `
  -p 8501:8501 `
  -e GROQ_API_KEY="YOUR_GROQ_API_KEY" `
  -e POSTGRES_URI="postgresql://postgres:postgres@postgres:5432/chatbot" `
  ramanpreet931/langgraph-chatbot:latest
```

Replace `YOUR_GROQ_API_KEY` with your own Groq API key.

The API key is passed directly to the running container as an environment variable. It is not stored in the Docker image.

The chatbot will be available at:

```text
http://localhost:8501
```

The PostgreSQL database and chatbot run in separate containers. The `--link` option allows the chatbot container to reach PostgreSQL using the hostname `postgres`.

### Stop the Containers

If the chatbot is running in the terminal, press:

```text
Ctrl + C
```

Then stop PostgreSQL with:

```powershell
docker stop chatbot-postgres
```

To remove the containers:

```powershell
docker rm langgraph-chatbot chatbot-postgres
```

The PostgreSQL data is stored in Docker's container storage unless a volume is explicitly used. For persistent database data when recreating the PostgreSQL container, use a named volume:

```powershell
docker run -d --name chatbot-postgres `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=chatbot `
  -v chatbot_postgres_data:/var/lib/postgresql/data `
  pgvector/pgvector:pg17
```

This volume keeps the PostgreSQL data when the container itself is removed.


## Evaluation

The `evaluation/` folder evaluates the long-term memory system at both the component and end-to-end levels.

It includes separate tests for **memory extraction, retrieval, and resolution**, along with end-to-end cases that check how the complete pipeline updates the stored memory state.

The evaluation cases are hand-written, with a focus on realistic conversations and edge cases rather than benchmark-scale data. The results are used to identify where the memory system works reliably and where it can make incorrect additions, updates, deletions, or no-op decisions.

### Memory Extraction

I tested extraction in two situations: explicit `remember` requests and normal 10-message conversations.

For explicit requests, I used 25 cases covering preferences, goals, projects, facts, and requests that should not be stored. The extractor got the intended memory in the cases where a memory was expected and correctly returned nothing for temporary requests such as remembering to explain something later. One notable error was classifying *“I usually code using Python 3.10”* as a preference instead of a fact. Since type is not used downstream, this does not affect the pipeline.

The 10-message cases were less consistent. It handled straightforward cases such as the user's goal, existing projects, and hardware, but missed some information that was spread across the conversation. For example, it missed an existing LangGraph project in one conversation and a new legal-document RAG project in another.

The main issue from these tests is that extraction is much easier when the user states something directly than when the information has to be picked out of a longer conversation.

### Retrieval for Resolution

The retrieval tests check whether relevant existing memories can be found for a new memory candidate. Across the test cases, relevant memories were consistently retrieved in the top results (`Recall@5 = 1.0`). An unrelated query also returned results, since the retriever ranks the closest memories rather than deciding whether a relevant memory exists.

### Memory Resolution

The resolution stage was evaluated using 20 hand-written cases covering the four possible decisions: `ADD`, `NOOP`, `UPDATE`, and `DELETE`.

The cases cover common situations such as adding completely new information, recognizing semantically equivalent memories, replacing outdated information with a newer value, and removing memories that are no longer valid. The resolver correctly handled all 20 cases.

For `NOOP`, the tests include both exact matches and differently worded memories with the same meaning. The `UPDATE` cases cover changes to existing facts, preferences, and goals, while the `DELETE` cases test situations where previously stored information is explicitly no longer true.

These cases are intentionally clear rather than highly ambiguous. They verify that the resolver can reliably distinguish the four actions under well-defined conditions. More ambiguous situations, such as deciding between `ADD` and `UPDATE` when information is only partially related, are not covered by this small evaluation set.

### End-to-End Evaluation

The end-to-end evaluation covers both **automatic cases** from normal conversations and **explicit `remember` requests**.

The **automatic cases** handled most clear situations correctly: temporary conversations were ignored, new preferences and goals were added, changed information was updated, outdated memories were removed, and existing information returned `NOOP`.

There were three failures. In **case 007**, the deployment goal was correctly added, but the statement about not going into DevOps was stored as a new memory instead of `NOOP`. In **cases 014 and 015**, the user stopped learning LangChain/LangGraph and LLM evaluation respectively. The extractor and retrieval worked correctly, but the resolver chose `UPDATE` instead of `DELETE`. This shows that the resolver can still **confuse `DELETE` and `UPDATE`, especially when the user is dropping or stopping something**.

The **explicit cases all behaved as expected**, including `ADD`, `UPDATE`, `NOOP`, and `DELETE`, while temporary or non-memory requests were ignored.

The evaluation is based on a small set of hand-written scenarios, so it mainly tests clear cases and does not cover many ambiguous situations.

### Chat Memory Retrieval

The retriever was tested with positive, borderline, and negative queries. It retrieved the expected memory in most positive cases, while some borderline cases did not retrieve all expected memories. Negative queries could also return weakly similar memories, since the retriever returns the closest matches.

A **0.20 similarity threshold** was used for the chatbot. On this small evaluation, it gave **93.8% positive recall** and a **28.6% negative false-positive rate**. These results are not enough to consider 0.20 an optimal threshold. Also, retrieving an irrelevant memory does not mean it will be used by the chatbot; memories are only used when they are relevant to the current message.

## Limitations

- **LLM-based memory decisions can be wrong.** Extraction and resolution depend on the LLM, so ambiguous conversations can still lead to incorrect memories or actions.

- **`DELETE` vs `UPDATE` can be confused.** The end-to-end evaluation showed failures where the user clearly stopped or dropped something, but the resolver chose `UPDATE` instead of `DELETE`.

- **The evaluation is small and hand-written.** It covers common and relatively clear cases, so it is not enough to claim general performance or an optimal retrieval threshold.

- **No authentication.** Users are identified by a browser-generated UUID, so there is no real account system or cross-device identity.

- **LTM processing is asynchronous.** Memory extraction and updates happen in the background, so newly created or changed memories may not be available immediately.
