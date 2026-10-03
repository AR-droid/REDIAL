PY ?= python3
PORT ?= 8000
PYTHON := .venv/bin/python

setup:
	$(PY) -m venv .venv
	.venv/bin/pip install -r requirements.txt

# Backend: tool webhooks (/tools) and the phone-call bridge (/voice/*). Expose with ngrok for calls.
mock-server:
	.venv/bin/uvicorn backend.app:app --port $(PORT)

test:
	.venv/bin/pytest

# Dry run by default. Set CONFIRM=1 to place a real call to the approved number.
call:
	@test -n "$(SCENARIO)" || (echo "usage: make call SCENARIO=<1-10> [CONFIRM=1]"; exit 1)
	$(PYTHON) scripts/place_voice_call.py $(SCENARIO) $(if $(CONFIRM),--confirm,)

# Offline run of every scenario against the agent prompt (OpenAI API, no phone). Needs OPENAI_API_KEY.
simulate:
	PYTHONPATH=. $(PYTHON) scripts/simulate.py

.PHONY: setup mock-server test call simulate
