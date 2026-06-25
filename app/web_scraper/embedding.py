# app/web_scraper/embedding.py

import math
import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

from app.web_scraper.embedding_config import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL_NAME,
    HF_EMBEDDING_API_URL,
)

load_dotenv()


HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")

if not HUGGINGFACE_API_KEY:
    raise RuntimeError("HUGGINGFACE_API_KEY is missing from .env")


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vector))

    if norm == 0:
        return vector

    return [x / norm for x in vector]


def _mean_pool_token_embeddings(token_embeddings: list[list[float]]) -> list[float]:
    """
    Some HF feature-extraction responses may return token-level embeddings:
        [
            [0.1, 0.2, ...],
            [0.3, 0.4, ...],
        ]

    This converts token embeddings into one sentence embedding by mean pooling.
    """

    if not token_embeddings:
        raise ValueError("Empty token embedding response from Hugging Face.")

    dimension = len(token_embeddings[0])

    pooled = []

    for dim_index in range(dimension):
        dim_values = [token[dim_index] for token in token_embeddings]
        pooled.append(sum(dim_values) / len(dim_values))

    return pooled


def _parse_hf_embedding_response(data: Any) -> list[float]:
    """
    Handles possible Hugging Face response shapes.

    Expected final result:
        [float, float, float, ...]  length = 384
    """

    if not isinstance(data, list):
        raise ValueError(f"Unexpected HF response type: {type(data)}")

    # Case 1:
    # [0.1, 0.2, 0.3, ...]
    if data and isinstance(data[0], (int, float)):
        return [float(x) for x in data]

    # Case 2:
    # [[0.1, 0.2, 0.3, ...]]
    if (
        data
        and isinstance(data[0], list)
        and data[0]
        and isinstance(data[0][0], (int, float))
    ):
        # If it is already one vector wrapped inside a list
        if len(data) == 1 and len(data[0]) == EMBEDDING_DIMENSION:
            return [float(x) for x in data[0]]

        # If it is token embeddings, mean-pool them
        pooled = _mean_pool_token_embeddings(data)
        return [float(x) for x in pooled]

    # Case 3:
    # [[[0.1, 0.2, ...], [0.3, 0.4, ...]]]
    if (
        data
        and isinstance(data[0], list)
        and data[0]
        and isinstance(data[0][0], list)
    ):
        pooled = _mean_pool_token_embeddings(data[0])
        return [float(x) for x in pooled]

    raise ValueError(f"Could not parse HF embedding response: {data}")


def create_embedding(text: str, max_retries: int = 3) -> list[float]:
    """
    Create embedding from full post_content using Hugging Face API.

    No local model.
    No sentence-transformers.
    No torch.
    No GPU/CPU model loading.

    post_content format:
        RAW NEWS:
        ...

        AI_ENRICHED_CONTEXT:
        ...
    """

    text = (text or "").strip()

    if not text:
        raise ValueError("Cannot create embedding from empty text.")

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": text,
        "options": {
            "wait_for_model": True,
        },
    }

    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            response = requests.post(
                HF_EMBEDDING_API_URL,
                headers=headers,
                json=payload,
                timeout=60,
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Hugging Face embedding API failed. "
                    f"Status: {response.status_code}, Response: {response.text}"
                )

            data = response.json()

            embedding = _parse_hf_embedding_response(data)

            if len(embedding) != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Embedding dimension mismatch for {EMBEDDING_MODEL_NAME}. "
                    f"Expected {EMBEDDING_DIMENSION}, got {len(embedding)}"
                )

            return _normalize_vector(embedding)

        except Exception as e:
            last_error = e
            wait_time = 2 * (attempt + 1)
            print(f"    ⚠️ HF embedding failed, retrying in {wait_time}s: {e}")
            time.sleep(wait_time)

    raise RuntimeError(f"Failed to create Hugging Face embedding: {last_error}")