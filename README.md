# DebateMind AI - Multi-Agent Debate System

DebateMind AI is a Streamlit-based Python project that simulates a structured debate between multiple AI agents:

- 🟢 **Pro Agent** argues in support of the topic.
- 🔴 **Anti Agent** argues against the topic.
- 🧠 **Judge Agent** evaluates both sides and delivers a balanced conclusion.

The project uses the Groq API through a clean modular architecture.

## Project Structure

```text
debatemind/
├── app.py
├── agents/
│   ├── anti_agent.py
│   ├── judge_agent.py
│   └── pro_agent.py
├── core/
│   ├── debate_engine.py
│   └── llm.py
├── utils/
│   └── prompts.py
├── requirements.txt
└── README.md
```

## Requirements

- Python 3.9+
- Groq API key

Install Python packages:

```bash
pip install -r requirements.txt
```

## Groq Setup

1. Create a `.env` file in `debatemind/` (or copy `.env.example`):

```bash
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_FALLBACK_MODELS=llama-3.1-8b-instant
```
2. Or export these variables in your shell instead of using `.env`.

## Run The App

Ensure you are in the project root (`debatemind/`):

```bash
streamlit run app.py
```

## How It Works

1. User enters a debate topic (for example, `Is AI dangerous?`).
2. Debate engine runs for 2-3 rounds.
3. In each round:
   - Pro Agent makes/rebuts an argument.
   - Anti Agent responds/rebuts with context awareness.
4. Judge Agent receives full history and produces:
   - Pro summary
   - Anti summary
   - Strongest points from both sides
   - Balanced final conclusion

## Error Handling

The app handles:

- Empty topic input
- Groq connection/auth failures
- Timeout/invalid API responses
- Unexpected runtime errors without crashing the UI

## Notes

- The app is intentionally modular for easy extension (more agents, custom prompts, scoring logic, etc.).
- Debate rounds are constrained to 2-3 for stability and UI clarity.
