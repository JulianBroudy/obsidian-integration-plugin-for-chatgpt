import os
from enum import Enum
from typing import Any, List, Optional

from loguru import logger
from supabase import Client

from datastore.providers.pgvector_datastore import PGClient, PgVectorDataStore
from models.models import (
    DocumentMetadataFilter, )

SUPABASE_URL = os.environ.get("SUPABASE_URL")
assert SUPABASE_URL is not None, "SUPABASE_URL is not set"
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
# use service role key if you want this app to be able to bypass your Row Level Security policies
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
assert (
        SUPABASE_ANON_KEY is not None or SUPABASE_SERVICE_ROLE_KEY is not None
), "SUPABASE_ANON_KEY or SUPABASE_SERVICE_ROLE_KEY must be set"


# class that implements the DataStore interface for Supabase Datastore provider
class SupabaseDataStore(PgVectorDataStore):
    def create_db_client(self):
        return SupabaseClient()


class SupabaseClient(PGClient):

    def __init__(self) -> None:
        super().__init__()
        if not SUPABASE_SERVICE_ROLE_KEY:
            self.client = Client(SUPABASE_URL, SUPABASE_ANON_KEY)
        else:
            self.client = Client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    async def upsert(self, table: str, json: dict[str, Any]):
        """
        Takes in a list of documents and inserts them into the table.
        """

        logger.info("Got to upsert in supabase_datastore.py")
        logger.info("Json before conversion: " + str(json))
        json = self._convert_object_to_serializable_json(json)
        logger.info("Json after conversion: " + str(json))

        if "created_at" in json:
            json["created_at"] = json["created_at"][0].isoformat()

        try:
            self.client.table(table).upsert(json).execute()
        except Exception as e:
            logger.error("Got exception in supabase_datastore.py: " + str(e), e)

    def _convert_object_to_serializable_json(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {k: self._convert_object_to_serializable_json(v) for k, v in data.items() if v is not None}
        elif isinstance(data, list):
            return [self._convert_object_to_serializable_json(v) for v in data]
        elif isinstance(data, Enum):
            return data.value
        else:
            return data

    async def update(self, table: str, json: dict[str, Any]):
        """
        Takes in a list of documents and inserts them into the table.
        """
        logger.info("Command before serializing: " + str(json))
        json = self._convert_object_to_serializable_json(json)
        logger.info("Command after serializing: " + str(json))
        self.client.table(table).update(json).eq("id", json["id"]).execute()

    async def get_by_id(self, table: str, id: str, columns: Optional[List[str]] = None) -> Any:
        """
        Get a row by id from the database.
        """
        if columns is None:
            columns = ["*"]
        response = self.client.table(table).select(",".join(columns)).eq("id", id).execute()
        return response.data

    async def rpc(self, function_name: str, params: dict[str, Any]):
        """
        Calls a stored procedure in the database with the given parameters.
        """
        if "in_start_date" in params:
            params["in_start_date"] = params["in_start_date"].isoformat()
        if "in_end_date" in params:
            params["in_end_date"] = params["in_end_date"].isoformat()

        response = self.client.rpc(function_name, params=params).execute()
        return response.data

    async def delete_like(self, table: str, column: str, pattern: str):
        """
        Deletes rows in the table that match the pattern.
        """
        self.client.table(table).delete().like(column, pattern).execute()

    async def delete_in(self, table: str, column: str, ids: List[str]):
        """
        Deletes rows in the table that match the ids.
        """
        self.client.table(table).delete().in_(column, ids).execute()

    async def delete_by_filters(self, table: str, filter: DocumentMetadataFilter):
        """
        Deletes rows in the table that match the filter.
        """
        builder = self.client.table(table).delete()
        if filter.document_id:
            builder = builder.eq(
                "document_id",
                filter.document_id,
            )
        if filter.source:
            builder = builder.eq("source", filter.source)
        if filter.source_id:
            builder = builder.eq("source_id", filter.source_id)
        if filter.author:
            builder = builder.eq("author", filter.author)
        if filter.start_date:
            builder = builder.gte(
                "created_at",
                filter.start_date[0].isoformat(),
            )
        if filter.end_date:
            builder = builder.lte(
                "created_at",
                filter.end_date[0].isoformat(),
            )
        builder.execute()
