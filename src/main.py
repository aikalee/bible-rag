from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from rag import Retriever, Generator, pipeline

# === Initialize Retriever and Generator ===
models_ready = False
retriever = None
generator = None

@asynccontextmanager
async def lifespan(app: FastAPI):

    global retriever, generator, models_ready

    # Initialize models here (can be async)
    retriever = Retriever()
    generator = Generator()
    models_ready = True
    yield

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Data class with automatic validating and parsing === 
class QueryRequest(BaseModel):
    query: str

@app.post("/query")
async def query_route(data: QueryRequest):

    def stream():
        for chunk in pipeline(data.query, retriever, generator):
            yield chunk

    return StreamingResponse(stream(), media_type="text/plain")

@app.get("/health")
def health():
    return {
        "message": "FastAPI is running",
        "models_ready": models_ready,
    }
