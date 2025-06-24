"""
Audio Service for Text-to-Speech using Kokoro FastAPI

Handles audio generation from text using the external Kokoro FastAPI service.
"""

import asyncio
import logging
import httpx
import base64
from typing import AsyncGenerator, Optional, Tuple, List
import re

logger = logging.getLogger(__name__)


class AudioServiceAPI:
    """Service for converting text to speech using Kokoro FastAPI."""

    def __init__(self, api_base: str = "http://kokoro-tts:8880", timeout: int = 30):
        """
        Initialize the audio service.

        Args:
            api_base: Base URL for the Kokoro API
            timeout: Request timeout in seconds
        """
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self._client = None
        self._initialized = False

    async def initialize(self):
        """Initialize the HTTP client."""
        if self._initialized:
            return

        try:
            self._client = httpx.AsyncClient(
                base_url=self.api_base, timeout=httpx.Timeout(self.timeout)
            )

            # Test connection
            response = await self._client.get("/v1/audio/voices")
            if response.status_code == 200:
                voices = response.json()
                logger.info(
                    "Audio service initialized. Available voices: %d", len(voices)
                )
                self._initialized = True
            else:
                raise httpx.HTTPStatusError(
                    f"Failed to connect to Kokoro API: {response.status_code}",
                    request=response.request,
                    response=response,
                )

        except Exception as e:
            logger.error("Failed to initialize audio service: %s", e)
            raise

    def _split_into_sentences(self, text: str) -> list[str]:
        """
        Split text into sentences for better audio generation.

        Args:
            text: Input text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting on common punctuation
        # Preserve the punctuation for natural speech
        sentences = re.split(r"(?<=[.!?])\s+", text)

        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]

        # If no sentences found, return the original text
        if not sentences:
            return [text] if text.strip() else []

        return sentences

    async def text_to_speech_stream(
        self,
        text: str,
        voice: str = "af_bella",
        speed: float = 1.25,
    ) -> AsyncGenerator[Tuple[bytes, int], None]:
        """
        Convert text to speech and yield audio chunks.

        Args:
            text: Text to convert to speech
            voice: Voice to use
            speed: Speech speed
            lang: Language code

        Yields:
            Tuples of (audio_data, sample_rate)
        """
        if not self._initialized:
            await self.initialize()

        if not text.strip():
            return

        try:
            # Split text into sentences for more natural streaming
            sentences = self._split_into_sentences(text)

            if self._client is None:
                logger.error("HTTP client is not initialized.")
                return

            for sentence in sentences:
                if not sentence.strip():
                    continue

                # Make API request for TTS
                response = await self._client.post(
                    "/v1/audio/speech",
                    json={
                        "model": "tts-1",
                        "input": sentence,
                        "voice": voice,
                        "response_format": "wav",
                        "speed": speed,
                    },
                )

                if response.status_code == 200:
                    # Get audio data
                    audio_data = response.content

                    # For WAV format, sample rate is typically 24000
                    # You might want to parse the WAV header to get the actual rate
                    sample_rate = 24000

                    yield (audio_data, sample_rate)
                else:
                    logger.error(
                        "TTS API error: %d - %s", response.status_code, response.text
                    )

        except httpx.HTTPError as e:
            logger.error("HTTP error in text-to-speech conversion: %s", e)
            # Continue without raising to allow graceful degradation
        except Exception as e:
            logger.error("Unexpected error in text-to-speech conversion: %s", e)
            # Continue without raising to allow graceful degradation

    async def generate_audio_for_streaming_text(
        self,
        text_stream: AsyncGenerator[str, None],
        voice: str = "af_bella",
        speed: float = 1.25,
    ) -> AsyncGenerator[Tuple[bytes, int, str], None]:
        """
        Generate audio for streaming text input.

        This method buffers text until complete sentences are formed,
        then generates audio for those sentences while continuing to
        receive more text.

        Args:
            text_stream: Async generator yielding text chunks
            voice: Voice to use
            speed: Speech speed

        Yields:
            Tuples of (audio_data, sample_rate, text_chunk)
        """
        if not self._initialized:
            await self.initialize()

        buffer = ""
        sentence_queue = asyncio.Queue()

        async def collect_sentences():
            """Collect sentences from the text stream."""
            nonlocal buffer

            async for chunk in text_stream:
                buffer += chunk

                # Check for complete sentences
                sentences = self._split_into_sentences(buffer)

                # If we have complete sentences, queue them
                if len(sentences) > 0:
                    # Check if the last "sentence" might be incomplete
                    if buffer.rstrip().endswith((".", "!", "?")):
                        # All sentences are complete
                        for sentence in sentences:
                            await sentence_queue.put(sentence)
                        buffer = ""
                    else:
                        # Last part might be incomplete
                        for sentence in sentences[:-1]:
                            await sentence_queue.put(sentence)
                        buffer = sentences[-1] if sentences else ""

            # Queue any remaining text
            if buffer.strip():
                await sentence_queue.put(buffer)

            # Signal completion
            await sentence_queue.put(None)

        # Start collecting sentences in background
        collect_task = asyncio.create_task(collect_sentences())

        try:
            while True:
                # Get next sentence
                sentence = await sentence_queue.get()

                # Check for completion
                if sentence is None:
                    break

                # Generate audio for this sentence
                async for audio_data, sample_rate in self.text_to_speech_stream(
                    sentence, voice, speed
                ):
                    yield (audio_data, sample_rate, sentence)

        finally:
            # Ensure collection task completes
            await collect_task

    def audio_to_base64(self, audio_data: bytes) -> str:
        """
        Convert audio data to base64-encoded string.

        Args:
            audio_data: Audio data (WAV format)

        Returns:
            Base64-encoded audio data
        """
        return base64.b64encode(audio_data).decode("utf-8")

    async def close(self):
        """Clean up resources."""
        if self._client:
            await self._client.aclose()
        self._initialized = False
