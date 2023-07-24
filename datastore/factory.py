from datastore.datastore import DataStore
import os


async def get_datastore() -> DataStore:
    datastore = os.environ.get("DATASTORE")
    assert datastore is not None

    match datastore:
        case "supabase":
            from datastore.providers.supabase_datastore import SupabaseDataStore
            return SupabaseDataStore()
        case _:
            raise ValueError(
                f"Unsupported vector database: {datastore}. "
                f"Try one of the following: llama, pinecone, weaviate, milvus, zilliz, redis, or qdrant"
            )