from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from loguru import logger

from datastore.datastore import DataStore
from models.models import (
    DocumentChunk,
    DocumentChunkMetadata,
    DocumentMetadataFilter,
    QueryResult,
    QueryWithEmbedding,
    DocumentChunkWithScore,
    CommandWithContent,
    Command
)
from services.date import to_unix_timestamp


# interface for Postgres client to implement pg based Datastore providers
class PGClient(ABC):
    @abstractmethod
    async def upsert(self, table: str, json: dict[str, Any]) -> None:
        """
        Takes in a list of documents and inserts them into the table.
        """
        raise NotImplementedError

    @abstractmethod
    async def update(self, table: str, json: dict[str, Any]):
        """
        Takes in a table and an object and updates the table with the object.
        """
        raise NotImplementedError

    @abstractmethod
    async def rpc(self, function_name: str, params: dict[str, Any]) -> Any:
        """
        Calls a stored procedure in the database with the given parameters.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_like(self, table: str, column: str, pattern: str) -> None:
        """
        Deletes rows in the table that match the pattern.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_in(self, table: str, column: str, ids: List[str]) -> None:
        """
        Deletes rows in the table that match the ids.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete_by_filters(
            self, table: str, filter: DocumentMetadataFilter
    ) -> None:
        """
        Deletes rows in the table that match the filter.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(
            self, table: str, id: str, columns: Optional[List[str]] = None
    ) -> Any:
        """
        Get a row by id from the database.
        """
        raise NotImplementedError


# abstract class for Postgres based Datastore providers that implements DataStore interface
class PgVectorDataStore(DataStore):
    def __init__(self):
        self.client = self.create_db_client()

    @abstractmethod
    def create_db_client(self) -> PGClient:
        """
        Create db client, can be accessing postgres database via different APIs.
        Can be supabase client or psycopg2 based client.
        Return a client for postgres DB.
        """

        raise NotImplementedError

    async def _upsert(self, chunks: Dict[str, List[DocumentChunk]]) -> List[str]:
        """
        Takes in a dict of document_ids to list of document chunks and inserts them into the database.
        Return a list of document ids.
        """
        for document_id, document_chunks in chunks.items():
            for chunk in document_chunks:
                json = {
                    "id": chunk.id,
                    "content": chunk.text,
                    "embedding": chunk.embedding,
                    "document_id": document_id,
                    "source": chunk.metadata.source,
                    "source_id": chunk.metadata.source_id,
                    "url": chunk.metadata.url,
                    "author": chunk.metadata.author,
                }
                if chunk.metadata.created_at:
                    json["created_at"] = (
                        datetime.fromtimestamp(
                            to_unix_timestamp(chunk.metadata.created_at)
                        ),
                    )
                await self.client.upsert("documents", json)

        return list(chunks.keys())

    async def _query(self, queries: List[QueryWithEmbedding]) -> List[QueryResult]:
        """
        Takes in a list of queries with embeddings and filters and returns a list of query results with matching document chunks and scores.
        """
        query_results: List[QueryResult] = []
        for query in queries:
            # get the top 3 documents with the highest cosine similarity using rpc function in the database called "match_page_sections"
            params = {
                "in_embedding": query.embedding,
            }
            if query.top_k:
                params["in_match_count"] = query.top_k
            if query.filter:
                if query.filter.document_id:
                    params["in_document_id"] = query.filter.document_id
                if query.filter.source:
                    params["in_source"] = query.filter.source.value
                if query.filter.source_id:
                    params["in_source_id"] = query.filter.source_id
                if query.filter.author:
                    params["in_author"] = query.filter.author
                if query.filter.start_date:
                    params["in_start_date"] = datetime.fromtimestamp(
                        to_unix_timestamp(query.filter.start_date)
                    )
                if query.filter.end_date:
                    params["in_end_date"] = datetime.fromtimestamp(
                        to_unix_timestamp(query.filter.end_date)
                    )
            logger.info(params)
            try:
                data = await self.client.rpc("match_page_sections", params=params)
                results: List[DocumentChunkWithScore] = []
                for row in data:
                    document_chunk = DocumentChunkWithScore(
                        id=row["id"],
                        text=row["content"],
                        # TODO: add embedding to the response ?
                        # embedding=row["embedding"],
                        score=float(row["similarity"]),
                        metadata=DocumentChunkMetadata(
                            source=row["source"],
                            source_id=row["source_id"],
                            document_id=row["document_id"],
                            url=row["url"],
                            created_at=row["created_at"],
                            author=row["author"],
                        ),
                    )
                    results.append(document_chunk)
                query_results.append(QueryResult(query=query.query, results=results))
            except Exception as e:
                logger.error(e)
                query_results.append(QueryResult(query=query.query, results=[]))
        return query_results

    async def delete(
            self,
            ids: Optional[List[str]] = None,
            filter: Optional[DocumentMetadataFilter] = None,
            delete_all: Optional[bool] = None,
    ) -> bool:
        """
        Removes vectors by ids, filter, or everything in the datastore.
        Multiple parameters can be used at once.
        Returns whether the operation was successful.
        """
        if delete_all:
            try:
                await self.client.delete_like("documents", "document_id", "%")
            except:
                return False
        elif ids:
            try:
                await self.client.delete_in("documents", "document_id", ids)
            except:
                return False
        elif filter:
            try:
                await self.client.delete_by_filters("documents", filter)
            except:
                return False
        return True

    async def create_command(self, command: CommandWithContent) -> str:
        """
        Creates a command in the database.
        Returns a dict with the command_id and the command.
        """
        command.id = str(uuid4())
        logger.info("got to create command in pgvector data store. Id: " + command.id)
        logger.info("Command: " + str(command.dict()))
        await self.client.upsert("commands", command.dict())
        return command.id

    async def get_command(self, command_id: str) -> Command | None:
        """
        Queries the database for a command with the given id without the CommandContent.
        """
        fields = list(Command.schema().get('properties').keys())
        data = await self.client.get_by_id("commands", command_id, fields)
        if data:
            return Command(**data[0])
        else:
            return None

    async def update_command(self, command: Command) -> bool:
        """
        Updates the command in the database.
        Returns whether the operation was successful.
        """
        logger.info("Attempting to update command in pgvector data store. Command: " + str(command))
        await self.client.update("commands", command.dict())
        return True
