from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from storage_expert.providers import get_embeddings

CHROMA_PATH = "./chroma_db"


def _get_vectorstore() -> Chroma:
    return Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())


def _already_ingested(vectorstore: Chroma, abs_path: str) -> bool:
    results = vectorstore._collection.get(where={"source": abs_path})
    return len(results["ids"]) > 0


def ingest_file(filepath: str) -> None:
    abs_path = str(Path(filepath).resolve())

    if not Path(abs_path).exists():
        print(f"Error: File not found: {filepath}")
        return

    vectorstore = _get_vectorstore()

    if _already_ingested(vectorstore, abs_path):
        print(f"Skipping (already ingested): {Path(filepath).name}")
        return

    print(f"Ingesting: {Path(filepath).name}")
    try:
        loader = PyMuPDFLoader(abs_path)
        docs = loader.load()
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}")
        return

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)

    vectorstore.add_documents(chunks)
    print(f"  Stored {len(chunks)} chunks from {len(docs)} pages")


def ingest_folder(folder_path: str) -> None:
    folder = Path(folder_path)
    if not folder.is_dir():
        print(f"Error: Not a directory: {folder_path}")
        return

    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        print(f"No PDF files found in {folder_path}")
        return

    for pdf in pdfs:
        ingest_file(str(pdf))
