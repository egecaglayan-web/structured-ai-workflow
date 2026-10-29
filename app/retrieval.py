import re
from dataclasses import dataclass
from pathlib import Path

STOP_WORDS = set("a an the this that is are to of for in on and or with can i we you my it be as do have please".split())


def tokens(text: str) -> set[str]:
    return {word for word in re.findall(r"\w+", text.casefold()) if len(word) > 2 and word not in STOP_WORDS}


@dataclass(frozen=True)
class Chunk:
    source_id: str
    document: str
    excerpt: str


def load_corpus(directory: Path) -> list[Chunk]:
    if not directory.is_dir():
        raise ValueError("Reference directory does not exist.")
    paths = sorted(p for p in directory.iterdir() if p.suffix.lower() in {".md", ".txt"})
    if len(paths) > 30:
        raise ValueError("Small-corpus limit is 30 documents.")
    chunks = []
    for path in paths:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 100_000:
            raise ValueError("Reference files must be regular UTF-8 files under 100 KB.")
        text = path.read_text(encoding="utf-8")
        # Bound each context excerpt, keeping exact source text for citations.
        for offset in range(0, len(text), 1000):
            excerpt = text[offset:offset + 1000].strip()
            if excerpt:
                chunks.append(Chunk(f"{path.name}:{offset // 1000 + 1}", path.name, excerpt))
    return chunks


def retrieve(query: str, chunks: list[Chunk]) -> list[Chunk]:
    query_tokens = tokens(query)
    ranked = [(len(query_tokens & tokens(c.excerpt)), c) for c in chunks]
    ranked.sort(key=lambda pair: (-pair[0], pair[1].source_id))
    return [chunk for score, chunk in ranked[:3] if score > 0]
