from qdrant_client import models, QdrantClient
from VectorDBInterface import VectorDBInterface
from enums.VectorDBEnums import VectorDBEnums, DistanceMethodEnums
import logging
from typing import List

class QdrantDB(VectorDBInterface):
    def __init__(self, db_path: str, distance_method: str):
        self.client = None
        self.db_path = None
        self.distance_method = None

        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        self.distance_method = models.Distance.DOT

        self.logger = logging.getLogger(__name__)

    def connet(self):
        self.client = QdrantClient(path=self.db_path)
        self.logger.info(f"Connected to Qdrant at {self.db_path}")

    
    def disconnet(self):
        self.client = None
        self.logger.info(f"Disconnected from Qdrant at {self.db_path}")
    
    
    def is_collection_exist(self, collection_name: str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)

    
    def list_all_collections(self) -> List:
        return self.client.get_collection()
    

    
    def get_collection_info(self, collection_name: str) -> dict:
        return self.client.get_collection(collection_name=collection_name)

    
    def delete_collection(self, collection_name: str):
        if self.is_collection_exist(collection_name=collection_name):
            self.client.delete_collection(collection_name=collection_name)

    
    def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):
        if do_reset:
            self.delete_collection(collection_name=collection_name)

        if not self.is_collection_exist(collection_name=collection_name):
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(
                    size=embedding_size, 
                    distance=self.distance_method
                ),
            )
            self.logger.info(f"Collection {collection_name} created.")
            return True
        return False
    
    
    def insert_vector(self, collection_name: str, text: str, vector: list, metadata: dict = None, record_id: str = None):
        if not self.is_collection_exist(collection_name=collection_name):
            self.logger.error(f"Cannot Insert new record to non-exist collection: {collection_name}")
            return False

        try:
            self.client.upload_collection(
                collection_name=collection_name,
                vectors=[models.Record(vector=vector, payload={"text": text, "metadate": metadata})]
            )
        except Exception as e:
            self.logger.error(f"Error inserting batch: {e}")
            raise e
        return True

    
    def insert_many_vectors(self, collection_name: str, text_list: list, vectors: list, metadata: list = None, record_ids: list = None, batch_size: int = 50):
        if metadata is None:
            metadata = [None] * len(text_list)

        if record_ids is None:
            record_ids = [None] * len(text_list)

        for i in range (0, len(text_list), batch_size):
            batch_end = i + batch_size
            batch_text = text_list[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]

            batch_records = [models.Record(vector=batch_vectors[x], payload={"text": batch_text[x], "metadate": batch_metadata[x]}) for x in range(len(batch_text))]

            try:
                self.client.upload_collection(
                            collection_name=collection_name,
                            vectors=batch_records
                        )
            except Exception as e:
                self.logger.error(f"Error inserting batch: {e}")
                raise e
            
        return True

    
    def search_by_vector(self, collection_name: str, vector: list, limit: int):
        return self.client.search_matrix_pairs(
            collection_name=collection_name,
            query_vector=vector,
            limit=limit,
            with_payload=True
        )
    