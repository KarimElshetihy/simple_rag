import json
import logging
from hashlib import sha256
from typing import List
from uuid import uuid4

from sqlalchemy import text as sqltext
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from ..vector_db_interface import VectorDBInterface
from src.enums.vector_db_enums import (
    DistanceMethodEnums,
    PGVectorDistanceMethodEnums,
    PGVectorIndexTypeEnums,
    PGVectorSchemaEnums,
)
from src.models.vector_schemes import RetrievedDocument


class PGVectorDBProvider(VectorDBInterface):
    supports_chunk_ids = True

    def __init__(
        self,
        db_path: str,
        distance_method: str,
        embedding_size: int = 786,
        index_type: str = PGVectorIndexTypeEnums.HNSW.value,
    ):
        self.db_path = db_path
        self.distance_method = distance_method
        self.embedding_size = embedding_size
        self.index_type = index_type
        self.table_prefix = PGVectorSchemaEnums._PREFIX.value
        self.engine: AsyncEngine | None = None
        self.logger = logging.getLogger(__name__)

    async def connect(self):
        database_url = make_url(self.db_path)
        if database_url.drivername in ("postgresql", "postgres"):
            database_url = database_url.set(drivername="postgresql+asyncpg")
        elif database_url.drivername in (
            "postgresql+psycopg2",
            "postgresql+psycopg",
        ):
            database_url = database_url.set(drivername="postgresql+asyncpg")

        engine = create_async_engine(database_url)
        self.engine = engine
        self.logger.info("Connected to PostgreSQL at %s", database_url.host)

    async def disconnect(self):
        if self.engine is not None:
            await self.engine.dispose()
            self.engine = None
            self.logger.info("Disconnected from PostgreSQL")

    def _require_engine(self) -> AsyncEngine:
        if self.engine is None:
            raise RuntimeError("The pgvector provider is not connected.")
        return self.engine

    @staticmethod
    def _table_name(collection_name: str) -> str:
        if not collection_name:
            raise ValueError("Collection name must not be empty.")

        table_name = f"{PGVectorSchemaEnums._PREFIX.value}_{collection_name}"
        if len(table_name.encode("utf-8")) > 63:
            raise ValueError("Collection name is too long for a PostgreSQL table.")
        return table_name

    def _quoted_table_name(self, collection_name: str) -> str:
        engine = self._require_engine()
        return engine.dialect.identifier_preparer.quote(
            self._table_name(collection_name)
        )

    async def collection_exists(self, collection_name: str) -> bool:
        table_name = self._table_name(collection_name)
        engine = self._require_engine()
        async with engine.connect() as connection:
            return bool(
                (
                    await connection.execute(
                        sqltext(
                            "SELECT EXISTS ("
                            "SELECT 1 FROM information_schema.tables "
                            "WHERE table_schema = current_schema() "
                            "AND table_name = :table_name)"
                        ),
                        {"table_name": table_name},
                    )
                ).scalar_one_or_none()
            )

    async def list_collections(self) -> List[str]:
        prefix = f"{PGVectorSchemaEnums._PREFIX.value}_"
        engine = self._require_engine()
        async with engine.connect() as connection:
            rows = await connection.execute(
                sqltext(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = current_schema() "
                    "AND left(table_name, :prefix_length) = :prefix "
                    "ORDER BY table_name"
                ),
                {"prefix": prefix, "prefix_length": len(prefix)},
            )
            return rows.scalars().all()

    async def get_collection_info(self, collection_name: str) -> dict:
        table_name = self._table_name(collection_name)
        engine = self._require_engine()
        async with engine.connect() as connection:
            rows = await connection.execute(
                sqltext(
                    "SELECT column_name, data_type, udt_name, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = :table_name "
                    "ORDER BY ordinal_position"
                ),
                {"table_name": table_name},
            )
            columns = [dict(row._mapping) for row in rows]
        if not columns:
            raise ValueError(f"Collection does not exist: {collection_name}")
        return {
            "name": collection_name,
            "table_name": table_name,
            "columns": columns,
        }

    async def delete_collection(self, collection_name: str):
        table_name = self._quoted_table_name(collection_name)
        engine = self._require_engine()
        async with engine.begin() as connection:
            await connection.execute(sqltext(f"DROP TABLE IF EXISTS {table_name}"))

    async def publish_staging_collection(
        self, staging_collection: str, collection_name: str
    ) -> None:
        if staging_collection == collection_name:
            raise ValueError("The staging and published collection names must differ.")
        if not await self.collection_exists(staging_collection):
            raise ValueError(f"Staging collection does not exist: {staging_collection}")

        staging_table = self._table_name(staging_collection)
        published_table = self._table_name(collection_name)
        engine = self._require_engine()
        preparer = engine.dialect.identifier_preparer
        quoted_staging_table = preparer.quote(staging_table)
        quoted_published_table = preparer.quote(published_table)
        staging_index_prefix, _ = self._vector_index_names(
            staging_collection, self.index_type
        )
        published_index_prefix, _ = self._vector_index_names(
            collection_name, self.index_type
        )

        async with engine.begin() as connection:
            await connection.execute(
                sqltext(f"DROP TABLE IF EXISTS {quoted_published_table}")
            )
            await connection.execute(
                sqltext(
                    f"ALTER TABLE {quoted_staging_table} "
                    f"RENAME TO {quoted_published_table}"
                )
            )
            index_names = (
                await connection.execute(
                    sqltext(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = current_schema() "
                        "AND tablename = :table_name"
                    ),
                    {"table_name": published_table},
                )
            ).scalars().all()
            for existing_name in index_names:
                if existing_name.startswith(staging_index_prefix):
                    suffix = existing_name[len(staging_index_prefix) :]
                    published_name = f"{published_index_prefix}{suffix}"
                    if len(published_name.encode("utf-8")) > 63:
                        raise ValueError("Published vector index name is too long.")
                    await connection.execute(
                        sqltext(
                            f"ALTER INDEX {preparer.quote(existing_name)} "
                            f"RENAME TO {preparer.quote(published_name)}"
                        )
                    )

        self.logger.info(
            "Published staging collection %s as %s.",
            staging_collection,
            collection_name,
        )

    async def create_collection(
        self, collection_name: str, embedding_size: int
    ):
        if embedding_size <= 0:
            raise ValueError("Embedding size must be greater than zero.")

        table_name = self._quoted_table_name(collection_name)
        if await self.collection_exists(collection_name):
            return False

        engine = self._require_engine()
        schema = PGVectorSchemaEnums
        chunk_fk_name = engine.dialect.identifier_preparer.quote(
            f"fk_vec_chunk_{sha256(self._table_name(collection_name).encode()).hexdigest()[:16]}"
        )
        quoted_columns = {
            column: engine.dialect.identifier_preparer.quote(column.value)
            for column in (
                schema.ID,
                schema.CHUNK_ID,
                schema.VECTOR,
                schema.TEXT,
                schema.METADATA,
            )
        }
        async with engine.begin() as connection:
            await connection.execute(
                sqltext(
                    f"CREATE TABLE {table_name} ("
                    f"{quoted_columns[schema.ID]} TEXT PRIMARY KEY, "
                    f"{quoted_columns[schema.CHUNK_ID]} INTEGER NOT NULL UNIQUE, "
                    f"{quoted_columns[schema.VECTOR]} vector({embedding_size}) NOT NULL, "
                    f"{quoted_columns[schema.TEXT]} TEXT NOT NULL, "
                    f"{quoted_columns[schema.METADATA]} JSONB NOT NULL "
                    "DEFAULT '{}'::jsonb, "
                    f"CONSTRAINT {chunk_fk_name} "
                    f"FOREIGN KEY ({quoted_columns[schema.CHUNK_ID]}) "
                    'REFERENCES "asset_chunks" ("chunk_id") ON DELETE CASCADE'
                    ")"
                )
            )
        self.logger.info("Collection %s created.", collection_name)
        return True

    def _vector_index_names(self, collection_name: str, index_type: str) -> tuple[str, str]:
        table_name = self._table_name(collection_name)
        name_prefix = f"vecidx_{sha256(table_name.encode()).hexdigest()[:12]}_"
        index_name = f"{name_prefix}{index_type}_{self.distance_method}"
        if len(index_name.encode("utf-8")) > 63:
            raise ValueError("Generated vector index name is too long.")
        return name_prefix, index_name

    async def ensure_vector_index(
        self, collection_name: str, index_type: str | None = None, lists: int | None = None
    ) -> bool:
        selected_type = PGVectorIndexTypeEnums(
            index_type or self.index_type
        ).value
        distance_operators = {
            DistanceMethodEnums.COSINE.value: PGVectorDistanceMethodEnums.COSINE.value,
            DistanceMethodEnums.DOT.value: PGVectorDistanceMethodEnums.DOT.value,
        }
        try:
            operator_class = distance_operators[self.distance_method]
        except KeyError as error:
            raise ValueError(
                f"Unsupported pgvector distance method: {self.distance_method}"
            ) from error

        if not await self.collection_exists(collection_name):
            raise ValueError(f"Collection does not exist: {collection_name}")

        name_prefix, index_name = self._vector_index_names(
            collection_name, selected_type
        )
        engine = self._require_engine()
        preparer = engine.dialect.identifier_preparer
        table_name = self._quoted_table_name(collection_name)
        vector_column = preparer.quote(PGVectorSchemaEnums.VECTOR.value)
        quoted_index_name = preparer.quote(index_name)
        index_options = ""
        if selected_type == PGVectorIndexTypeEnums.IVFFLAT.value:
            if lists is None:
                async with engine.connect() as connection:
                    row_count = await connection.scalar(
                        sqltext(f"SELECT count(*) FROM {table_name}")
                    )
                if not row_count:
                    raise ValueError(
                        "IVFFlat index creation requires a non-empty collection."
                    )
                lists = max(
                    1,
                    row_count // 1000
                    if row_count <= 1_000_000
                    else round(row_count**0.5),
                )
            if not isinstance(lists, int) or isinstance(lists, bool) or lists <= 0:
                raise ValueError("IVFFlat lists must be greater than zero.")
            index_options = f" WITH (lists = {lists})"
        elif lists is not None:
            raise ValueError("The lists option applies only to IVFFlat indexes.")

        async with engine.begin() as connection:
            await connection.execute(
                sqltext(
                    f"CREATE INDEX IF NOT EXISTS {quoted_index_name} "
                    f"ON {table_name} USING {selected_type} "
                    f"({vector_column} {operator_class}){index_options}"
                )
            )
            existing_indexes = (
                await connection.execute(
                    sqltext(
                        "SELECT indexname FROM pg_indexes "
                        "WHERE schemaname = current_schema() "
                        "AND tablename = :table_name"
                    ),
                    {"table_name": self._table_name(collection_name)},
                )
            ).scalars().all()
            for existing_name in existing_indexes:
                if existing_name.startswith(name_prefix) and existing_name != index_name:
                    await connection.execute(
                        sqltext(
                            f"DROP INDEX {preparer.quote(existing_name)}"
                        )
                    )

        self.logger.info(
            "Ensured %s vector index for collection %s.",
            selected_type,
            collection_name,
        )
        return True

    async def upsert_vector(
        self,
        collection_name: str,
        text: str,
        vector: list[float],
        metadata: dict | None = None,
        record_id: str | int | None = None,
        chunk_id: int | None = None,
    ) -> bool:
        return await self.upsert_vectors(
            collection_name=collection_name,
            text_list=[text],
            vectors=[vector],
            metadata=[metadata],
            record_ids=[record_id],
            chunk_ids=[chunk_id],
        )

    async def upsert_vectors(
        self,
        collection_name: str,
        text_list: list[str],
        vectors: list[list[float]],
        metadata: list[dict | None] | None = None,
        record_ids: list[str | int | None] | None = None,
        batch_size: int = 50,
        chunk_ids: list[int | None] | None = None,
    ) -> bool:
        if len(text_list) != len(vectors):
            raise ValueError("Text and vector counts must match.")
        if metadata is None:
            metadata = [None] * len(text_list)
        if record_ids is None:
            record_ids = [None] * len(text_list)
        if len(metadata) != len(text_list) or len(record_ids) != len(text_list):
            raise ValueError("Text, metadata, and record ID counts must match.")
        if chunk_ids is None or len(chunk_ids) != len(text_list):
            raise ValueError("A database chunk ID is required for every vector.")
        if any(chunk_id is None for chunk_id in chunk_ids):
            raise ValueError("Database chunk IDs must not be None.")
        if batch_size <= 0:
            raise ValueError("Batch size must be greater than zero.")
        if not await self.collection_exists(collection_name):
            self.logger.error(
                "Cannot insert records into non-existent collection: %s",
                collection_name,
            )
            return False
        if not text_list:
            return True

        table_name = self._quoted_table_name(collection_name)
        id_column = PGVectorSchemaEnums.ID.value
        chunk_id_column = PGVectorSchemaEnums.CHUNK_ID.value
        vector_column = PGVectorSchemaEnums.VECTOR.value
        text_column = PGVectorSchemaEnums.TEXT.value
        metadata_column = PGVectorSchemaEnums.METADATA.value
        engine = self._require_engine()
        statement = sqltext(
            f"INSERT INTO {table_name} "
            f'("{id_column}", "{chunk_id_column}", "{vector_column}", '
            f'"{text_column}", "{metadata_column}") '
            "VALUES (:record_id, :chunk_id, CAST(:vector AS vector), :text, "
            "CAST(:metadata AS jsonb)) "
            f'ON CONFLICT ("{chunk_id_column}") DO UPDATE SET '
            f'"{vector_column}" = EXCLUDED."{vector_column}", '
            f'"{text_column}" = EXCLUDED."{text_column}", '
            f'"{metadata_column}" = EXCLUDED."{metadata_column}"'
        )
        async with engine.begin() as connection:
            for start in range(0, len(text_list), batch_size):
                end = start + batch_size
                rows = [
                    {
                        "record_id": str(record_ids[index] or uuid4()),
                        "chunk_id": chunk_ids[index],
                        "vector": json.dumps(vectors[index]),
                        "text": text_list[index],
                        "metadata": json.dumps(metadata[index] or {}),
                    }
                    for index in range(start, min(end, len(text_list)))
                ]
                await connection.execute(statement, rows)
        return True

    async def search_by_embedding(
        self, collection_name: str, vector: list, limit: int = 5
    ) -> List[RetrievedDocument]:
        if limit <= 0:
            raise ValueError("Search limit must be greater than zero.")
        if not await self.collection_exists(collection_name):
            raise ValueError(f"Collection does not exist: {collection_name}")

        operator = (
            "<=>"
            if self.distance_method == DistanceMethodEnums.COSINE.value
            else "<#>"
        )
        table_name = self._quoted_table_name(collection_name)
        vector_column = PGVectorSchemaEnums.VECTOR.value
        text_column = PGVectorSchemaEnums.TEXT.value
        engine = self._require_engine()
        async with engine.connect() as connection:
            rows = await connection.execute(
                sqltext(
                    f'SELECT "{text_column}", "{PGVectorSchemaEnums.CHUNK_ID.value}", '
                    f'"{vector_column}" {operator} CAST(:vector AS vector) AS distance '
                    f'FROM {table_name} ORDER BY "{vector_column}" {operator} '
                    "CAST(:vector AS vector) LIMIT :limit"
                ),
                {"vector": json.dumps(vector), "limit": limit},
            )
            results = rows.fetchall()

        if not results:
            self.logger.warning(
                "No results found for the given vector in collection: %s",
                collection_name,
            )
            return []

        return [
            RetrievedDocument(
                text=row.text,
                chunk_id=row.chunk_id,
                score=(
                    1 - row.distance
                    if self.distance_method == DistanceMethodEnums.COSINE.value
                    else -row.distance
                ),
            )
            for row in results
        ]
