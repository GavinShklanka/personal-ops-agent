"""
Klara — Personal Ops Agent
A thoughtful AI assistant that helps manage schedule, goals, and opportunities.
"""

import os
import yaml
import anthropic
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Load settings
CONFIG_PATH = Path(__file__).parent.parent / "config" / "settings.yaml"


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def create_client():
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in .env file.")
        print("Copy .env.example to .env and add your key.")
        raise SystemExit(1)
    return anthropic.Anthropic(api_key=api_key)


def chat():
    """Main conversational loop with Klara."""
    config = load_config()
    client = create_client()
    klara_config = config["klara"]

    system_prompt = klara_config["system_prompt"]
    model = klara_config["model"]

    messages = []

    print()
    print("=" * 50)
    print("  Klara — Personal Ops Agent")
    print("  Type 'quit' or 'exit' to end the conversation")
    print("=" * 50)
    print()

    # Klara's greeting
    greeting_response = client.messages.create(
        model=model,
        max_tokens=300,
        system=system_prompt,
        messages=[{"role": "user", "content": "Say hello and briefly introduce yourself. Keep it warm and concise — 2-3 sentences max."}]
    )
    greeting = greeting_response.content[0].text
    print(f"Klara: {greeting}")
    print()

    # Don't add greeting to conversation history — start fresh

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nKlara: Take care, Gavin. I'll be here when you need me.")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "bye"):
            print("\nKlara: Take care, Gavin. I'll be here when you need me.")
            break

        messages.append({"role": "user", "content": user_input})

        try:
            response = client.messages.create(
                model=model,
                max_tokens=1024,
                system=system_prompt,
                messages=messages
            )

            assistant_message = response.content[0].text
            messages.append({"role": "assistant", "content": assistant_message})

            print(f"\nKlara: {assistant_message}\n")

        except anthropic.APIError as e:
            print(f"\n[Connection issue: {e}. Try again.]\n")
            messages.pop()  # Remove the failed user message


if __name__ == "__main__":
    chat()
