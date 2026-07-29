import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version
from chat import run_model_tool_loop, write_transcript, now_iso, safe_slug, trim_history

# Page configuration
st.set_page_config(
    page_title="AI Research Chatbot",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
load_lab_env(ROOT)

# Clean Modern Chat CSS (ChatGPT/Claude Style)
st.markdown("""
<style>
    .stApp {
        background-color: #0f172a;
        color: #f8fafc;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Header */
    .chat-header {
        text-align: center;
        padding-top: 10px;
        padding-bottom: 20px;
        border-bottom: 1px solid #1e293b;
        margin-bottom: 20px;
    }
    .chat-title {
        font-size: 1.6rem;
        font-weight: 700;
        color: #ffffff;
    }
    .chat-subtitle {
        font-size: 0.9rem;
        color: #94a3b8;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #1e293b !important;
        border-right: 1px solid #334155 !important;
    }

    /* Tool Trace Styling (Compact & Secondary) */
    .stExpander {
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        background-color: #1e293b !important;
        margin-top: 10px !important;
        margin-bottom: 10px !important;
    }
    
    .stButton button {
        background-color: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 6px !important;
        font-size: 0.82rem !important;
        padding: 4px 10px !important;
    }
    .stButton button:hover {
        background-color: #334155 !important;
        color: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
<div class="chat-header">
    <div class="chat-title">💬 AI Research Chatbot</div>
    <div class="chat-subtitle">Hỏi đáp & Tìm kiếm nghiên cứu khoa học trực tiếp</div>
</div>
""", unsafe_allow_html=True)

# Sidebar Configuration
with st.sidebar:
    st.markdown("### ⚙️ Cấu hình")
    
    provider_name = st.selectbox(
        "Nhà cung cấp Model",
        options=["openrouter", "openai", "anthropic", "gemini"],
        index=1,
    )
    
    model_name = st.text_input(
        "Tên Model",
        value="gpt-4o" if provider_name == "openai" else "openai/gpt-4o-mini",
    )
    
    version_label = st.selectbox(
        "Phiên bản Artifact",
        options=["v0", "v1", "v2", "v3"],
        index=3,
    )

    system_prompt_file = ARTIFACTS_DIR / "system_prompt.md"
    tools_file = ARTIFACTS_DIR / "tools.yaml"

    history_window = st.slider("Số lượt nhớ hội thoại", min_value=1, max_value=10, value=5)
    max_tool_rounds = st.slider("Giới hạn số vòng gọi Tool", min_value=1, max_value=8, value=4)

    # Version Info
    try:
        artifact_ver = build_artifact_version(version_label, system_prompt_file, tools_file)
        st.caption(f"Artifact Version: `{artifact_ver.artifact_version}`")
        st.caption(f"Prompt Hash: `{artifact_ver.prompt_hash[:10]}` | Tools Hash: `{artifact_ver.tools_hash[:10]}`")
    except Exception as e:
        st.error(f"Lỗi Version: {e}")

    if st.button("🔄 Tải lại / Xóa lịch sử"):
        st.session_state.messages = []
        st.session_state.transcript = None
        st.rerun()

# Initialize Session State for Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

if "transcript" not in st.session_state:
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    transcript_id = f"{safe_slug(version_label)}_{safe_slug(provider_name)}_{timestamp}"
    st.session_state.transcript = {
        "transcript_id": transcript_id,
        "created_at": now_iso(),
        "turns": [],
    }

# Quick Prompt Suggestions (Displayed as text buttons)
if not st.session_state.messages:
    st.markdown("<p style='color: #94a3b8; font-size: 0.9rem;'>💡 Câu hỏi gợi ý:</p>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    sample_prompt = None
    if c1.button("Tìm 5 bài báo mới nhất về LLM reasoning"):
        sample_prompt = "Tìm cho mình 5 bài báo khoa học mới nhất về LLM reasoning trên ArXiv"
    if c2.button("Cho xem trích dẫn bài báo 2301.00001"):
        sample_prompt = "Cho mình xem danh sách trích dẫn (citations) của bài báo 2301.00001"
    if c3.button("Quy định trích dẫn bài báo nội bộ"):
        sample_prompt = "Công ty mình có quy định gì về việc trích dẫn nguồn tài liệu tham khảo khi xuất bản bài báo không?"
else:
    sample_prompt = None

# Render Chat History
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Tool execution details collapsed by default so JSON doesn't clutter chat
        if "rounds" in msg and msg["rounds"]:
            tool_calls_count = sum(len(r.get("tool_calls", [])) for r in msg["rounds"])
            if tool_calls_count > 0:
                with st.expander(f"🔍 Chi tiết {tool_calls_count} bước xử lý ngầm (Tool Trace)", expanded=False):
                    for r in msg["rounds"]:
                        for call in r.get("tool_calls", []):
                            st.write(f"- Gọi tool: `{call.get('name')}` với tham số `{call.get('args')}`")
                        for res in r.get("tool_results", []):
                            st.caption(f"Trả về từ {res.get('tool')}:")
                            st.json(res.get("result", {}))

# Chat Input Box
user_input = st.chat_input("Nhập tin nhắn để nhắn tin với Assistant...") or sample_prompt

if user_input:
    # Append user input
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Process Assistant Response
    with st.chat_message("assistant"):
        with st.spinner("Assistant đang trả lời..."):
            try:
                system_prompt_text = system_prompt_file.read_text(encoding="utf-8")
                tool_decls = load_tool_declarations(tools_file)
                openai_tools = to_openai_tools(tool_decls)
                provider = make_provider(provider_name)
                
                # Build conversation context history for multi-turn
                history_pairs = [
                    {"role": m["role"], "content": m["content"]}
                    for m in st.session_state.messages[:-1]
                ]
                messages_context = [
                    {"role": "system", "content": system_prompt_text},
                    *trim_history(history_pairs, history_window),
                    {"role": "user", "content": user_input},
                ]

                # Run loop
                result = run_model_tool_loop(
                    provider=provider,
                    messages=messages_context,
                    tools=openai_tools,
                    model=model_name or None,
                    max_tool_rounds=max_tool_rounds,
                )

                assistant_response = result.get("assistant_text", "")
                
                # Render clean assistant response text
                st.markdown(assistant_response)

                rounds = result.get("rounds", [])
                tool_calls_count = sum(len(r.get("tool_calls", [])) for r in rounds)
                if tool_calls_count > 0:
                    with st.expander(f"🔍 Chi tiết {tool_calls_count} bước xử lý ngầm (Tool Trace)", expanded=False):
                        for r in rounds:
                            for call in r.get("tool_calls", []):
                                st.write(f"- Gọi tool: `{call.get('name')}` với tham số `{call.get('args')}`")
                            for res in r.get("tool_results", []):
                                st.caption(f"Trả về từ {res.get('tool')}:")
                                st.json(res.get("result", {}))

                # Save assistant message to session
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": assistant_response,
                    "rounds": rounds,
                    "tool_events": result.get("tool_events", []),
                })

                # Write transcript
                artifact_ver = build_artifact_version(version_label, system_prompt_file, tools_file)
                transcript_path = TRANSCRIPTS_DIR / f"{st.session_state.transcript['transcript_id']}.transcript.json"
                
                turn_record = {
                    "turn_index": len(st.session_state.messages) // 2,
                    "user": user_input,
                    "assistant_text": assistant_response,
                    "rounds": rounds,
                    "tool_events": result.get("tool_events", []),
                    "timestamp": now_iso(),
                }
                
                full_transcript = {
                    "transcript_id": st.session_state.transcript['transcript_id'],
                    **artifact_version_dict(artifact_ver),
                    "provider": provider_name,
                    "model": model_name,
                    "turns": st.session_state.transcript.get("turns", []) + [turn_record],
                    "updated_at": now_iso(),
                }
                st.session_state.transcript = full_transcript
                write_transcript(transcript_path, full_transcript)

            except Exception as exc:
                err_msg = f"Lỗi: {exc}"
                st.error(err_msg)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": err_msg,
                })
