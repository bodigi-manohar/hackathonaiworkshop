.PHONY: serve test replay

serve:
	$(PYTHON) -m uvicorn backend.main:app --reload --port 8000

test:
	$(PYTHON) -m pytest backend/tests -q

replay:
	$(PYTHON) -m backend.replay --start 2013-02-10 --days 7
