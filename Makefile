.PHONY: help install serve download-models ingest ask chat adduser docker-build docker-up docker-down clean reset reingest \
        deploy deploy-setup deploy-install-service deploy-install-nginx deploy-update \
        deploy-start deploy-stop deploy-restart deploy-status deploy-logs

VENV = .venv
BIN  = $(VENV)/bin

help:
	@echo ""
	@echo "Storage Expert — available commands"
	@echo ""
	@echo "Local development:"
	@echo "  make install                  Create venv and install dependencies"
	@echo "  make download-models          Download embedding model for offline use (~80MB)"
	@echo "  make serve                    Start web UI at http://localhost:8000"
	@echo "  make ingest ARGS='--file f'   Ingest a PDF (--file or --folder)"
	@echo "  make ask    ARGS='question'   Ask a single question"
	@echo "  make chat                     Interactive CLI chat"
	@echo ""
	@echo "User management:"
	@echo "  make adduser ARGS='username'  Create a web UI user (prompts for password)"
	@echo ""
	@echo "Knowledge base:"
	@echo "  make reset                    Wipe ChromaDB (clean slate)"
	@echo "  make reingest                 Re-ingest all PDFs under vendor_pdfs/"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build             Build the Docker image"
	@echo "  make docker-up                Start with docker compose"
	@echo "  make docker-down              Stop docker compose"
	@echo ""
	@echo "VM deployment (run as root on the server):"
	@echo "  make deploy                   Full first-time setup (venv + systemd + nginx)"
	@echo "  make deploy-update            Pull latest code and restart service"
	@echo "  make deploy-start             Start the systemd service"
	@echo "  make deploy-stop              Stop the systemd service"
	@echo "  make deploy-restart           Restart the systemd service"
	@echo "  make deploy-status            Show service status"
	@echo "  make deploy-logs              Tail live service logs"
	@echo ""
	@echo "  make clean                    Remove venv and cached files"
	@echo ""

install:
	python3 -m venv $(VENV)
	$(BIN)/pip install --upgrade pip --quiet
	$(BIN)/pip install -e . --quiet
	@echo "Done. Activate with: source $(VENV)/bin/activate"

download-models:
	$(BIN)/python -c "import os; from langchain_huggingface import HuggingFaceEmbeddings; HuggingFaceEmbeddings(model_name='all-MiniLM-L6-v2', cache_folder=os.path.join(os.getcwd(), 'models')); print('Model ready in ./models/')"

serve:
	-pkill -f "uvicorn web.server" 2>/dev/null; sleep 0.5
	$(BIN)/uvicorn web.server:app --host 0.0.0.0 --port 8000 --reload --log-level debug

ingest:
	$(BIN)/storage-expert ingest $(ARGS)

ask:
	$(BIN)/storage-expert ask $(ARGS)

chat:
	$(BIN)/storage-expert chat $(ARGS)

adduser:
	$(BIN)/storage-expert adduser $(ARGS)

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

# ── VM deployment (systemd + nginx, project at /data/storage-expert) ──────────
DEPLOY_DIR = /data/storage-expert
SERVICE    = storage-expert

deploy-setup:
	python3 -m venv $(DEPLOY_DIR)/.venv
	$(DEPLOY_DIR)/.venv/bin/pip install --upgrade pip --quiet
	$(DEPLOY_DIR)/.venv/bin/pip install -e . --quiet
	mkdir -p $(DEPLOY_DIR)/vendor_pdfs

deploy-install-service:
	cp deploy/storage-expert.service /etc/systemd/system/
	systemctl daemon-reload
	systemctl enable $(SERVICE)

deploy-install-nginx:
	cp deploy/nginx.conf /etc/nginx/sites-available/$(SERVICE)
	ln -sf /etc/nginx/sites-available/$(SERVICE) /etc/nginx/sites-enabled/$(SERVICE)
	nginx -t && systemctl reload nginx

deploy: deploy-setup deploy-install-service deploy-install-nginx
	systemctl start $(SERVICE)
	@echo "Deployed. App is running at http://$(shell hostname -I | awk '{print $$1}')"

deploy-update:
	git -C $(DEPLOY_DIR) pull
	$(DEPLOY_DIR)/.venv/bin/pip install -e . --quiet
	systemctl restart $(SERVICE)

deploy-start:
	systemctl start $(SERVICE)

deploy-stop:
	systemctl stop $(SERVICE)

deploy-restart:
	systemctl restart $(SERVICE)

deploy-status:
	systemctl status $(SERVICE)

deploy-logs:
	journalctl -u $(SERVICE) -f
