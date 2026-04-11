"""Anti debate agent."""

try:
    from debatemind.core.llm import generate
    from debatemind.utils.prompts import build_anti_prompt
except ModuleNotFoundError:
    from core.llm import generate
    from utils.prompts import build_anti_prompt


def generate_anti_argument(topic: str, context: str, round_number: int) -> str:
    prompt = build_anti_prompt(topic=topic, context=context, round_number=round_number)
    output = generate(prompt)
    required_prefix = f"Round {round_number} | Anti Agent:"
    if not output.startswith(required_prefix):
        return f"{required_prefix}\n{output}"
    return output
