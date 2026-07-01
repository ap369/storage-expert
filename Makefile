.PHONY: install serve ingest ask chat docker-build docker-up docker-down clean reset reingest

VENV = .venv
BIN  = $(VENV)/bin

install:
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip --quiet
	$(BIN)/pip install -e . --quiet
	@echo "Done. Activate with: source $(VENV)/bin/activate"

serve:
	-pkill -f "uvicorn web.server" 2>/dev/null; sleep 0.5
	$(BIN)/uvicorn web.server:app --host 0.0.0.0 --port 8000 --reload --log-level debug

ingest:
	$(BIN)/storage-expert ingest $(ARGS)

ask:
	$(BIN)/storage-expert ask $(ARGS)

chat:
	$(BIN)/storage-expert chat $(ARGS)

docker-build:
	docker build -t storage-expert .

docker-up:
	docker compose up -d

docker-down:
	docker compose down

reset:
	rm -rf chroma_db/
	@echo "ChromaDB wiped. Run 'make reingest' to rebuild from vendor_pdfs/."

reingest:
	$(BIN)/storage-expert ingest --folder vendor_pdfs/

clean:
	rm -rf $(VENV) __pycache__ storage_expert/__pycache__ web/__pycache__ *.egg-info
