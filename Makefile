.PHONY: install serve ingest ask chat docker-build docker-up docker-down clean

VENV = .venv
BIN  = $(VENV)/bin

install:
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip --quiet
	$(BIN)/pip install -e . --quiet
	@echo "Done. Activate with: source $(VENV)/bin/activate"

serve:
	$(BIN)/uvicorn web.server:app --host 0.0.0.0 --port 8000 --reload

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

clean:
	rm -rf $(VENV) __pycache__ storage_expert/__pycache__ web/__pycache__ *.egg-info
