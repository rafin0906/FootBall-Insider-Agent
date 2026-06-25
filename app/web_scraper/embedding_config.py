# app/web_scraper/embedding_config.py

EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# all-MiniLM-L6-v2 output dimension
EMBEDDING_DIMENSION = 384

HF_EMBEDDING_API_URL = (
    f"https://router.huggingface.co/hf-inference/models/"
    f"{EMBEDDING_MODEL_NAME}/pipeline/feature-extraction"
)