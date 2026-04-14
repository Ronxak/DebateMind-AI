"""Streamlit app for DebateMind AI."""

from __future__ import annotations

from datetime import datetime
import re

import streamlit as st

# Must be the first Streamlit command (before any other st.* calls).
st.set_page_config(page_title="DebateMind AI", page_icon="🧠", layout="wide")

from dotenv import load_dotenv

try:
    from debatemind.core.debate_engine import run_debate
    from debatemind.core.llm import LLMError
except ModuleNotFoundError:
    from core.debate_engine import run_debate
    from core.llm import LLMError

load_dotenv()


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned[:40] or "debate_topic"


def _build_transcript(result: dict) -> str:
    lines = [
        "DebateMind AI - Debate Transcript",
        f"Topic: {result['topic']}",
        f"Rounds: {result['rounds']}",
        "-" * 40,
    ]

    for entry in result["history"]:
        lines.append(f"Round {entry['round']} | {entry['agent']}")
        lines.append(entry["argument"])
        lines.append("")

    lines.extend(
        [
            "-" * 40,
            "Final Judgment",
            result["judgment"],
            "",
            f"Generated at: {datetime.now().isoformat(timespec='seconds')}",
        ]
    )
    return "\n".join(lines)

def _split_sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return [chunk.strip(" -\n\t") for chunk in chunks if chunk.strip(" -\n\t")]


def _ensure_bullet_points(text: str, *, bullet_count: int = 4) -> list[str]:
    raw = (text or "").replace("\r\n", "\n").strip()
    bullet_matches = re.findall(r"(?m)^\s*[-*•]\s+(.+)$", raw)
    numbered_matches = re.findall(r"(?m)^\s*\d+[.)]\s+(.+)$", raw)
    points = [item.strip() for item in (bullet_matches or numbered_matches) if item.strip()]

    if not points:
        points = _split_sentences(raw)

    if not points:
        points = ["No clear point generated."]

    if len(points) < bullet_count:
        fallback_sentences = _split_sentences(" ".join(points))
        for sentence in fallback_sentences:
            if len(points) >= bullet_count:
                break
            if sentence not in points:
                points.append(sentence)

    while len(points) < bullet_count:
        points.append("Additional supporting point.")

    return points[:bullet_count]


def _clean_leading_markers(text: str) -> str:
    value = (text or "").strip()
    value = re.sub(r"^\s*(?:\*{1,2}|[-•]+)\s*", "", value)
    return value.strip()


def _extract_judgment_sections(judgment: str) -> dict[str, str]:
    text = (judgment or "").replace("\r\n", "\n")
    label = r"(?:\*{0,2}\s*)?(?:\d+[.)]\s*)?"
    sep = r"(?:\s*[:\-]\s*|\s*\n)"
    patterns = {
        "pro_summary": rf"(?ims)^\s*{label}pro\s+summary{sep}(.*?)(?=^\s*{label}anti\s+summary{sep}|\Z)",
        "anti_summary": rf"(?ims)^\s*{label}anti\s+summary{sep}(.*?)(?=^\s*{label}strongest\s+pro\s+point{sep}|\Z)",
        "strongest_pro": rf"(?ims)^\s*{label}strongest\s+pro\s+point{sep}(.*?)(?=^\s*{label}strongest\s+anti\s+point{sep}|\Z)",
        "strongest_anti": rf"(?ims)^\s*{label}strongest\s+anti\s+point{sep}(.*?)(?=^\s*{label}balanced\s+conclusion{sep}|\Z)",
        "balanced_conclusion": rf"(?ims)^\s*{label}balanced\s+conclusion{sep}(.*)$",
    }
    sections: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        sections[key] = (match.group(1).strip() if match else "")

    if not sections["pro_summary"] and not sections["anti_summary"]:
        sections["pro_summary"] = text
        sections["anti_summary"] = text

    # Fallback: if tail sections are unlabeled, infer from trailing paragraphs.
    tail_keys = ("strongest_pro", "strongest_anti", "balanced_conclusion")
    if not any(sections.get(key) for key in tail_keys):
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
        if len(paragraphs) >= 3:
            sections["strongest_pro"] = paragraphs[-3]
            sections["strongest_anti"] = paragraphs[-2]
            sections["balanced_conclusion"] = paragraphs[-1]

    return sections


def _render_final_judgment(judgment: str) -> None:
    sections = _extract_judgment_sections(judgment)
    pro_points = _ensure_bullet_points(sections.get("pro_summary", ""))
    anti_points = _ensure_bullet_points(sections.get("anti_summary", ""))

    st.subheader("Pro Summary")
    st.markdown("\n".join(f"* {point}" for point in pro_points))
    st.markdown("")

    st.subheader("Anti Summary")
    st.markdown("\n".join(f"* {point}" for point in anti_points))
    st.markdown("")

    st.subheader("Strongest Pro Point")
    st.markdown(_clean_leading_markers(sections.get("strongest_pro", "No strongest pro point generated.")))
    st.markdown("")

    st.subheader("Strongest Anti Point")
    st.markdown(_clean_leading_markers(sections.get("strongest_anti", "No strongest anti point generated.")))
    st.markdown("")

    st.subheader("Balanced Conclusion")
    st.markdown(_clean_leading_markers(sections.get("balanced_conclusion", "No balanced conclusion generated.")))

def clean_round_header(text: str) -> str:
    # Remove "Round X | Pro/Anti Agent:" from start
    return re.sub(r"^Round\s+\d+\s+\|\s+(Pro|Anti)\s+Agent:\s*", "", text, flags=re.IGNORECASE)

def _render_result(result: dict) -> None:
    history = result["history"]
    judgment = result["judgment"]

    st.subheader("Opening Viewpoints")
    pro_opening = next(
        (item for item in history if item["round"] == "1" and item["agent"] == "Pro Agent"),
        None,
    )
    anti_opening = next(
        (item for item in history if item["round"] == "1" and item["agent"] == "Anti Agent"),
        None,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            """
            <div style="background-color:#eaf8ef;border:1px solid #9ad0a2;padding:14px;border-radius:10px;color:#111111;">
                <h4 style="margin-top:0;color:#111111;">🟢 Pro Agent</h4>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div style="margin-top:10px;background-color:#ffffff;border-radius:10px;padding:14px 16px;color:#111111;">
                <p style="margin:0;white-space:pre-wrap;">
                {clean_round_header((pro_opening or {}).get("argument", "No argument generated.")).strip().replace("\n", "<br />")}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            """
            <div style="background-color:#fdeeee;border:1px solid #e6a8a8;padding:14px;border-radius:10px;color:#111111;">
                <h4 style="margin-top:0;color:#111111;">🔴 Anti Agent</h4>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            f"""
            <div style="margin-top:10px;background-color:#ffffff;border-radius:10px;padding:14px 16px;color:#111111;">
                <p style="margin:0;white-space:pre-wrap;">
                {clean_round_header((anti_opening or {}).get("argument", "No argument generated.")).strip().replace("\n", "<br />")}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("🔁 Debate Rounds")
    for round_number in range(1, int(result["rounds"]) + 1):
        with st.expander(f"Round {round_number}", expanded=(round_number == 1)):
            round_entries = [item for item in history if item["round"] == str(round_number)]
            for entry in round_entries:
                icon = "🟢" if entry["agent"] == "Pro Agent" else "🔴"
                st.markdown(f"**{icon} {entry['agent']}**")
                st.write(entry["argument"])
                st.markdown("")

    st.markdown("---")
    st.subheader("Final Judgment")
    st.markdown(
        """
        <div style="background-color:#f2f2f2;border:1px solid #d3d3d3;padding:16px;border-radius:10px;color:#111111;">
            <h4 style="margin:0;color:#111111;">Judge Agent</h4>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("")
    _render_final_judgment(judgment)

    st.markdown("")
    transcript = _build_transcript(result)
    filename = f"debate_transcript_{_safe_filename(result['topic'])}.txt"
    st.download_button(
        "Download Transcript",
        data=transcript,
        file_name=filename,
        mime="text/plain",
        use_container_width=True,
    )


st.markdown(
    """
    <style>
        .block-container {
            max-width: 980px;
            padding-top: 2rem;
            padding-bottom: 2.5rem;
        }
        [data-testid="stAppViewContainer"] {
            background: radial-gradient(circle at top, #1a1f2e 0%, #0f1117 55%);
        }
        [data-testid="stVerticalBlock"] > [style*="flex-direction: column;"] > [data-testid="stVerticalBlock"] {
            gap: 0.85rem;
        }
        .main-title {
            margin: 0;
            color: #ffffff;
            font-size: 2.35rem;
            font-weight: 700;
            text-align: center;
            letter-spacing: 0.2px;
        }
        .main-caption {
            text-align: center;
            color: #c8d1e6;
            margin-bottom: 1rem;
        }
        .panel {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 14px;
            padding: 14px 16px;
            backdrop-filter: blur(4px);
        }
        .stTextArea textarea {
            color: #111111 !important;
            background-color: #f8f9fb !important;
            border-radius: 10px !important;
        }
        .stTextArea label p {
            color: #111111 !important;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<h1 class="main-title">DebateMind AI</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="main-caption">Structured multi-agent debate with a final neutral judgment.</p>',
    unsafe_allow_html=True,
)
st.markdown("---")

if "debate_history" not in st.session_state:
    st.session_state.debate_history = []
if "latest_result" not in st.session_state:
    st.session_state.latest_result = None
if "result_run_id" not in st.session_state:
    st.session_state.result_run_id = 0
with st.form("debate_form", clear_on_submit=False):
    topic = st.text_input(
        "Enter a debate topic or question",
        placeholder="Example: Is AI dangerous?",
    )
    rounds = st.radio(
        "Debate rounds",
        options=[1, 2, 3],
        index=1,
        horizontal=True,
    )
    start = st.form_submit_button("Start Debate", type="primary")

if start:
    if not topic.strip():
        st.error("Please enter a topic before starting the debate.")
        st.stop()

    try:
        st.info(
            "Please wait — the first run can take several minutes while the model loads. "
            "Do not click again until this finishes."
        )
        # Do not call Streamlit APIs from inside run_debate (progress callbacks break SessionInfo).
        with st.spinner("Running debate (Pro → Anti each round, then Judge)..."):
            result = run_debate(topic=topic, rounds=rounds)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()
    except LLMError as exc:
        st.error(f"LLM error: {exc}")
        st.info("Tip: Add `GROQ_API_KEY` in your environment or .env file.")
        st.stop()
    except Exception as exc:  # pragma: no cover
        st.error(f"Unexpected error: {exc}")
        st.stop()

    st.session_state.result_run_id = int(st.session_state.result_run_id) + 1
    st.session_state.latest_result = result
    st.session_state.debate_history.insert(
        0,
        {
            "topic": result["topic"],
            "rounds": result["rounds"],
            "judgment": result["judgment"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )

if st.session_state.latest_result:
    _render_result(st.session_state.latest_result)

if st.session_state.debate_history:
    st.markdown("---")
    st.subheader("Session Debate History")
    for idx, item in enumerate(st.session_state.debate_history, start=1):
        with st.expander(f"{idx}. {item['topic']} ({item['timestamp']})", expanded=False):
            st.write(f"**Rounds:** {item['rounds']}")
            st.write("**Judgment Preview:**")
            st.write(item["judgment"][:500] + ("..." if len(item["judgment"]) > 500 else ""))
