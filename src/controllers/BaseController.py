from ..helpers.config import Settings, get_settings
import os
import random
import string


class BaseController:
    def __init__(self):

        self.app_settings = get_settings()

        self.base_dir = os.path.dirname(os.path.dirname(__file__))
        self.files_dir = os.path.join(self.base_dir, "assets/uploaded_files")
        self.vector_db_dir = os.path.join(self.base_dir, "assets/vector_db")

    def generate_key(self, length: int = 12):
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def get_vector_db_path(self, db_name: str):
        vector_db_path = os.path.join(self.vector_db_dir, db_name)
        if not vector_db_path:
            os.makedirs(vector_db_path, exist_ok=True)
        return vector_db_path
