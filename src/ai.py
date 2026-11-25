"""
AI module using Ollama for music-related text generation.

Uses qwen2.5:0.5b - a tiny but capable model optimized for 2GB RAM.
"""

import asyncio
import logging
import time

import ollama

import config

logger = logging.getLogger(__name__)

# Initialize Ollama async client with centralized host and timeout
client = ollama.AsyncClient(host=config.OLLAMA_HOST, timeout=config.OLLAMA_TIMEOUT)

# Match OLLAMA_NUM_PARALLEL=1 in the 2 GB container to prevent OOM / connection pile-ups
OLLAMA_SEMAPHORE = asyncio.Semaphore(config.OLLAMA_MAX_CONCURRENT)

_MODEL_READY = False
_LAST_MODEL_CHECK = 0.0
_MODEL_CHECK_COOLDOWN = 60.0


async def ensure_model_exists() -> bool:
    """Pull the model if it doesn't exist. Returns True if ready."""
    global _MODEL_READY, _LAST_MODEL_CHECK
    model_name = config.OLLAMA_MODEL
    try:
        models = await asyncio.wait_for(client.list(), timeout=config.OLLAMA_TIMEOUT)
        model_names = [m.model for m in models.models] if models.models else []
        if model_name not in model_names and f"{model_name}:latest" not in model_names:
            logger.info(f"Pulling model {model_name}...")
            await client.pull(model_name)
            logger.info(f"Model {model_name} pulled successfully")
        _MODEL_READY = True
        return True
    except Exception as e:
        _MODEL_READY = False
        logger.error(f"Failed to ensure model exists: {e}")
        return False
    finally:
        _LAST_MODEL_CHECK = time.time()


async def _model_available() -> bool:
    """Check model readiness, retrying lazily at most once per cooldown period."""
    if _MODEL_READY:
        return True
    if time.time() - _LAST_MODEL_CHECK >= _MODEL_CHECK_COOLDOWN:
        return await ensure_model_exists()
    return False


async def _generate_text(prompt: str, options: dict) -> str:
    """Run a bounded, timeout-guarded Ollama generation and reset readiness on error."""
    global _MODEL_READY
    async with OLLAMA_SEMAPHORE:
        try:
            response = await asyncio.wait_for(
                client.generate(
                    model=config.OLLAMA_MODEL,
                    prompt=prompt,
                    options=options,
                ),
                timeout=config.OLLAMA_TIMEOUT,
            )
            return response.response.strip()
        except Exception:
            _MODEL_READY = False
            raise


async def generate_vibe(
    recent_tracks: list[str], current_track: str | None = None
) -> str:
    """Generate a vibe/mood description based on recent listening."""
    if not await _model_available():
        return "AI is temporarily unavailable. Please try again later."

    tracks_text = "\n".join(f"- {track}" for track in recent_tracks[:10])
    current = f"Currently playing: {current_track}\n" if current_track else ""

    prompt = f"""You are a music mood analyst. Based on these recently played songs, describe the listener's current vibe/mood in 2-3 sentences. Be creative, use emojis, and capture the emotional atmosphere.

{current}Recent tracks:
{tracks_text}

Describe the vibe:"""

    try:
        return await _generate_text(
            prompt=prompt,
            options={"temperature": 0.8, "num_predict": 80, "num_ctx": 1024},
        )
    except Exception as e:
        logger.error(f"Vibe generation failed: {e}")
        return "Couldn't analyze your vibe right now. Try again later!"


async def generate_roast(top_artists: list[str], top_tracks: list[str]) -> str:
    """Generate a humorous roast of the user's music taste."""
    if not await _model_available():
        return "AI is temporarily unavailable. Please try again later."

    artists_text = ", ".join(top_artists[:10])
    tracks_text = ", ".join(top_tracks[:5])

    prompt = f"""You are a witty music critic. Roast this person's music taste in a funny but not mean way. Keep it to 2-3 sentences max. Use emojis.

Top artists: {artists_text}
Top tracks: {tracks_text}

Your roast:"""

    try:
        return await _generate_text(
            prompt=prompt,
            options={"temperature": 0.9, "num_predict": 80, "num_ctx": 1024},
        )
    except Exception as e:
        logger.error(f"Roast generation failed: {e}")
        return "My roasting circuits are fried. Try again later! 🔥"


async def generate_recommendations(top_artists: list[str]) -> str:
    """Generate music recommendations based on top artists."""
    if not await _model_available():
        return "AI is temporarily unavailable. Please try again later."

    artists_text = ", ".join(top_artists[:10])

    prompt = f"""Based on these favorite artists, recommend 5 similar artists they might not know. Format as a simple list with brief reasons.

Favorite artists: {artists_text}

Recommendations:"""

    try:
        return await _generate_text(
            prompt=prompt,
            options={"temperature": 0.7, "num_predict": 120, "num_ctx": 1024},
        )
    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}")
        return "Couldn't generate recommendations right now. Try again later!"
