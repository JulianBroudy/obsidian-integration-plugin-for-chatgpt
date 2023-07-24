from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class Source(str, Enum):
    EMAIL = "EMAIL"
    FILE = "FILE"
    CHAT = "CHAT"


class DocumentMetadata(BaseModel):
    source: Optional[Source] = None
    source_id: Optional[str] = None
    url: Optional[str] = None
    created_at: Optional[str] = None
    author: Optional[str] = None


class DocumentChunkMetadata(DocumentMetadata):
    document_id: Optional[str] = None


class DocumentChunk(BaseModel):
    id: Optional[str] = None
    text: str
    metadata: DocumentChunkMetadata
    embedding: Optional[List[float]] = None


class DocumentChunkWithScore(DocumentChunk):
    score: float


class Document(BaseModel):
    id: Optional[str] = None
    text: str
    metadata: Optional[DocumentMetadata] = None


class DocumentWithChunks(Document):
    chunks: List[DocumentChunk]


class DocumentMetadataFilter(BaseModel):
    document_id: Optional[str] = None
    source: Optional[Source] = None
    source_id: Optional[str] = None
    author: Optional[str] = None
    start_date: Optional[str] = None  # any date string format
    end_date: Optional[str] = None  # any date string format


class Query(BaseModel):
    query: str
    filter: Optional[DocumentMetadataFilter] = None
    top_k: Optional[int] = 3


class QueryWithEmbedding(Query):
    embedding: List[float]


class QueryResult(BaseModel):
    query: str
    results: List[DocumentChunkWithScore]


class CommandStatus(str, Enum):
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    ERROR = "ERROR"


class CommandType(str, Enum):
    CREATE_NOTE = "CREATE_NOTE"
    MODIFY_NOTE = "MODIFY_NOTE"
    DELETE_NOTE = "DELETE_NOTE"


class CommandContent(BaseModel):
    text: str
    metadata: DocumentMetadata


class Command(BaseModel):
    id: Optional[str]
    status: CommandStatus = CommandStatus.NEW
    errors: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class CommandWithContent(Command):
    type: CommandType
    content: CommandContent
