"""Embeddings generation and similarity search for ad copy."""

import logging
from typing import Optional

import numpy as np
from openai import OpenAI
from sklearn.metrics.pairwise import cosine_similarity

from app.config import get_settings
from app.models import Ad

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingsService:
    """Service for generating and comparing ad copy embeddings."""

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.embedding_model = "text-embedding-3-small"
        self.embedding_dimensions = 1536

    def extract_ad_text(self, ad: Ad) -> str:
        """Extract meaningful text from ad for embedding."""
        text_parts = []

        if ad.headlines:
            headlines = [h.get("text", "") for h in ad.headlines if isinstance(h, dict)]
            text_parts.append(" | ".join(headlines[:5]))  # First 5 headlines

        if ad.descriptions:
            descriptions = [d.get("text", "") for d in ad.descriptions if isinstance(d, dict)]
            text_parts.append(" ".join(descriptions[:2]))  # First 2 descriptions

        text = " ".join(text_parts).strip()
        return text if text else "Empty ad"

    def generate_embedding(self, text: str) -> Optional[np.ndarray]:
        """Generate embedding vector for text using OpenAI."""
        try:
            response = self.client.embeddings.create(
                input=text, model=self.embedding_model
            )
            embedding = np.array(response.data[0].embedding)
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def generate_embeddings_batch(self, texts: list[str]) -> list[Optional[np.ndarray]]:
        """Generate embeddings for multiple texts in batch."""
        try:
            response = self.client.embeddings.create(
                input=texts, model=self.embedding_model
            )
            embeddings = [np.array(data.embedding) for data in response.data]
            return embeddings
        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {e}")
            return [None] * len(texts)

    def compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        similarity = cosine_similarity(
            embedding1.reshape(1, -1), embedding2.reshape(1, -1)
        )[0][0]
        return float(similarity)

    def find_most_similar(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: list[np.ndarray],
        top_k: int = 5,
    ) -> list[tuple[int, float]]:
        """
        Find top-k most similar embeddings to query.

        Returns list of (index, similarity_score) tuples.
        """
        if not candidate_embeddings:
            return []

        # Stack embeddings into matrix
        candidates_matrix = np.vstack(candidate_embeddings)
        query_matrix = query_embedding.reshape(1, -1)

        # Compute all similarities at once
        similarities = cosine_similarity(query_matrix, candidates_matrix)[0]

        # Get top-k indices
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = [(int(idx), float(similarities[idx])) for idx in top_indices]
        return results


def embed_best_ads(ads: list[Ad]) -> tuple[list[Ad], list[np.ndarray]]:
    """
    Generate embeddings for a list of best-performing ads.

    Returns (ads, embeddings) with same length, filtering out any failures.
    """
    service = EmbeddingsService()

    texts = [service.extract_ad_text(ad) for ad in ads]
    embeddings = service.generate_embeddings_batch(texts)

    # Filter out failed embeddings
    valid_ads = []
    valid_embeddings = []

    for ad, emb in zip(ads, embeddings):
        if emb is not None:
            valid_ads.append(ad)
            valid_embeddings.append(emb)
        else:
            logger.warning(f"Skipping ad {ad.id} due to embedding failure")

    logger.info(f"Generated embeddings for {len(valid_ads)}/{len(ads)} best ads")
    return valid_ads, valid_embeddings


def retrieve_exemplars_for_ad(
    target_ad: Ad, best_ads: list[Ad], best_embeddings: list[np.ndarray], top_k: int = 5
) -> list[tuple[Ad, float]]:
    """
    Retrieve top-k most similar best-performing ads as exemplars.

    Returns list of (ad, similarity_score) tuples.
    """
    service = EmbeddingsService()

    # Generate embedding for target ad
    target_text = service.extract_ad_text(target_ad)
    target_embedding = service.generate_embedding(target_text)

    if target_embedding is None:
        logger.error(f"Failed to generate embedding for target ad {target_ad.id}")
        return []

    # Find most similar
    similar_indices = service.find_most_similar(
        target_embedding, best_embeddings, top_k=top_k
    )

    exemplars = [(best_ads[idx], score) for idx, score in similar_indices]

    logger.info(
        f"Retrieved {len(exemplars)} exemplars for ad {target_ad.id}, "
        f"similarity scores: {[f'{s:.3f}' for _, s in exemplars]}"
    )

    return exemplars
