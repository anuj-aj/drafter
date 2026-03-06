import json
from typing import Any, Dict, Optional

import requests
import streamlit as st


def _url_join(base: str, path: str) -> str:
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _get_json(url: str) -> Dict[str, Any]:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


st.set_page_config(page_title="Drafter AI", layout="wide")

st.title("Drafter AI — Streamlit UI")

with st.sidebar:
    st.header("API")
    api_base_url = st.text_input("Base URL", value=st.session_state.get("api_base_url", "http://127.0.0.1:8000"))
    st.session_state["api_base_url"] = api_base_url

    st.divider()

    st.header("Start")
    default_index = 0
    if st.session_state.get("start_mode") == "Open existing document":
        default_index = 1
    elif "start_mode" not in st.session_state and st.session_state.get("document_id"):
        default_index = 1

    start_mode = st.radio(
        "Choose",
        options=["Create new document", "Open existing document"],
        index=default_index,
    )
    st.session_state["start_mode"] = start_mode

    doc_id_input = st.session_state.get("document_id", "")
    new_title = st.session_state.get("new_title", "Untitled")
    new_content = st.session_state.get("new_content", "")

    load_clicked = False
    create_clicked = False

    if start_mode == "Open existing document":
        doc_id_input = st.text_input("Document ID", value=doc_id_input)
        load_clicked = st.button("Open", use_container_width=True)
    else:
        new_title = st.text_input("Title", value=new_title)
        st.session_state["new_title"] = new_title
        new_content = st.text_area("Initial content (optional)", value=new_content, height=120)
        st.session_state["new_content"] = new_content
        create_clicked = st.button("Create", use_container_width=True)

    st.divider()

    if st.session_state.get("document_id"):
        st.caption(f"Current document: {st.session_state.get('document_id')}")
    clear_clicked = st.button("Clear session", use_container_width=True)

if clear_clicked:
    for key in [
        "document_id",
        "document",
        "draft",
        "last_interact",
        "last_apply",
        "last_error",
    ]:
        st.session_state.pop(key, None)

if create_clicked:
    try:
        created = _post_json(
            _url_join(api_base_url, "/documents"),
            {"title": new_title, "content": st.session_state.get("new_content", "")},
        )
        st.session_state["document_id"] = created.get("id")
        st.session_state["document"] = created
        st.session_state["draft"] = None
        st.session_state["last_error"] = None
    except Exception as e:  # noqa: BLE001
        st.session_state["last_error"] = str(e)

if load_clicked:
    if not doc_id_input.strip():
        st.session_state["last_error"] = "Enter a document ID to load."
    else:
        try:
            document = _get_json(_url_join(api_base_url, f"/documents/{doc_id_input.strip()}"))
            st.session_state["document_id"] = doc_id_input.strip()
            st.session_state["document"] = document
            # Draft is optional; fetch it best-effort
            try:
                draft_resp = _get_json(_url_join(api_base_url, f"/documents/{doc_id_input.strip()}/draft"))
                st.session_state["draft"] = draft_resp if draft_resp.get("status") != "no_draft" else None
            except Exception:
                st.session_state["draft"] = None
            st.session_state["last_error"] = None
        except Exception as e:  # noqa: BLE001
            st.session_state["last_error"] = str(e)

if st.session_state.get("last_error"):
    st.error(st.session_state["last_error"])


document_id = st.session_state.get("document_id")
document = st.session_state.get("document")
draft = st.session_state.get("draft")

col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Live Document")
    if not document:
        st.caption("Create or load a document to begin.")
    else:
        st.text_input("Title", value=document.get("title", ""), disabled=True)
        st.text_input("Version", value=str(document.get("version", "")), disabled=True)
        st.text_area("Content", value=document.get("content", ""), height=320, disabled=True)

with col_right:
    st.subheader("Current Draft (Proposed)")
    if not document_id:
        st.caption("No document selected.")
    else:
        draft_content = ""
        if draft and isinstance(draft, dict):
            draft_content = draft.get("content") or ""
        st.text_area("Draft content", value=draft_content, height=320, disabled=True)

st.divider()

st.subheader("Interact")
user_input = st.text_area("User input", value=st.session_state.get("user_input", ""), height=120)

col_i1, col_i2 = st.columns([1, 1])
with col_i1:
    interact_clicked = st.button("Send", use_container_width=True, disabled=not bool(document_id))
with col_i2:
    refresh_clicked = st.button("Refresh doc + draft", use_container_width=True, disabled=not bool(document_id))

if interact_clicked and document_id:
    try:
        result = _post_json(
            _url_join(api_base_url, f"/documents/{document_id}/interact"),
            {"user_input": user_input},
        )
        st.session_state["last_interact"] = result
        st.session_state["user_input"] = user_input

        # Update draft if present
        if isinstance(result, dict) and result.get("draft"):
            st.session_state["draft"] = result.get("draft")

        # Refresh document to show version changes when /interact auto-applies
        st.session_state["document"] = _get_json(_url_join(api_base_url, f"/documents/{document_id}"))
        st.session_state["last_error"] = None
    except Exception as e:  # noqa: BLE001
        st.session_state["last_error"] = str(e)

if refresh_clicked and document_id:
    try:
        st.session_state["document"] = _get_json(_url_join(api_base_url, f"/documents/{document_id}"))
        draft_resp = _get_json(_url_join(api_base_url, f"/documents/{document_id}/draft"))
        st.session_state["draft"] = draft_resp if draft_resp.get("status") != "no_draft" else None
        st.session_state["last_error"] = None
    except Exception as e:  # noqa: BLE001
        st.session_state["last_error"] = str(e)

st.divider()

st.subheader("Apply Draft")
expected_version_default = ""
if isinstance(document, dict) and document.get("version") is not None:
    expected_version_default = str(document.get("version"))
expected_version = st.text_input("expected_version (optional)", value=expected_version_default, disabled=not bool(document_id))
apply_clicked = st.button("Apply", use_container_width=True, disabled=not bool(document_id))

if apply_clicked and document_id:
    payload: Dict[str, Any] = {}
    if expected_version.strip():
        try:
            payload["expected_version"] = int(expected_version.strip())
        except ValueError:
            st.session_state["last_error"] = "expected_version must be an integer."
            payload = {}

    if payload is not None:
        try:
            result = _post_json(_url_join(api_base_url, f"/documents/{document_id}/apply-update"), payload)
            st.session_state["last_apply"] = result
            st.session_state["document"] = _get_json(_url_join(api_base_url, f"/documents/{document_id}"))
            # Draft should be deleted after apply; refresh
            try:
                draft_resp = _get_json(_url_join(api_base_url, f"/documents/{document_id}/draft"))
                st.session_state["draft"] = draft_resp if draft_resp.get("status") != "no_draft" else None
            except Exception:
                st.session_state["draft"] = None
            st.session_state["last_error"] = None
        except Exception as e:  # noqa: BLE001
            st.session_state["last_error"] = str(e)

with st.expander("Last /interact response"):
    st.code(json.dumps(st.session_state.get("last_interact"), indent=2), language="json")

with st.expander("Last /apply-update response"):
    st.code(json.dumps(st.session_state.get("last_apply"), indent=2), language="json")
