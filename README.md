# Aevom

**A cold-outreach engine for job applications.** Enrich a contact from their
LinkedIn URL, generate a tailored email with an LLM against a versioned system
prompt, send it through Gmail, and track follow-ups so nobody gets emailed twice.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-app-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![HuggingFace](https://img.shields.io/badge/HF-Inference%20API-FFD21E?style=flat-square&logo=huggingface&logoColor=black)](https://huggingface.co/docs/api-inference/index)
[![Gmail API](https://img.shields.io/badge/Gmail-OAuth2-EA4335?style=flat-square&logo=gmail&logoColor=white)](https://developers.google.com/gmail/api)

---

## Why

Generic cold emails do not get replies. Personalised ones do, but researching
each recipient by hand does not scale past about ten a week. Aevom automates the
research and drafting while keeping a human in the loop before anything sends.

## Features

| Feature | Description |
|---|---|
| **Contact enrichment** | Resolves a person and their company from a LinkedIn URL through a third-party API, with a disk-backed cache so the same profile is never paid for twice |
| **LLM generation** | Builds a structured context object and generates the email through the HuggingFace Inference API against a versioned system prompt in `prompts/` |
| **Robust output parsing** | Expects JSON; falls back to a regex extractor when the model wraps output in prose or fences, so a malformed response degrades instead of crashing |
| **Template selection** | Picks an email shape based on role type and how much context enrichment actually returned |
| **Gmail sending** | Sends as you, over OAuth2 - no SMTP passwords stored |
| **Follow-up tracking** | Per-contact state machine (`active` / `replied` / `closed`) with follow-up counts and next-touch dates, so a sequence never double-sends |
| **Review before send** | Every draft is editable in the UI; nothing leaves without a click |

## Architecture

```
                      ┌──────────────────┐
   LinkedIn URL ─────▶│   enrichment.py  │──▶ person + company profile
                      │  (cached on disk)│
                      └────────┬─────────┘
                               │
                               ▼
  prompts/cold_email_prompt.txt ──▶ ┌────────────────────┐
  user_profile/resume.txt ────────▶ │ email_generator.py │──▶ subject + body
  user_profile/additional_details ▶ │  HF Inference API  │    (JSON, with
                                    └─────────┬──────────┘     regex fallback)
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │  Streamlit UI    │  human edits + approves
                                    └────────┬─────────┘
                                             │
                          ┌──────────────────┴───────────────────┐
                          ▼                                      ▼
                 ┌─────────────────┐                  ┌────────────────────┐
                 │ gmail_sender.py │                  │ contact_tracker.py │
                 │  OAuth2 send    │                  │  status + next     │
                 └─────────────────┘                  │  follow-up date    │
                                                      └────────────────────┘
```

## Project Structure

```
app.py                        Streamlit UI and orchestration
modules/
├── enrichment.py             LinkedIn person/company lookup + disk cache
├── email_generator.py        prompt assembly, LLM call, JSON parsing + fallback
├── gmail_sender.py           Gmail API over OAuth2
├── contact_tracker.py        contact state, follow-up scheduling, dedupe
└── utils.py                  file IO, resume parsing, formatting helpers
prompts/
└── cold_email_prompt.txt     the system prompt (edit this to change voice)
tests/                        unit tests for tracker, enrichment and utils
user_profile/                 your resume and details (gitignored - see below)
```

## Setup

**Prerequisites:** Python 3.10+, a HuggingFace token, and a Google Cloud project
with the Gmail API enabled.

```bash
git clone https://github.com/dhruvg0ya1/Aevom.git
cd Aevom

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
streamlit run app.py
```

Then, in the app sidebar:

1. Paste your **HuggingFace token** and **enrichment API key** - they are stored
   locally in `settings.json`, which is gitignored and never committed
2. Upload your **resume** and an **additional details** file into `user_profile/`
3. Connect **Gmail** and complete the OAuth consent flow

## Configuration

| Setting | Where it lives | Purpose |
|---|---|---|
| `hf_token` | `settings.json` (local only) | HuggingFace Inference API |
| `rapidapi_key` | `settings.json` (local only) | LinkedIn enrichment |
| `gmail_creds` | `gmail_token.json` (local only) | Gmail OAuth2 |
| System prompt | `prompts/cold_email_prompt.txt` | Email voice, structure and rules |

## Tests

```bash
pip install pytest
pytest -q
```

Covers contact state transitions, the enrichment cache, and the utility layer.

## Privacy

This repository deliberately ships **no personal data**. `user_profile/`,
`contact_tracker.json`, `settings.json`, `gmail_token.json` and `email_history.json`
are all gitignored - they hold your resume, your API keys, and the contact
details of real people. Keep them local.

If you fork this, do not commit your tracker file. Other people's email
addresses are their data, not yours.

## License

MIT
