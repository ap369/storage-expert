import os
import warnings

import click
from dotenv import load_dotenv

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

load_dotenv()


@click.group()
def cli():
    """Storage Expert — query enterprise storage vendor PDFs with AI."""


@cli.command()
@click.option("--file", "filepath", default=None, metavar="PATH", help="Single PDF to ingest")
@click.option("--folder", "folder_path", default=None, metavar="DIR", help="Folder of PDFs to ingest")
def ingest(filepath, folder_path):
    """Ingest PDF files into the persistent knowledge base."""
    if not filepath and not folder_path:
        raise click.UsageError("Provide --file <path> or --folder <dir> (or both)")

    from storage_expert.ingest import ingest_file, ingest_folder

    if filepath:
        ingest_file(filepath)
    if folder_path:
        ingest_folder(folder_path)


@cli.command()
@click.argument("question")
@click.option("--provider", default=None, metavar="PROVIDER",
              help="LLM provider: claude | openai | ollama | groq | custom  [env: STORAGE_EXPERT_PROVIDER]")
@click.option("--model", default=None, metavar="MODEL", help="Model name override")
def ask(question, provider, model):
    """Ask a single question (non-interactive)."""
    provider = provider or os.getenv("STORAGE_EXPERT_PROVIDER", "claude")
    from storage_expert.qa import ask_question
    try:
        ask_question(question, provider, model)
    except ValueError as e:
        raise click.ClickException(str(e))


@cli.command()
@click.option("--provider", default=None, metavar="PROVIDER",
              help="LLM provider: claude | openai | ollama | groq | custom  [env: STORAGE_EXPERT_PROVIDER]")
@click.option("--model", default=None, metavar="MODEL", help="Model name override")
def chat(provider, model):
    """Start an interactive chat session with conversation memory."""
    provider = provider or os.getenv("STORAGE_EXPERT_PROVIDER", "claude")
    from storage_expert.chat import start_chat
    try:
        start_chat(provider, model)
    except ValueError as e:
        raise click.ClickException(str(e))
