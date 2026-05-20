from whoosh import index
from whoosh.fields import Schema, TEXT, NUMERIC
import json
import os


def bm25_index(corpus, writing_dir="../../data/bm25"):

    schema = Schema(text=TEXT(stored=True), index=NUMERIC(stored=True, unique=True))

    if not os.path.exists(writing_dir):
        os.mkdir(writing_dir)

    try:
    
        ix = index.create_in(writing_dir, schema)

        writer = ix.writer()

        for text in corpus:
            writer.add_document(**text)
        
        writer.commit()

    except Exception as e:

        writer.cancel()
        print(f"Failed to write to {writing_dir} because {e} occur. Writer cancelled.")


def main():

    READING_PATH = "../../data/commentary.json"

    with open(READING_PATH, encoding="utf-8") as f:
        commentary = json.load(f)

    corpus = [{"text": commentary[i]["text"], "index": i} for i in range(len(commentary))]

    bm25_index(corpus)

if __name__ == "__main__":
    main()