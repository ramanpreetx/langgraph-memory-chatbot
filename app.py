import logging_config
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from chatbot import create_chatbot
from memory import get_user_memories, delete_user_memory, clear_user_memories
from utils import generate_id, generate_title, fetch_user_threads, create_title_table, save_title, fetch_titles, delete_title, delete_thread, normalize_math
from identity import get_user_id
import logging
import html
import os
from groq import Groq

logger = logging.getLogger(__name__)

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("GROQ_API_KEY is not set.")
    st.info("Set your Groq API key and restart the application.")
    st.stop()

try:
    client = Groq(api_key=api_key)
    client.models.list()
except Exception:
    st.error("The GROQ_API_KEY is invalid or could not be authenticated.")
    st.info("Check your API key and restart the application.")
    st.stop()


try:
    create_title_table()
except Exception:
    st.error("Can't reach PostgreSQL – is docker compose up?")
    st.stop()

# USER IDENTITY

if "user_id" not in st.session_state:

    st.session_state["user_id"] = get_user_id()

user_id = st.session_state["user_id"]

# CREATE CHATBOT

if "chatbot" not in st.session_state:

    try:
        st.session_state.chatbot = create_chatbot()
    except Exception:
        st.error("Can't reach PostgreSQL – is docker compose up?")
        st.stop()

chatbot = st.session_state.chatbot


# INITIALIZE SESSION STATE

if "chat_threads" not in st.session_state:

    st.session_state["chat_threads"] = fetch_user_threads(user_id)


if "chat_titles" not in st.session_state:

    st.session_state["chat_titles"] = fetch_titles(user_id)


if "thread_id" not in st.session_state:

    st.session_state["thread_id"] = None

# STREAMLIT UI

st.markdown(
    """
    <style>
    [data-testid="stSidebarContent"] {
        overflow: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# NEW CHAT

if st.sidebar.button("✦\u00A0\u00A0\u00A0New Chat", key="new_chat", use_container_width=True):
    st.session_state["thread_id"] = None
    st.rerun()  

    #st.session_state["thread_id"] = None

    #st.rerun()

# MANAGE MEMORIES

@st.dialog("➲\u00A0\u00A0Manage memories")
def manage_memories():
    memories = get_user_memories(chatbot.store, user_id)

    st.caption(
    'ⓘ  Use "remember" in a message to save something to memory. '
    'The chatbot also automatically checks for useful memories every 5 user messages, '
    'and you can delete any saved memory whenever you want.'
    )

    if not memories:
        st.write("No memories stored yet.")
    else:
        with st.container(height=300, border=False):
            for memory in memories:
                col1, col2 = st.columns([8, 1])

                with col1:
                    st.markdown(
                        f"""
                        <div class="memory-text">
                            {html.escape(memory.value["text"])}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col2:
                    if st.button(
                        "",
                        key=f"delete_memory_{memory.key}"
                    ):
                        delete_user_memory(
                            chatbot.store,
                            user_id,
                            memory.key,
                        )
                        st.rerun()

        st.divider()

        if st.button(
            "Clear all memories",
            use_container_width=True,
        ):

            clear_user_memories(
                chatbot.store,
                user_id,
            )

            st.rerun()

if st.sidebar.button( "⚙\u00A0\u00A0\u00A0Memory", key="manage_memories", use_container_width=True):
    manage_memories()

st.sidebar.write("")
st.sidebar.write("")

st.markdown(
    """
    <style>
    [data-testid="stSidebar"] button[kind="secondary"] {
    border: none;
    border-radius: 8px;
    background: transparent;
    transition: background 0.15s ease, box-shadow 0.15s ease;
    padding-left: 12px;
    }

    [data-testid="stSidebar"] button[kind="secondary"] > div {
        width: 100%;
        justify-content: flex-start;
    }

    /* Conversation titles — selected and unselected */
    /* Conversation titles */
    [data-testid="stHorizontalBlock"]:has(button[kind="tertiary"]) button[kind="secondary"] p,
    [data-testid="stHorizontalBlock"]:has(button[kind="tertiary"]) button[kind="primary"] p {
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        }

    /* Keep conversation title and delete button on the same row */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(button[kind="tertiary"]) {
        flex-wrap: nowrap !important;
        flex-direction: row !important;
    }

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(button[kind="tertiary"]) > div {
        min-width: 0 !important;
    }


    [data-testid="stSidebar"] button[kind="secondary"]:hover {
        background: rgba(255, 255, 255, 0.08);
        box-shadow: 0 0 12px rgba(255, 255, 255, 0.08);
    }

    [data-testid="stSidebar"] {
    background: #000000;
    }

    [data-testid="stSidebarContent"] {
        background: #000000;
    }

    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p {
        color: #ffffff;
    }

    [data-testid="stSidebarHeader"] {
    display: flex;
    align-items: center;
    justify-content: space-between;
    }

    [data-testid="stSidebarHeader"]::after {
        content: "✴\u00A0\u00A0Chatbot";
        order: -1;
        font-size: 18px;
        font-weight: 700;
        color: white;
        white-space: nowrap;
        margin-right: auto;
    }

    [data-testid="stApp"] {
    background: #000000;
    }

    [data-testid="stAppViewContainer"] {
        background: #000000;
    }

    [data-testid="stHeader"] {
        background: #000000;
    }

    [data-testid="stBottom"] {
        background: #000000;
    }

    [data-testid="stBottomBlockContainer"] {
        background: #000000;
    }

    html,
    body {
        background: #000000 !important;
    }

    [data-testid="stBottom"] > div {
        background: #000000 !important;
    }

    [data-testid="stSidebar"] {
    border-right: 1px solid #262626;
    }

    [data-testid="stChatInput"] {
    background: #1A1A1A !important;
    border: 1px solid #333333 !important;
    border-radius: 14px !important;
    }

    [data-testid="stChatInput"] > div {
        background: #1A1A1A !important;
        border-radius: 14px !important;
    }

    /* Conversation delete button */
    [data-testid="stHorizontalBlock"]:has(button) > div:last-child button {
        opacity: 0;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        width: 38px;
        height: 38px;
        transition: opacity 0.15s ease;
    }

    /* Show on conversation hover */
    [data-testid="stHorizontalBlock"]:has(button):hover > div:last-child button {
        opacity: 1;
    }

    /* Large red trash icon */
    [data-testid="stHorizontalBlock"]:has(button) > div:last-child button::before {
        content: "";
        display: block;
        width: 26px;
        height: 26px;
        margin: auto;

        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23ff4d4d' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 6h18'/%3E%3Cpath d='M8 6V4h8v2'/%3E%3Cpath d='M19 6l-1 15H6L5 6'/%3E%3Cpath d='M10 11v6'/%3E%3Cpath d='M14 11v6'/%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: center;
        background-size: contain;
    }

    /* =========================
   Memory Dialog
   ========================= */

    [data-testid="stDialog"] {
        background: #111111 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 16px !important;
    }

    /* Dialog content */
    [data-testid="stDialog"] > div {
        background: #111111 !important;
    }

    /* Memory text */
    [data-testid="stDialog"] p {
        color: #e5e5e5 !important;
    }

    /* Individual memories */
[data-testid="stDialog"] [data-testid="stHorizontalBlock"] {
    position: relative !important;
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;

    width: 100% !important;
    max-width: 100% !important;

    align-items: flex-start !important;

    height: auto !important;
    min-height: 0 !important;

    box-sizing: border-box !important;

    padding: 7px 2px 15px 22px !important;
    margin: 0 !important;

    border-radius: 8px;
    transition: background 0.15s ease;

    overflow: visible !important;
    }

    [data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div {
    min-width: 0 !important;
    max-width: 100% !important;
    height: fit-content !important;
    align-self: flex-start !important;

    padding: 0 !important;
    margin: 0 !important;

    box-sizing: border-box !important;
}

    [data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div:first-child {
    flex: 1 1 auto !important;
    min-width: 0 !important;
    max-width: calc(100% - 32px) !important;
    overflow: visible !important;
    }

    [data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div:last-child {
        flex: 0 0 32px !important;
        width: 32px !important;
        min-width: 32px !important;
    }

    [data-testid="stDialog"] [data-testid="stHorizontalBlock"]::before {
    content: "\u00A0●\u00A0";
    position: absolute;
    left: 2px;
    top: 8px;
    transform: none;
    font-size: 11px;
    color: #777777;
    }

[data-testid="stDialog"] [data-testid="stHorizontalBlock"]:hover {
    background: rgba(255, 255, 255, 0.06);
}


/* Memory delete button */
[data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div:last-child {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

[data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div:last-child [data-testid="stButton"] {
    width: auto !important;
    min-width: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}

[data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div:last-child button {
    opacity: 1 !important;
    width: 32px !important;
    height: 32px !important;
    padding: 0 !important;
    margin: 0 !important;

    display: flex !important;
    align-items: center !important;
    justify-content: center !important;

    background: transparent !important;
    border: none !important;
    box-shadow: none !important;

    color: #999999 !important;
}

[data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div:last-child button:hover {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #ff4d4d !important;
}

/* Center delete button */
[data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div:last-child {
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

    /* Clear all memories */
    [data-testid="stDialog"] button[kind="secondary"] {
        background: #1c1c1c !important;
        border: 1px solid #333333 !important;
        color: #ffffff !important;
    }

    [data-testid="stDialog"] button[kind="secondary"]:hover {
        background: #262626 !important;
        border-color: #444444 !important;
    }


    /* Transparent modal overlay */
    [data-testid="stDialog"] {
        background: transparent !important;
    }

    /* Actual dialog panel */
    [data-testid="stDialog"] > div[role="dialog"] {
        background: #111111 !important;
        border: 1px solid #2a2a2a !important;
        border-radius: 16px !important;
    }

    [data-testid="stDialog"] [data-testid="stHorizontalBlock"]:hover {
        background: rgba(255, 255, 255, 0.06);
    }

    /* Center dialog title */
    [data-testid="stDialog"] div[role="dialog"] > div:first-child {
        text-align: center !important;
    }

    [data-testid="stDialog"] div[role="dialog"] > div:first-child h1 {
        text-align: center !important;
        width: 100% !important;
    }

    [data-testid="stDialog"] [data-testid="stHorizontalBlock"] > div {
        min-width: 0 !important;
        height: auto !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    [data-testid="stDialog"] .memory-text {
    position: static !important;

    display: block !important;

    width: 100% !important;
    max-width: 100% !important;

    height: auto !important;
    min-height: 0 !important;

    margin: 0 !important;
    padding: 0 !important;

    color: #e5e5e5 !important;
    line-height: 1.4 !important;

    white-space: normal !important;
    overflow: visible !important;
    overflow-wrap: anywhere !important;
    word-break: break-word !important;

    box-sizing: border-box !important;
    }

    </style>
    """,
    unsafe_allow_html=True,
)

# SHOW CONVERSATIONS

st.sidebar.subheader("My Conversations")

with st.sidebar.container(height=400, border=False):

    for thread_id in st.session_state["chat_threads"][::-1]:

        title = st.session_state["chat_titles"][thread_id]

        col1, col2 = st.columns([6, 1])

        with col1:

            if st.button(title, key=f"chat_{thread_id}", type="primary" if thread_id == st.session_state["thread_id"] else "secondary", use_container_width=True):

                st.session_state["thread_id"] = thread_id

                st.session_state["chat_threads"].remove(thread_id)
                st.session_state["chat_threads"].append(thread_id)

                st.rerun()

        with col2:

            if st.button(" ", key=f"delete_{thread_id}", type="tertiary"):

                delete_thread(chatbot.checkpointer, thread_id)

                delete_title(thread_id, user_id)

                st.session_state["chat_threads"].remove(thread_id)

                st.session_state["chat_titles"].pop(thread_id)

                if st.session_state["thread_id"] == thread_id:

                    st.session_state["thread_id"] = None

                st.rerun()


# GET CURRENT THREAD

thread_id = st.session_state["thread_id"]

config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}


# LOAD PREVIOUS MESSAGES

state = chatbot.get_state(config)

for message in state.values.get("messages", []):

    if isinstance(message, HumanMessage):

        st.markdown(
            f"""
            <div style="
                display: flex;
                justify-content: flex-end;
                margin: 16px 0;
            ">
                <div style="
                    max-width: 70%;
                    padding: 10px 14px;
                    border-radius: 16px;
                    background: #2563eb;
                    color: white;
                ">
                    {html.escape(message.content)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    else:

        st.markdown(normalize_math(message.content), unsafe_allow_html=False)

# USER INPUT

user_input = st.chat_input("Ask anything...", max_chars=10000)

if st.session_state["thread_id"] is None and not user_input:
    st.markdown(
        """
        <div style="
            text-align: center;
            margin-top: 120px;
        ">
            <div style="
                margin: 0;
                font-size: 2.5rem;
                font-weight: 700;
                color: white;
            ">
                ✴\u00A0\u00A0Chatbot
            </div>
            <p style="
                margin-top: 10px;
                color: #888888;
                font-size: 1rem;
            ">
                Ask questions, explore ideas, or start a conversation.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if user_input:

    is_new_chat = False
    failed = False

    # CREATE NEW THREAD

    if st.session_state["thread_id"] is None:

        thread_id = generate_id()

        st.session_state["thread_id"] = thread_id

        is_new_chat = True

    else:

        thread_id = st.session_state["thread_id"]


    config = {"configurable": {"thread_id": thread_id, "user_id": user_id}}


    # SHOW USER MESSAGE
    st.markdown(
            f"""
            <div style="
                display: flex;
                justify-content: flex-end;
                margin: 16px 0;
            ">
                <div style="
                    max-width: 70%;
                    padding: 10px 14px;
                    border-radius: 16px;
                    background: #2563eb;
                    color: white;
                ">
                    {html.escape(user_input)}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    

        
    # GENERATE AI RESPONSE

    full_response = ""

    placeholder = st.empty()

    try:
        for message_chunk, metadata in chatbot.stream(
            {
                "messages": [
                    HumanMessage(content=user_input)
                ]
            },
            config=config,
            stream_mode="messages"
        ):
            if metadata.get("langgraph_node") != "chat":
                continue

            if message_chunk.content:

                full_response += message_chunk.content

                placeholder.markdown(normalize_math(full_response), unsafe_allow_html=False)

    except Exception as e:

        failed = True

        logger.error("Chat failed: %s", e)
        placeholder.error("Sorry, something went wrong. Please try again.")

    # GENERATE TITLE

    if is_new_chat and failed:

        st.session_state["thread_id"] = None

    if is_new_chat and not failed:

        title = generate_title(user_input, full_response)

        st.session_state["chat_titles"][thread_id] = title

        save_title(thread_id, title, user_id)

        st.session_state["chat_threads"].append(thread_id)

        st.rerun()