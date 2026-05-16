PYTHON ?= python
HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: api worker worker-once ui seed rag test clean

api:
	$(PYTHON) -m uvicorn app.api:app --reload --reload-dir app --host $(HOST) --port $(PORT)

worker:
	$(PYTHON) -m app.runner

worker-once:
	$(PYTHON) -m app.runner --once

ui:
	$(PYTHON) -m streamlit run ui/streamlit_app.py --server.headless true

seed:
	$(PYTHON) scripts/seed_logs.py
	$(PYTHON) scripts/seed_rag_examples.py
	$(PYTHON) scripts/seed_incidents.py

rag:
	$(PYTHON) -m app.rag.build_index

test:
	$(PYTHON) -m pytest -q

clean:
	$(PYTHON) -c "from pathlib import Path; [p.unlink() for p in [Path('dev.db')] if p.exists()]"
