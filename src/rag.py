import faiss
import os
import torch
from dotenv import load_dotenv
from FlagEmbedding import FlagModel
from optimum.onnxruntime import ORTModelForSequenceClassification
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from together import Together
from transformers import AutoTokenizer
from transformers.utils.logging import set_verbosity_error
from whoosh import index
from whoosh.qparser import QueryParser, OrGroup


class Retriever:

    def __init__(self):

        # === Run when initialize the class object ===
        self.clients = self.launch_clients()
        self.indices = self.load_indices()
       
    
    def launch_clients(self, mongo_user=None, mongo_pass=None):

        load_dotenv()
        set_verbosity_error()

        EMBEDDER_NAME = "BAAI/bge-small-en-v1.5"
        INSTRUCTION = "Represent this sentence for searching relevant passages: "

        RERANKER_PATH = "../models/onnx_model_quant"

        # === Use default variables if custom variables not found ===
        mongo_user = mongo_user or os.getenv("MONGO_USER")
        mongo_pass = mongo_pass or os.getenv("MONGO_PASS")

        embedder = FlagModel(EMBEDDER_NAME, 
                        query_instruction_for_retrieval=INSTRUCTION,
                        use_fp16=True)
        
        tokenizer = AutoTokenizer.from_pretrained(RERANKER_PATH)
        reranker = ORTModelForSequenceClassification.from_pretrained(RERANKER_PATH)

        URI = f"mongodb+srv://{mongo_user}:{mongo_pass}@bible-rag-prod.w3pskcn.mongodb.net/?retryWrites=true&w=majority&appName=bible-rag-prod"
        client = MongoClient(URI, server_api=ServerApi('1'))

        db = client["bible"]
        collection = db["commentary"]

        return {"embedder": embedder, "tokenizer": tokenizer, "reranker": reranker, "collection": collection}
    
    def load_indices(self):

        FAISS_PATH = "../data/bge-small-en-v1.5.faiss"
        WHOOSH_PATH = "../data/bm25"

        # === Load document embeddings and indices ===
        faiss_index = faiss.read_index(FAISS_PATH)
        whoosh_index = index.open_dir(WHOOSH_PATH)

        return {"faiss_index": faiss_index, "whoosh_index": whoosh_index}
    
    def from_database(self, doc_ids, text_only=False):

        collection = self.clients["collection"]

        query_filter = {"metadata.doc_id": {"$in": doc_ids}}
        field_filter = {"text": 1, "_id": 0} if text_only else None

        if field_filter:
            docs = list(collection.find(query_filter, field_filter))
            docs = [x["text"] for x in docs]
        else:
            docs = list(collection.find(query_filter))
           
        return docs
    
    def search(self, query):

        embedder = self.clients["embedder"]

        faiss_index = self.indices["faiss_index"]
        whoosh_index = self.indices["whoosh_index"]

        N = 10

        # === Embed user query ===
        query_embedding = embedder.encode_queries([query])

        # === Find documents with cosine similarity ===
        faiss_similarities, faiss_indices = faiss_index.search(query_embedding, k=N)

        # === Find documents with BM25 ===
        parser = QueryParser("text", whoosh_index.schema, group=OrGroup)
        parsed_query = parser.parse(query)

        with whoosh_index.searcher() as searcher:
            results = searcher.search(parsed_query, limit=N)
            whoosh_indices = [x['index'] for x in results]

        # === Find the union of documents returned by FAISS and WHOOSH ===
        union = set(whoosh_indices) | set(faiss_indices.squeeze().tolist())

        return list(union)
    
    
    def rerank(self, docs, query, k=5, n_std=1.0):
        
        tokenizer = self.clients["tokenizer"]
        reranker = self.clients["reranker"]

        queries = [query] * len(docs)
        inputs = tokenizer(queries, docs, return_tensors="pt", padding=True, truncation=True)

        with torch.no_grad():
            outputs = reranker(**inputs)
            scores = outputs.logits.squeeze(-1)
        
        # === Soft threshold ===
        threshold = scores.mean() + n_std * scores.std()
        top_id_indices = torch.where(scores >= threshold)

        # === Top-k documents ===
        if len(top_id_indices) > k:
            top_k = torch.topk(scores, k)
            top_id_indices = top_k.indices
        
        return top_id_indices
    
    def retrieve(self, query):

        doc_ids = self.search(query)
        docs = self.from_database(doc_ids, True)

        top_id_indices = self.rerank(docs, query)

        top_ids = torch.as_tensor(list(doc_ids))[top_id_indices].tolist()
        top_docs = self.from_database(top_ids, False)

        return top_docs
    

class Generator:

    def __init__(self):
        self.client = self.launch_client()
        self.system_prompt = self.system_prompt()
        

    def launch_client(self):

        client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

        return client
    
    
    def system_prompt(self):

        # === Tasks Context ===    
        TASK_CONTEXT = """
        You're a pastor and an expert in Bible study. Your goal is to 
        explain the Bible to users.
        """

        # === Tone Context ===
        TONE_CONTEXT = """
        You should maintain a professional tone.
        """

        # === Task Description ===
        TASK_DESCRIPTION = """
        - Please rely on the commentary in the documents provided by the user. 
          Only answer if you know the answer with certainty. However, do not 
          mention the documents in your response. Provide a natural, fluent answer 
          as if you know the information directly.

        - If you are unsure how to respond, say \"Sorry, I didn't understand that. 
          Could you rephrase your question?\"

        - If someone asks something irrelevant, say, \"Sorry, I am an expert in 
          Bible study and explain the Bible. Do you have a Biblical question today 
          I can help you with?\
        """

        # === Chain-of-Thoughts ===
        PRECOGNITION = """
        Think through the problem carefully before answering. You may think silently, 
        but only return your final answer.
        """
        
        # === Output Formmatting ===
        OUTPUT_FORMATTING = """
        """

        SYSTEM_PROMPT = f"""
        {TASK_CONTEXT}\n\n
        {TONE_CONTEXT}\n\n
        {TASK_DESCRIPTION}\n\n
        {PRECOGNITION}\n\n
        {OUTPUT_FORMATTING}
        """
        return SYSTEM_PROMPT
    
    def user_prompt(self, query, docs):

        # === Remind LLM about the task ===
        IMMEDIATE_TASK = """
        How do you respond to the user's question?
        """

        documents = ""

        for i, doc in enumerate(docs):

            metadata = doc["metadata"]

            book = metadata["book"]
            beg_verse = metadata["beg_verse"]
            end_verse = metadata["end_verse"]

            verse = metadata["verse"]
            commentary = metadata["commentary"]

            document_string = f"""
            Document {i+1}:
            Book: {book}, Chapter-Verse Numbers: {beg_verse} - {end_verse}
            Verses: {verse}
            Commentary of the verses: {commentary}
            """

            documents += document_string
       
        user_prompt = f"""
        ### Contexts: 
        {documents}

        ### Here is the user query:
        {query}

        {IMMEDIATE_TASK}     
        """
        return user_prompt

    
    def generate(self, query, docs):

        GENERATOR = "meta-llama/Llama-Vision-Free"
        # GENERATOR = "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"
        MAX_TOKENS = 1000
        TEMPERATURE = 0.7


        user_prompt = self.user_prompt(query, docs)

        response = self.client.chat.completions.create(
            model= GENERATOR,
            messages=[
                {
                    "role": "system", 
                    "content": self.system_prompt
                },
                {
                    "role": "user", 
                    "content": user_prompt
                }
            ],
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE,
            stream=True
        )

        for chunk in response:

            if len(chunk.choices) > 0:
               first_choice = chunk.choices[0]

            if hasattr(first_choice, 'delta') and hasattr(first_choice.delta, 'content'):
                content = first_choice.delta.content

                if content:
                    yield content
              

def pipeline(query, retriever, generator):

    docs = retriever.retrieve(query)
    response = generator.generate(query, docs)
    
    for content in response:
        if content:
            yield content
            

def main():
    retriever = Retriever()
    generator = Generator()
    
    sample_query = "Are there any verses about food?"
    response = pipeline(sample_query, retriever, generator)
    for content in response:
        if content:
            print(content, end='', flush=True)
            

if __name__ == "__main__":
    main()