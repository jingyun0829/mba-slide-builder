"""Invite-code authentication + per-user usage cap.

Strategy
--------
- A single public invite code (configured via st.secrets["INVITE_CODE"], default
  "BETA2026"). Users type it on the login screen.
- Each successful login generates a unique user_id (UUID) stored in
  st.session_state. The user_id stays in the URL as ?u=<uuid> so the user
  doesn't have to re-enter the code on refresh / share.
- Per-user_id usage counter persists in a JSON file on disk (usage_log.json).
  This works fine on Streamlit Community Cloud — the file lives across reruns
  within a session, and even if the app restarts, the URL ?u= persists, so a
  fresh container will recognize the user (counter resets on container restart,
  which is acceptable: it just gives the user a free re-roll).
- Cap defaults to 3 decks per user (st.secrets["MAX_DECKS_PER_USER"]).

Why store user_id in URL
------------------------
Streamlit has no built-in way to set a real cookie. Query params are the
closest thing — they survive page refresh and tab close+reopen as long as the
user uses the same URL. Good enough for a beta.
"""
from __future__ import annotations
import json
import os
import uuid
from pathlib import Path
from typing import Optional

import streamlit as st

USAGE_PATH = Path("usage_log.json")
DEFAULT_INVITE_CODE = "BETA2026"
DEFAULT_CAP = 3


# ---------- secrets helpers ----------

def get_invite_code() -> str:
    try:
        return str(st.secrets.get("INVITE_CODE", DEFAULT_INVITE_CODE)).strip()
    except Exception:
        return os.environ.get("INVITE_CODE", DEFAULT_INVITE_CODE).strip()


def get_max_decks() -> int:
    try:
        return int(st.secrets.get("MAX_DECKS_PER_USER", DEFAULT_CAP))
    except Exception:
        return int(os.environ.get("MAX_DECKS_PER_USER", DEFAULT_CAP))


def get_admin_pass() -> Optional[str]:
    """Optional admin password — bypasses the cap and lets you reset users.
    Set st.secrets["ADMIN_PASS"] to enable. Leave unset to disable."""
    try:
        v = st.secrets.get("ADMIN_PASS")
        return str(v) if v else None
    except Exception:
        return os.environ.get("ADMIN_PASS")


# ---------- usage log on disk ----------

def _load_log() -> dict:
    if not USAGE_PATH.exists():
        return {}
    try:
        return json.loads(USAGE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_log(log: dict) -> None:
    try:
        USAGE_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")
    except Exception:
        pass  # ephemeral filesystem on Streamlit Cloud — best effort


def get_usage(user_id: str) -> int:
    return int(_load_log().get(user_id, 0))


def increment_usage(user_id: str) -> int:
    log = _load_log()
    log[user_id] = int(log.get(user_id, 0)) + 1
    _save_log(log)
    return log[user_id]


def reset_user(user_id: str) -> None:
    log = _load_log()
    log.pop(user_id, None)
    _save_log(log)


# ---------- session helpers ----------

def _ensure_user_id() -> str:
    """Get a stable user_id for this session.

    Order of preference:
    1. Already in st.session_state — use it.
    2. ?u=<uuid> in the URL — adopt it (e.g., user refreshed page).
    3. Generate a new one and stamp it into the URL.
    """
    if st.session_state.get("user_id"):
        return st.session_state["user_id"]

    qp = st.query_params
    url_uid = qp.get("u")
    if url_uid:
        st.session_state["user_id"] = url_uid
        return url_uid

    new_id = uuid.uuid4().hex[:12]
    st.session_state["user_id"] = new_id
    qp["u"] = new_id  # add to URL so refresh keeps it
    return new_id


def is_authenticated() -> bool:
    return bool(st.session_state.get("auth_ok"))


def is_admin() -> bool:
    return bool(st.session_state.get("is_admin"))


def remaining_decks() -> int:
    """How many more decks this user can build. Admins are unlimited."""
    if is_admin():
        return 9999
    uid = _ensure_user_id()
    return max(0, get_max_decks() - get_usage(uid))


def can_build() -> bool:
    return is_admin() or remaining_decks() > 0


def consume_deck() -> int:
    """Call this AFTER a successful build. Returns new total usage."""
    if is_admin():
        return 0
    uid = _ensure_user_id()
    return increment_usage(uid)


# ---------- the login screen ----------

def render_login_gate() -> bool:
    """Show login form if not authenticated. Returns True if user is in.
    Call this at the top of app.py before rendering anything else."""
    if is_authenticated():
        return True

    # Try query-param fast-path: if ?code=... matches, auto-login.
    # (Useful for invite links you send: https://your.app/?code=BETA2026)
    qp_code = st.query_params.get("code")
    if qp_code and qp_code.strip() == get_invite_code():
        st.session_state["auth_ok"] = True
        _ensure_user_id()
        # Strip the code out of the URL so it isn't shoulder-surfed
        try:
            del st.query_params["code"]
        except Exception:
            pass
        st.rerun()

    # Otherwise render the login screen
    st.markdown(
        """
        <div style="max-width:520px;margin:8vh auto 0;padding:0 24px;">
          <h1 style="font-family:'Source Serif Pro',Georgia,serif;font-size:38pt;
                     margin:0 0 8px;color:#0d9488;letter-spacing:-1px;">
            MBA Slide Builder
          </h1>
          <p style="font-size:14pt;color:#475569;margin:0 0 28px;line-height:1.5;">
            AI-generated course decks for business school instructors.
            Currently in <strong>private beta</strong> — please enter your
            invite code below.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns([1, 2, 1])
    with cols[1]:
        with st.form("login_form", clear_on_submit=False):
            code = st.text_input(
                "Invite code",
                placeholder="e.g., BETA2026",
                help="Don't have one? Email dvora5018@gmail.com",
            )
            submitted = st.form_submit_button("Sign in", type="primary",
                                              use_container_width=True)
            if submitted:
                code = (code or "").strip()
                # Admin path
                admin_pw = get_admin_pass()
                if admin_pw and code == admin_pw:
                    st.session_state["auth_ok"] = True
                    st.session_state["is_admin"] = True
                    _ensure_user_id()
                    st.success("Welcome, admin. Cap removed for this session.")
                    st.rerun()
                # Normal path
                elif code == get_invite_code():
                    st.session_state["auth_ok"] = True
                    _ensure_user_id()
                    st.success(f"Welcome! You can build up to "
                               f"{get_max_decks()} decks. Loading...")
                    st.rerun()
                else:
                    st.error("Invalid invite code. Email dvora5018@gmail.com to request access.")
        st.caption(
            f"Quota: each invitee can generate **{get_max_decks()} decks**. "
            "Want more? Email the admin and we'll extend your quota."
        )
    return False


def render_usage_badge() -> None:
    """Small inline badge showing remaining decks. Call from app.py after login."""
    if not is_authenticated():
        return
    if is_admin():
        st.caption("👑 **Admin** — no quota limit.")
        return
    rem = remaining_decks()
    cap = get_max_decks()
    used = cap - rem
    if rem == 0:
        st.error(
            f"⚠️ Quota exhausted ({used}/{cap} decks built). "
            "Email **dvora5018@gmail.com** to request more."
        )
    elif rem == 1:
        st.warning(f"⚠️ {used}/{cap} decks built. **1 build remaining.**")
    else:
        st.caption(f"📊 {used}/{cap} decks built · **{rem} remaining**.")
