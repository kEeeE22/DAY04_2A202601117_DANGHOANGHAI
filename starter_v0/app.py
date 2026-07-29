"""
Paper Scout — Streamlit UI
Run: streamlit run app.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

# ── path setup so imports from the project work ──────────────────────────────
ROOT = Path(__file__).parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from env_loader import load_lab_env
load_lab_env(ROOT)

from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from chat import run_model_tool_loop, trim_history

# ── constants ────────────────────────────────────────────────────────────────
ARTIFACTS_DIR = ROOT / "artifacts"
SYSTEM_PROMPT_PATH = ARTIFACTS_DIR / "system_prompt.md"
TOOLS_YAML_PATH = ARTIFACTS_DIR / "tools.yaml"

PROVIDERS = ["openai", "openrouter", "anthropic", "gemini"]
PROVIDER_MODELS: dict[str, list[str]] = {
    "openai":     ["gpt-4o", "gpt-4o-mini", "gpt-4.1"],
    "openrouter": ["openai/gpt-4o", "openai/gpt-4o-mini", "google/gemini-2.0-flash-001"],
    "anthropic":  ["claude-sonnet-4-5", "claude-haiku-4-5"],
    "gemini":     ["gemini-2.0-flash", "gemini-2.5-flash"],
}

TOOL_ICONS: dict[str, str] = {
    "papers":         "🔍",
    "paper_text":     "📄",
    "citation_lookup":"📚",
    "format":         "📝",
    "clarify":        "❓",
    "policy":         "📋",
    "lookup":         "🌐",
    "fetch":          "🔗",
    "social_search":  "📣",
    "timeline":       "🕐",
    "send":           "📤",
}

# ── page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Paper Scout",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* \u2500\u2500 gradient background \u2500\u2500 */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #f0f4ff 0%, #e8edff 40%, #eef2ff 100%);
    min-height: 100vh;
}
[data-testid="stSidebar"] {
    background: rgba(255, 255, 255, 0.92) !important;
    border-right: 1px solid rgba(139, 92, 246, 0.2);
}

/* \u2500\u2500 header \u2500\u2500 */
.ps-header {
    background: linear-gradient(90deg, rgba(139,92,246,0.12), rgba(59,130,246,0.08));
    border: 1px solid rgba(139,92,246,0.25);
    border-radius: 16px;
    padding: 20px 28px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
}
.ps-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700;
    background: linear-gradient(90deg, #7c3aed, #2563eb); -webkit-background-clip: text;
    -webkit-text-fill-color: transparent; }
.ps-header p  { margin: 4px 0 0; font-size: 0.85rem; color: #64748b; }

/* \u2500\u2500 chat bubbles \u2500\u2500 */
.chat-user {
    background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(59,130,246,0.10));
    border: 1px solid rgba(139,92,246,0.3);
    border-radius: 16px 16px 4px 16px;
    padding: 14px 18px; margin: 10px 0; color: #1e1b4b;
    margin-left: 20%;
}
.chat-agent {
    background: rgba(255, 255, 255, 0.85);
    border: 1px solid rgba(139,92,246,0.15);
    border-radius: 16px 16px 16px 4px;
    padding: 14px 18px; margin: 10px 0; color: #1e293b;
    margin-right: 20%;
    box-shadow: 0 2px 8px rgba(139,92,246,0.06);
}
.chat-label { font-size: 0.72rem; font-weight: 600; letter-spacing: .06em;
    margin-bottom: 6px; text-transform: uppercase; }
.chat-label.user  { color: #7c3aed; }
.chat-label.agent { color: #2563eb; }

/* \u2500\u2500 tool trace card \u2500\u2500 */
.tool-card {
    background: rgba(241, 245, 255, 0.9);
    border: 1px solid rgba(139,92,246,0.2);
    border-left: 3px solid #7c3aed;
    border-radius: 10px;
    padding: 12px 16px;
    margin: 8px 0;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.8rem;
    color: #475569;
}
.tool-name { color: #7c3aed; font-weight: 600; font-size: 0.85rem; }
.tool-icon { font-size: 1.1rem; margin-right: 6px; }

/* \u2500\u2500 citation block \u2500\u2500 */
.citation-block {
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 12px;
    padding: 16px 20px;
    margin: 10px 0;
    box-shadow: 0 2px 8px rgba(59,130,246,0.06);
}
.citation-title { font-weight: 600; color: #2563eb; font-size: 1rem; margin-bottom: 6px; }
.citation-meta  { color: #475569; font-size: 0.82rem; line-height: 1.6; }
.citation-count { display: inline-block; background: rgba(139,92,246,0.1);
    border: 1px solid rgba(139,92,246,0.3); border-radius: 20px;
    padding: 2px 10px; font-size: 0.75rem; color: #7c3aed; margin-top: 6px; }

/* \u2500\u2500 sidebar widgets \u2500\u2500 */
.sidebar-section { color: #94a3b8; font-size: 0.72rem; font-weight: 600;
    text-transform: uppercase; letter-spacing: .08em; margin: 16px 0 6px; }

/* \u2500\u2500 quick prompts \u2500\u2500 */
.quick-btn { cursor: pointer; }

/* \u2500\u2500 input area placeholder ro rang \u2500\u2500 */
[data-testid="stChatInput"] textarea {
    background: rgba(255,255,255,0.95) !important;
    border: 1.5px solid rgba(139,92,246,0.35) !important;
    border-radius: 12px !important;
    color: #1e293b !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #64748b !important;
    opacity: 1 !important;
}
[data-testid="stChatInput"] textarea:focus {
    border-color: rgba(124,58,237,0.6) !important;
    box-shadow: 0 0 0 3px rgba(124,58,237,0.12) !important;
}

/* \u2500\u2500 metric pills \u2500\u2500 */
.metric-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(139,92,246,0.08); border: 1px solid rgba(139,92,246,0.2);
    border-radius: 20px; padding: 4px 12px; font-size: 0.78rem; color: #7c3aed;
    margin: 3px;
}

/* scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(139,92,246,0.25); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ── helpers ──────────────────────────────────────────────────────────────────

@st.cache_resource
def load_tools() -> list[dict[str, Any]]:
    return to_openai_tools(load_tool_declarations(TOOLS_YAML_PATH))


@st.cache_resource
def load_system_prompt() -> str:
    return SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


def get_provider(name: str):
    try:
        return make_provider(name)
    except Exception as exc:
        st.error(f"❌ Không khởi tạo được provider **{name}**: {exc}")
        st.stop()


def render_tool_trace(events: list[dict[str, Any]]) -> None:
    """Render collapsible tool trace."""
    if not events:
        return
    with st.expander(f"🔧 Tool calls ({len(events)})", expanded=False):
        for ev in events:
            tool = ev.get("tool", "?")
            args = ev.get("args", {})
            result = ev.get("result", {})
            icon = TOOL_ICONS.get(tool, "🔧")

            st.markdown(
                f'<div class="tool-card">'
                f'<span class="tool-icon">{icon}</span>'
                f'<span class="tool-name">{tool}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            col_a, col_b = st.columns(2)
            with col_a:
                st.caption("**Args**")
                st.json(args, expanded=False)
            with col_b:
                st.caption("**Result**")
                # Special rendering for citation_lookup
                if tool == "citation_lookup" and isinstance(result, dict) and "title" in result:
                    render_citation_card(result)
                elif isinstance(result, dict) and "items" in result:
                    st.caption(f"{len(result['items'])} item(s) returned")
                    st.json(result, expanded=False)
                else:
                    st.json(result, expanded=False)


def render_citation_card(result: dict[str, Any]) -> None:
    """Pretty citation card for citation_lookup results."""
    title = result.get("title", "")
    authors = result.get("authors", [])
    venue = result.get("venue", "")
    year = result.get("year", "")
    doi = result.get("doi", "")
    cites = result.get("citation_count")
    bibtex = result.get("bibtex", "")

    author_str = ", ".join(authors[:4]) + (" et al." if len(authors) > 4 else "")
    meta_parts = []
    if venue:
        meta_parts.append(f"📍 {venue}")
    if year:
        meta_parts.append(f"📅 {year}")
    if doi:
        meta_parts.append(f'<a href="https://doi.org/{doi}" target="_blank" style="color:#60a5fa;">🔗 DOI</a>')

    st.markdown(
        f'<div class="citation-block">'
        f'<div class="citation-title">{title}</div>'
        f'<div class="citation-meta">{author_str}<br>{"  ·  ".join(meta_parts)}</div>'
        f'{"<span class=citation-count>🔖 " + str(cites) + " citations</span>" if cites else ""}'
        f'</div>',
        unsafe_allow_html=True,
    )
    if bibtex:
        with st.expander("BibTeX"):
            st.code(bibtex, language="bibtex")


def render_papers_cards(items: list[dict]) -> None:
    """Render paper search results as cards."""
    for p in items[:5]:
        arxiv_id = p.get("arxiv_id", "")
        title = p.get("title", "")
        authors = p.get("authors", [])
        summary = p.get("summary", "")[:280] + "…"
        year = (p.get("published") or "")[:4]
        url = p.get("url", "")
        pdf_url = p.get("pdf_url", "")

        author_str = ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
        links = []
        if url:
            links.append(f'<a href="{url}" target="_blank" style="color:#60a5fa;">arXiv</a>')
        if pdf_url:
            links.append(f'<a href="{pdf_url}" target="_blank" style="color:#a78bfa;">PDF</a>')

        st.markdown(
            f'<div class="citation-block">'
            f'<div class="citation-title">{title}</div>'
            f'<div class="citation-meta">'
            f'{author_str} · {year}<br>'
            f'<span style="color:#64748b;font-size:.78rem;">{summary}</span><br>'
            f'{"  ·  ".join(links)}'
            f'</div></div>',
            unsafe_allow_html=True,
        )


# ── session state ────────────────────────────────────────────────────────────
def init_state() -> None:
    defaults: dict[str, Any] = {
        "messages": [],      # list of {role, content, tool_events?}
        "history":  [],      # plain {role,content} for LLM context
        "provider_name": "openai",
        "model":    "gpt-4o",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()

# ── sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<p style="font-size:1.3rem;font-weight:700;color:#a78bfa;margin:0;">⚙️ Cấu hình</p>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-section">Provider & Model</div>', unsafe_allow_html=True)
    provider_name = st.selectbox("Provider", PROVIDERS,
                                  index=PROVIDERS.index(st.session_state.provider_name),
                                  key="provider_select")
    model_options = PROVIDER_MODELS.get(provider_name, ["default"])
    model = st.selectbox("Model", model_options, key="model_select")

    if provider_name != st.session_state.provider_name or model != st.session_state.model:
        st.session_state.provider_name = provider_name
        st.session_state.model = model

    st.markdown('<div class="sidebar-section">Quick prompts</div>', unsafe_allow_html=True)
    QUICK_PROMPTS = [
        ("🔍 Tìm bài về LLM reasoning",      "Tìm cho mình các bài báo mới nhất về LLM reasoning trên ArXiv"),
        ("📚 Citation bài 2005.14165",         "Cho mình xem thông tin trích dẫn của bài báo 2005.14165"),
        ("📄 Đọc bài 2301.00001",              "Tải và đọc nội dung bài báo https://arxiv.org/abs/2301.00001"),
        ("📋 Policy trích dẫn nội bộ",         "Công ty có quy định gì về trích dẫn nguồn khi xuất bản bài báo không?"),
        ("🤖 Tìm bài về AI Agent Evaluation", "Tìm paper mới về AI agent evaluation trên ArXiv"),
    ]
    for label, prompt in QUICK_PROMPTS:
        if st.button(label, use_container_width=True, key=f"qp_{label}"):
            st.session_state["_quick_prompt"] = prompt

    st.markdown('<div class="sidebar-section">Lịch sử</div>', unsafe_allow_html=True)
    turn_count = sum(1 for m in st.session_state.messages if m["role"] == "user")
    tool_count  = sum(len(m.get("tool_events", [])) for m in st.session_state.messages)
    st.markdown(
        f'<div class="metric-pill">💬 {turn_count} turns</div>'
        f'<div class="metric-pill">🔧 {tool_count} tool calls</div>',
        unsafe_allow_html=True,
    )
    if st.button("🗑️ Xóa lịch sử", use_container_width=True):
        st.session_state.messages = []
        st.session_state.history  = []
        st.rerun()

    st.markdown("---")
    st.caption("Paper Scout · Powered by OpenAlex + arXiv")

# ── main area ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="ps-header">
  <div style="font-size:2.5rem">🔬</div>
  <div>
    <h1>Paper Scout</h1>
    <p>Trợ lý nghiên cứu — Tìm, đọc và trích dẫn bài báo khoa học trên arXiv</p>
  </div>
</div>
""", unsafe_allow_html=True)

# ── render existing messages ─────────────────────────────────────────────────
for msg in st.session_state.messages:
    role = msg["role"]
    content = msg["content"]
    tool_events = msg.get("tool_events", [])

    if role == "user":
        st.markdown(
            f'<div class="chat-user">'
            f'<div class="chat-label user">Bạn</div>'
            f'{content}</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="chat-agent">'
            f'<div class="chat-label agent">🔬 Paper Scout</div>'
            f'{content}</div>',
            unsafe_allow_html=True,
        )
        # Rich rendering for paper results
        for ev in tool_events:
            tool = ev.get("tool", "")
            result = ev.get("result", {})
            if tool == "papers" and isinstance(result, dict) and result.get("items"):
                with st.expander(f"📚 {len(result['items'])} bài báo tìm được", expanded=True):
                    render_papers_cards(result["items"])
            elif tool == "citation_lookup" and isinstance(result, dict) and "title" in result:
                with st.expander("📖 Thông tin trích dẫn", expanded=True):
                    render_citation_card(result)
        # Tool trace
        if tool_events:
            render_tool_trace(tool_events)

# ── handle quick prompt ──────────────────────────────────────────────────────
if "_quick_prompt" in st.session_state:
    prompt = st.session_state.pop("_quick_prompt")
    st.session_state["_pending_input"] = prompt

# ── chat input ───────────────────────────────────────────────────────────────
user_input = st.chat_input("Hỏi Paper Scout... (VD: Tìm bài về RAG, citation 2005.14165)")

# Accept from quick prompt or typed input
if "_pending_input" in st.session_state:
    user_input = st.session_state.pop("_pending_input")

if user_input:
    # Store user message
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.session_state.history.append({"role": "user", "content": user_input})

    # Show user bubble immediately
    st.markdown(
        f'<div class="chat-user">'
        f'<div class="chat-label user">Bạn</div>'
        f'{user_input}</div>',
        unsafe_allow_html=True,
    )

    # ── call agent ──
    system_prompt = load_system_prompt()
    tools = load_tools()
    provider = get_provider(st.session_state.provider_name)

    messages_ctx = [
        {"role": "system", "content": system_prompt},
        *trim_history(st.session_state.history[:-1], window=5),
        {"role": "user", "content": user_input},
    ]

    with st.spinner("🔬 Paper Scout đang tra cứu…"):
        try:
            result = run_model_tool_loop(
                provider=provider,
                messages=messages_ctx,
                tools=tools,
                model=st.session_state.model,
                max_tool_rounds=4,
            )
            assistant_text = result.get("assistant_text") or ""
            tool_events    = result.get("tool_events", [])
        except Exception as exc:
            assistant_text = f"⚠️ Lỗi: {exc}"
            tool_events    = []

    # Store assistant message
    st.session_state.messages.append({
        "role": "assistant",
        "content": assistant_text,
        "tool_events": tool_events,
    })
    st.session_state.history.append({"role": "assistant", "content": assistant_text})

    # Render agent reply
    st.markdown(
        f'<div class="chat-agent">'
        f'<div class="chat-label agent">🔬 Paper Scout</div>'
        f'{assistant_text}</div>',
        unsafe_allow_html=True,
    )

    # Rich results
    for ev in tool_events:
        tool_name = ev.get("tool", "")
        res = ev.get("result", {})
        if tool_name == "papers" and isinstance(res, dict) and res.get("items"):
            with st.expander(f"📚 {len(res['items'])} bài báo tìm được", expanded=True):
                render_papers_cards(res["items"])
        elif tool_name == "citation_lookup" and isinstance(res, dict) and "title" in res:
            with st.expander("📖 Thông tin trích dẫn", expanded=True):
                render_citation_card(res)

    if tool_events:
        render_tool_trace(tool_events)

    st.rerun()
