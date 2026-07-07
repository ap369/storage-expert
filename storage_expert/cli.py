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
@click.option("--model", default=None, metavar="MODEL", help="Model name override  [env: LLM_MODEL]")
def ask(question, model):
    """Ask a single question (non-interactive)."""
    from storage_expert.qa import ask_question
    try:
        ask_question(question, model)
    except ValueError as e:
        raise click.ClickException(str(e))


@cli.command()
@click.option("--model", default=None, metavar="MODEL", help="Model name override  [env: LLM_MODEL]")
def chat(model):
    """Start an interactive chat session with conversation memory."""
    from storage_expert.chat import start_chat
    try:
        start_chat(model)
    except ValueError as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("username")
@click.password_option()
def adduser(username, password):
    """Add a user who can log in to the web UI."""
    from storage_expert.auth import init_db, add_user
    import sqlite3
    init_db()
    try:
        add_user(username, password)
        click.echo(f"User '{username}' created.")
    except sqlite3.IntegrityError:
        raise click.ClickException(f"User '{username}' already exists.")
