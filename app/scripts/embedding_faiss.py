import numpy as np
import faiss

def embed_text(texts, client , model="text-embedding-3-large"):
    embeddings = []
    batch_size = 20
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i+batch_size]
        resp = client.embeddings.create(input=batch, model=model)
        batch_embeddings = [e.embedding for e in resp.data]
        embeddings.extend(batch_embeddings)
    return np.array(embeddings).astype("float32")

def build_faiss_index(embeddings):
    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    faiss.normalize_L2(embeddings)
    index.add(embeddings)
    return index
