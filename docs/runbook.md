# Klara — Runbook

## Quickstart

### 1. Get the project

```bash
git clone <your-repo-url>
cd personal-ops-agent
```

Or just copy the folder if you're working locally.

### 2. Create a virtual environment

```bash
python -m venv .venv
```

### 3. Activate it

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Configure your environment

```bash
cp .env.example .env
```

Open `.env` and add your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 6. Run Klara

```bash
python main.py
```

### 7. Talk to Klara

Klara will greet you and wait for input. Type your message and press Enter. Type `quit` or `exit` to end the session.

---

## Troubleshooting

**`ANTHROPIC_API_KEY not found`** — Make sure `.env` exists and contains your key. It should NOT be in quotes.

**`ModuleNotFoundError`** — Make sure your virtual environment is activated (`pip list` should show `anthropic`).

**Import errors on Google modules** — These are expected until Google OAuth is set up in a future work package.
