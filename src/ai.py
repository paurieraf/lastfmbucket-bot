"""
AI module using Ollama for music-related text generation.

Uses qwen2.5:0.5b - a tiny but capable model optimized for 2GB RAM.
"""

import logging
import os

import ollama

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
MODEL_NAME = "qwen2.5:0.5b"

# Initialize Ollama client
client = ollama.Client(host=OLLAMA_HOST)


def ensure_model_exists() -> bool:
    """Pull the model if it doesn't exist. Returns True if ready."""
    try:
        models = client.list()
        model_names = [m.model for m in models.models] if models.models else []
        if MODEL_NAME not in model_names and f"{MODEL_NAME}:latest" not in model_names:
            logger.info(f"Pulling model {MODEL_NAME}...")
            client.pull(MODEL_NAME)
            logger.info(f"Model {MODEL_NAME} pulled successfully")
        return True
    except Exception as e:
        logger.error(f"Failed to ensure model exists: {e}")
        return False


def generate_vibe(recent_tracks: list[str], current_track: str | None = None) -> str:
    """Generate a vibe/mood description based on recent listening."""
    if not ensure_model_exists():
        return "AI is temporarily unavailable. Please try again later."

    tracks_text = "\n".join(f"- {track}" for track in recent_tracks[:10])
    current = f"Currently playing: {current_track}\n" if current_track else ""

    prompt = f"""You are a music mood analyst. Based on these recently played songs, describe the listener's current vibe/mood in 2-3 sentences. Be creative, use emojis, and capture the emotional atmosphere.

{current}Recent tracks:
{tracks_text}

Describe the vibe:"""

    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=prompt,
            options={"temperature": 0.8, "num_predict": 100},
        )
        return response.response.strip()
    except Exception as e:
        logger.error(f"Vibe generation failed: {e}")
        return "Couldn't analyze your vibe right now. Try again later!"


def generate_roast(top_artists: list[str], top_tracks: list[str]) -> str:
    """Generate a humorous roast of the user's music taste."""
    if not ensure_model_exists():
        return "AI is temporarily unavailable. Please try again later."

    artists_text = ", ".join(top_artists[:10])
    tracks_text = ", ".join(top_tracks[:5])

    prompt = f"""You are a witty music critic. Roast this person's music taste in a funny but not mean way. Keep it to 2-3 sentences max. Use emojis.

Top artists: {artists_text}
Top tracks: {tracks_text}

Your roast:"""

    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=prompt,
            options={"temperature": 0.9, "num_predict": 120},
        )
        return response.response.strip()
    except Exception as e:
        logger.error(f"Roast generation failed: {e}")
        return "My roasting circuits are fried. Try again later! 🔥"


def generate_recommendations(top_artists: list[str]) -> str:
    """Generate music recommendations based on top artists."""
    if not ensure_model_exists():
        return "AI is temporarily unavailable. Please try again later."

    artists_text = ", ".join(top_artists[:10])

    prompt = f"""Based on these favorite artists, recommend 5 similar artists they might not know. Format as a simple list with brief reasons.

Favorite artists: {artists_text}

Recommendations:"""

    try:
        response = client.generate(
            model=MODEL_NAME,
            prompt=prompt,
            options={"temperature": 0.7, "num_predict": 150},
        )
        return response.response.strip()
    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        return "Couldn't generate recommendations right now. Try again later!"
