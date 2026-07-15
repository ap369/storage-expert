import logging
from functools import lru_cache
from pathlib import Path

from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from storage_expert.providers import get_embeddings

CHROMA_PATH = "./chroma_db"
_EMBED_BATCH = 50

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_vectorstore() -> Chroma:
    return Chroma(persist_directory=CHROMA_PATH, embedding_function=get_embeddings())


def already_ingested(vectorstore: Chroma, abs_path: str) -> bool:
    results = vectorstore._collection.get(where={"source": abs_path})
    return len(results["ids"]) > 0


def ingest_file(filepath: str) -> int:
    abs_path = str(Path(filepath).resolve())

    if not Path(abs_path).exists():
        logger.error("File not found: %s", filepath)
        return 0

    vectorstore = get_vectorstore()

    if already_ingested(vectorstore, abs_path):
        logger.info("Skipping (already ingested): %s", Path(filepath).name)
        return 0

    size_mb = Path(abs_path).stat().st_size / 1_048_576
    logger.info("Ingesting: %s (%.1f MB)", Path(filepath).name, size_mb)

    try:
        loader = PyMuPDFLoader(abs_path)
        docs = loader.load()
    except Exception as e:
        logger.warning("Could not read %s: %s", filepath, e)
        return 0

    logger.info("  Loaded %d pages — chunking...", len(docs))
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_documents(docs)
    logger.info("  Created %d chunks — embedding (this may take a while)...", len(chunks))

    for i in range(0, len(chunks), _EMBED_BATCH):
        batch = chunks[i:i + _EMBED_BATCH]
        vectorstore.add_documents(batch)
        done = min(i + _EMBED_BATCH, len(chunks))
        logger.info("  Embedded %d/%d chunks...", done, len(chunks))

    logger.info("  Done: stored %d chunks from %d pages", len(chunks), len(docs))
    return len(chunks)


def ingest_folder(folder_path: str) -> None:
    folder = Path(folder_path)
    if not folder.is_dir():
        logger.error("Not a directory: %s", folder_path)
        return

    pdfs = sorted(folder.glob("*.pdf"))
    if not pdfs:
        logger.info("No PDF files found in %s", folder_path)
        return

    for pdf in pdfs:
        ingest_file(str(pdf))
