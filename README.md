# Support Message Triage API

A small FastAPI service that classifies customer support messages using LLMs hosted on Groq. It takes a list of messages, sends them through a shared async queue, and returns a structured triage result for each one.

Built as a take-home assignment for an internship.

## What it does

- Accepts one or many support messages over a REST API.
- Uses an LLM with structured output (Pydantic schema) so every result has the same shape.
- Spreads the load across **two Groq API keys** to get more throughput and stay under rate limits.
- Falls back to a second model automatically if the primary model fails.
- Retries failed requests and records every failure so you can see what went wrong.

## How it works

<p align="center">
  <img src="workflow-img.png" alt="Triage Queue Architecture" height="900">
</p>


1. The API validates the messages and puts them on one shared queue.
2. Each worker slot owns one API key, a primary model, and a fallback model.
3. A worker pulls a message, calls its primary model, and uses LangChain's `with_fallbacks` to switch to the fallback model if that call fails.
4. If both models fail, the message goes back on the queue and may be picked up again (up to `max_attempts`).
5. After a cooldown, the worker's concurrency slot is released. This keeps each key under its rate limit.
6. Results come back in the same order as the input.

## Project structure

```
Project/
├──client/           # Streamlit app 
├──evals/            # Evaluation assets and pipeline
src/
├── api/             # API routes / app entry point
├── config.py        # Settings loaded from environment variables
├── prompt.py        # The triage prompt template
├── schema.py        # Pydantic models (TriageResult, TriageRequest)
├── triage_queue.py  # Queue, workers, fallback and failure tracking
└── main.py          # Main File Starting
```

<!-- TODO: adjust the tree above to match your actual folders -->

## Setup

### Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/)
- Two Groq API keys *(one key is enough to try the application; the second is used by the second worker for parallel processing/fallback)*

```bash
# 1. Clone the repository
git clone https://github.com/anishpandey7659/Take-Home-Project-AI-Support-Ticket-Triage.git

# 2. Enter the project
cd Take-Home-Project-AI-Support-Ticket-Triage

# 3. Create the virtual environment and install dependencies
uv sync

# 4. Activate the virtual environment
source .venv/bin/activate
```

### Configuration

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_first_key
GROQ_API_KEY2=your_second_key

GROQ_MODEL=<primary model for worker-1>
GROQ_MODEL2=<primary model for worker-2>
FALLBACK_MODEL1=<fallback model for worker-1>
FALLBACK_MODEL2=<fallback model for worker-2>

DEFAULT_TEMPERATURE=0
MAX_CONCURRENCY=2
COOLDOWN=1.0
MAX_ATTEMPTS=3
```

<!-- TODO: make sure these names match the fields in src/config.py -->

| Setting | Meaning |
|---|---|
| `GROQ_API_KEY`, `GROQ_API_KEY2` | One API key per worker |
| `GROQ_MODEL`, `GROQ_MODEL2` | Primary model used by each worker |
| `FALLBACK_MODEL1`, `FALLBACK_MODEL2` | Model used if the primary fails |
| `DEFAULT_TEMPERATURE` | LLM temperature (low = more consistent labels) |
| `MAX_CONCURRENCY` | Parallel calls allowed per worker |
| `COOLDOWN` | Seconds before a worker slot is freed after a call |
| `MAX_ATTEMPTS` | How many times a message is tried before it fails |

## Running

**Start the API:**

```bash
uvicorn src.main:app --reload
```

<!-- TODO: replace src.main:app with your actual app path -->

Interactive docs are available at `http://localhost:8000/docs`.

**Quick test without the API** (runs the queue directly on a few sample messages):

```bash
python -m src.triage_queue
```

## API

### `POST /triage_all`

Classifies a list of support messages. Results are returned in the same order as the input.

**Request**

```json
[
  { "message": "I was charged twice for my subscription this month." },
  { "message": "The app crashes every time I try to upload a photo." }
]
```

**Response** `200 OK`

A list of `TriageResult` objects, one per message (see `src/schema.py` for the exact fields).

**Errors**

| Status | When |
|---|---|
| `422` | A message is blank |
| `502` | The LLM failed on a message after all retries |



## Prompt Engineering & Evaluation

- **Requirement Analysis:** Read the problem requirements and converted them into a clear rubric covering **urgency, category, sentiment, and suggested reply**.

- **Initial Prompt:** Created the first prompt using the rubric, with explicit definitions and rules for each label.

- **Golden Dataset:** Reviewed all **20 provided support messages** and, with the help of AI, created a **golden dataset** containing the expected labels for each message.

- **Evaluation Pipeline:** Built an evaluation pipeline using the golden dataset to measure prompt performance with **precision, recall, and confusion matrices**.

- **Error Analysis:** Identified common classification issues, particularly confusion between **High vs. Critical** urgency and **Angry vs. Frustrated** sentiment.

- **Prompt Iteration:** Refined ambiguous definitions and added clearer decision rules based on the evaluation results.

- **Continuous Evaluation:** Re-ran the evaluation after each prompt change, analyzed the results, and repeated the process to improve **classification accuracy and consistency**.

## Tech stack

Python · FastAPI · LangChain · Groq · Pydantic · asyncio