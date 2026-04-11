"""Debate orchestration engine."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

try:
    from debatemind.agents.anti_agent import generate_anti_argument
    from debatemind.agents.judge_agent import generate_judgment
    from debatemind.agents.pro_agent import generate_pro_argument
except ModuleNotFoundError:
    from agents.anti_agent import generate_anti_argument
    from agents.judge_agent import generate_judgment
    from agents.pro_agent import generate_pro_argument


def _format_history(entries: List[Dict[str, str]]) -> str:
    if not entries:
        return "No history yet."
    return "\n\n".join(
        f"Round {entry['round']} | {entry['agent']}:\n{entry['argument']}" for entry in entries
    )


def run_debate(
    topic: str, rounds: int = 2, progress_callback: Optional[Callable[[str], None]] = None
) -> Dict[str, object]:
    """Run a structured multi-round debate and return all outputs."""
    clean_topic = (topic or "").strip()
    if not clean_topic:
        raise ValueError("Topic cannot be empty.")

    rounds = max(1, min(int(rounds), 3))
    history: List[Dict[str, str]] = []

    for round_number in range(1, rounds + 1):
        if progress_callback:
            progress_callback(f"Round {round_number}: Pro Agent is preparing arguments...")
        pro_context = (
            _format_history(history)
            + "\n\nInstruction: Respond directly to the latest Anti argument where relevant."
        )
        pro_argument = generate_pro_argument(
            topic=clean_topic,
            context=pro_context,
            round_number=round_number,
        )
        history.append(
            {
                "round": str(round_number),
                "agent": "Pro Agent",
                "argument": pro_argument,
            }
        )

        anti_context = (
            _format_history(history)
            + "\n\nInstruction: Respond directly to the latest Pro argument where relevant."
        )
        if progress_callback:
            progress_callback(f"Round {round_number}: Anti Agent is analyzing Pro points...")
        anti_argument = generate_anti_argument(
            topic=clean_topic,
            context=anti_context,
            round_number=round_number,
        )
        history.append(
            {
                "round": str(round_number),
                "agent": "Anti Agent",
                "argument": anti_argument,
            }
        )

    if progress_callback:
        progress_callback("Judge Agent is reviewing all rounds and preparing a balanced verdict...")
    full_history = _format_history(history)
    judgment = generate_judgment(topic=clean_topic, debate_history=full_history)

    return {
        "topic": clean_topic,
        "rounds": rounds,
        "history": history,
        "judgment": judgment,
    }
