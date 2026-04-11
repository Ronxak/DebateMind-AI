"""Judge agent for final evaluation."""

try:
    from debatemind.core.llm import generate
    from debatemind.utils.prompts import build_judge_prompt
except ModuleNotFoundError:
    from core.llm import generate
    from utils.prompts import build_judge_prompt


def generate_judgment(topic: str, debate_history: str) -> str:
    prompt = build_judge_prompt(topic=topic, debate_history=debate_history)
    return generate(prompt)
