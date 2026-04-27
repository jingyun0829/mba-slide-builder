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
NAMES_PATH = Path("names_log.json")  # user_id → display name (set at login, optional)
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


# ---------- name log on disk ----------

def _load_names() -> dict:
    if not NAMES_PATH.exists():
        return {}
    try:
        return json.loads(NAMES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_names(names: dict) -> None:
    try:
        NAMES_PATH.write_text(json.dumps(names, indent=2), encoding="utf-8")
    except Exception:
        pass


def set_user_name(user_id: str, name: str) -> None:
    name = (name or "").strip()
    if not name:
        return
    names = _load_names()
    names[user_id] = name[:60]  # cap length
    _save_names(names)


def get_user_name(user_id: str) -> str:
    return _load_names().get(user_id, "")


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
    # We KEEP the code in the URL after auto-login so that if Streamlit Cloud
    # disconnects after idle (~5 min), the next page-load auto-logs in again
    # — the user sees no interruption. Trade-off: code is visible in URL,
    # but for a beta with a single global invite code that's meant to be
    # shared anyway, this is acceptable.
    qp_code = st.query_params.get("code")
    if qp_code and qp_code.strip() == get_invite_code():
        st.session_state["auth_ok"] = True
        _ensure_user_id()
        st.rerun()

    # Otherwise render the login screen
    st.markdown(
        """
        <div style="max-width:520px;margin:8vh auto 0;padding:0 24px;">
          <h1 style="font-family:'Source Serif Pro',Georgia,serif;font-size:54pt;
                     margin:0 0 4px;color:#0d9488;letter-spacing:-2px;line-height:1;">
            SlideGen
          </h1>
          <div style="font-size:11pt;color:#94a3b8;letter-spacing:3px;
                      text-transform:uppercase;margin:0 0 18px;font-weight:600;">
            AI course decks · for B-school instructors
          </div>
          <p style="font-size:14pt;color:#475569;margin:0 0 28px;line-height:1.5;">
            Generate slide-by-slide lecture decks in your own teaching style —
            undergrad, MBA, EMBA, or executive ed.
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
            display_name = st.text_input(
                "Your name (optional)",
                placeholder="e.g., Prof. Lee · Wharton",
                help="So Dvora knows who's testing. Leave blank to stay anonymous.",
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
                    uid = _ensure_user_id()
                    if display_name.strip():
                        set_user_name(uid, display_name.strip() + " (admin)")
                    st.success("Welcome, admin. Cap removed for this session.")
                    st.rerun()
                # Normal path
                elif code == get_invite_code():
                    st.session_state["auth_ok"] = True
                    uid = _ensure_user_id()
                    if display_name.strip():
                        set_user_name(uid, display_name.strip())
                    # Stamp code into URL so a later disconnect/reconnect
                    # auto-logs back in instead of bouncing to login screen.
                    st.query_params["code"] = code
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


def render_admin_panel() -> None:
    """Admin-only usage dashboard. Shows who's using the app and how much.
    Call right after render_usage_badge() in app.py."""
    if not is_admin():
        return

    log = _load_log()
    names = _load_names()
    # Merge: every named user appears in admin view, even if they haven't built a deck yet
    all_user_ids = set(log.keys()) | set(names.keys())
    total_users = len(all_user_ids)
    total_decks = sum(log.values()) if log else 0
    cap = get_max_decks()
    named_count = sum(1 for uid in all_user_ids if names.get(uid))

    # Header line, always visible
    header = (f"👑 Admin · **{total_users}** beta user{'s' if total_users != 1 else ''} "
              f"({named_count} named) · **{total_decks}** deck{'s' if total_decks != 1 else ''} built")
    with st.expander(header, expanded=False):
        if not all_user_ids:
            st.info("No users yet. Once people log in with the invite code, "
                    "they'll show up here — with real names if they fill in the "
                    "optional 'Your name' field at login.")
            st.caption("⚠️ This list resets when Streamlit Cloud restarts the container "
                       "(e.g., after a code push). For long-term tracking, use "
                       "Manage app → Analytics.")
            return

        # Top metrics
        c1, c2, c3 = st.columns(3)
        c1.metric("Beta users", total_users)
        c2.metric("Total decks", total_decks)
        avg = total_decks / total_users if total_users else 0
        c3.metric("Avg per user", f"{avg:.1f}")

        # Engagement summary
        used_all = sum(1 for uid in all_user_ids if log.get(uid, 0) >= cap)
        active = sum(1 for uid in all_user_ids if 1 <= log.get(uid, 0) < cap)
        zero = total_users - used_all - active
        st.caption(
            f"**Engagement:** {used_all} hit the {cap}-deck cap · "
            f"{active} are mid-quota · "
            f"{zero} just registered (0 decks)"
        )

        st.markdown("**Per-user breakdown** (sorted by usage):")
        # Sort: by deck count desc, then named ones first
        sorted_users = sorted(
            all_user_ids,
            key=lambda uid: (-log.get(uid, 0), 0 if names.get(uid) else 1)
        )
        for uid in sorted_users:
            count = log.get(uid, 0)
            name = names.get(uid, "")
            pct = min(1.0, count / cap) if cap else 0
            display = name if name else f"(anonymous · {uid[:8]}…)"
            label = f"**{display}** — {count}/{cap} decks"
            if count >= cap:
                label += " 🔥"
            st.progress(pct, text=label)

        st.markdown("---")
        c_reset, c_caption = st.columns([1, 3])
        with c_reset:
            if st.button("🔄 Reset all quotas", key="admin_reset_all",
                         help="Clears every user's deck counter. They'll get a fresh quota."):
                USAGE_PATH.unlink(missing_ok=True)
                st.success("All quotas reset.")
                st.rerun()
        with c_caption:
            st.caption(
                "⚠️ This counter lives in a file on Streamlit Cloud. "
                "It **resets automatically** if the container restarts "
                "(e.g., after a code push or scheduled reboot). "
                "For long-term analytics, see Manage app → Analytics."
            )
