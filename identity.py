import datetime
import uuid
import streamlit as st
import extra_streamlit_components as stx

COOKIE_NAME = "chatbot_user_id"
COOKIE_LIFETIME = datetime.timedelta(days=365 * 5)


def _get_cookie_manager():

    if "cookie_manager" not in st.session_state:
        st.session_state["cookie_manager"] = stx.CookieManager(key="user_id_cookie_manager")

    return st.session_state["cookie_manager"]


def get_user_id() -> str:
    cookie_manager = _get_cookie_manager()

    cookies = cookie_manager.get_all()

    user_id = cookies.get(COOKIE_NAME)

    # CookieManager may need a few Streamlit reruns before
    # the browser cookie becomes available.
    if user_id is None:
        attempts = st.session_state.get("_cookie_attempts", 0)

        if attempts < 5:
            st.session_state["_cookie_attempts"] = attempts + 1
            st.stop()

        # Cookie did not become available after several attempts.
        st.session_state.pop("_cookie_attempts", None)

        user_id = str(uuid.uuid4())

        cookie_manager.set(
            COOKIE_NAME,
            user_id,
            key="set_user_id_cookie",
            expires_at=datetime.datetime.now() + COOKIE_LIFETIME,
        )

        return user_id

    # Cookie exists, so keep using it.
    st.session_state.pop("_cookie_attempts", None)

    return str(user_id)