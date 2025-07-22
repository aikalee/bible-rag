# Bible Commentary RAG
## Framework
### Data processing
- **Number of documents in the corpus:** 9318
- **Embedding Text:** Only titles, subtitles, and verses are embedded or indexed, due to the embedding model’s context window limitations.
- **Data Structure:** NoSQL-style documents stored in MongoDB using a JSON-like format (BSON) for efficient retrieval.

### Search Function
- **Searching Approach:** A hybrid approach combining FAISS for dense vector retrieval and Whoosh for BM25 sparse retrieval, followed by result re-ranking.
- **Reranker Quantization:** [TO BE UPDATED]

### Models
  
|                |Model Name                                  |  
|----------------|--------------------------------------------|
|Embedder        |BAAI/bge-small-en-v1.5                      |
|Reranker        |BAAI/bge-reranker                           |
|Generation model|meta-llama/Llama-3.3-70B-Instruct-Turbo-Free|

## Data Source and Attribution

This project uses content from the **Enduring Word Bible Commentary** by David Guzik.

©1996–present The Enduring Word Bible Commentary by David Guzik – [enduringword.com](https://enduringword.com)

The content is used for educational or research purposes within a Retrieval-Augmented Generation (RAG) framework.

All rights remain with the original author. Please refer to [Enduring Word's Terms of Use](https://enduringword.com) for further information.
