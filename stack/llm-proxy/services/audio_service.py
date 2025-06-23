"""
Audio Service for Text-to-Speech using Kokoro ONNX

Handles audio generation from text using the Kokoro TTS model.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional, Tuple, List
import numpy as np
from kokoro_onnx import Kokoro
import re
import os

logger = logging.getLogger(__name__)


class AudioService:
    """Service for converting text to speech using Kokoro ONNX."""
    
    def __init__(self, model_path: str = "/app/models/kokoro-v1.0.onnx", 
                 voices_path: str = "/app/models/voices-v1.0.bin",
                 use_gpu: bool = True):
        """
        Initialize the audio service.
        
        Args:
            model_path: Path to the Kokoro ONNX model
            voices_path: Path to the voices binary file
            use_gpu: Whether to attempt using GPU acceleration
        """
        self.model_path = model_path
        self.voices_path = voices_path
        self.use_gpu = use_gpu
        self._kokoro = None
        self._initialized = False
        self._providers = self._get_providers()
    
    def _get_providers(self) -> List[str]:
        """
        Get ONNX Runtime providers based on availability.
        
        Returns:
            List of providers to use in order of preference
        """
        providers = []
        
        if self.use_gpu:
            try:
                import onnxruntime as ort
                available_providers = ort.get_available_providers()
                
                # Check for CUDA provider
                if 'CUDAExecutionProvider' in available_providers:
                    providers.append('CUDAExecutionProvider')
                    logger.info("CUDA GPU acceleration available for Kokoro TTS")
                else:
                    logger.warning("CUDA not available, falling back to CPU for Kokoro TTS")
            except Exception as e:
                logger.warning(f"Error checking GPU availability: {e}")
        
        # Always add CPU provider as fallback
        providers.append('CPUExecutionProvider')
        
        return providers
        
    async def initialize(self):
        """Initialize the Kokoro model asynchronously."""
        if self._initialized:
            return
            
        try:
            # Initialize in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            # Log which providers we're using
            logger.info(f"Initializing Kokoro with providers: {self._providers}")
            
            # Create Kokoro instance (it will automatically detect GPU support)
            self._kokoro = await loop.run_in_executor(
                None, 
                lambda: Kokoro(
                    self.model_path, 
                    self.voices_path
                )
            )
            self._initialized = True
            
            # Log successful initialization
            using_gpu = 'CUDAExecutionProvider' in self._providers
            logger.info(f"Audio service initialized successfully (GPU: {using_gpu})")
            
        except Exception as e:
            logger.error(f"Failed to initialize audio service: {e}")
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
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Filter out empty sentences
        sentences = [s.strip() for s in sentences if s.strip()]
        
        # If no sentences found, return the original text
        if not sentences:
            return [text] if text.strip() else []
            
        return sentences
    
    async def text_to_speech_stream(
        self,
        text: str,
        voice: str = "af_nicole",
        speed: float = 1.0,
        lang: str = "en-us"
    ) -> AsyncGenerator[Tuple[np.ndarray, int], None]:
        """
        Convert text to speech and yield audio chunks.
        
        Args:
            text: Text to convert to speech
            voice: Voice to use (default: af_nicole)
            speed: Speech speed (default: 1.0)
            lang: Language code (default: en-us)
            
        Yields:
            Tuples of (audio_samples, sample_rate)
        """
        if not self._initialized:
            await self.initialize()
            
        if not text.strip():
            return
            
        try:
            # Split text into sentences for more natural streaming
            sentences = self._split_into_sentences(text)
            
            for sentence in sentences:
                if not sentence.strip():
                    continue
                    
                # Create stream for this sentence
                stream = self._kokoro.create_stream(
                    sentence,
                    voice=voice,
                    speed=speed,
                    lang=lang
                )
                
                # Yield audio chunks
                async for samples, sample_rate in stream:
                    yield (samples, sample_rate)
                    
        except Exception as e:
            logger.error(f"Error in text-to-speech conversion: {e}")
            # Continue without raising to allow graceful degradation
    
    async def generate_audio_for_streaming_text(
        self,
        text_stream: AsyncGenerator[str, None],
        voice: str = "af_nicole",
        speed: float = 1.0,
        lang: str = "en-us",
        sentence_buffer_size: int = 2
    ) -> AsyncGenerator[Tuple[np.ndarray, int, str], None]:
        """
        Generate audio for streaming text input.
        
        This method buffers text until complete sentences are formed,
        then generates audio for those sentences while continuing to
        receive more text.
        
        Args:
            text_stream: Async generator yielding text chunks
            voice: Voice to use
            speed: Speech speed
            lang: Language code
            sentence_buffer_size: Number of sentences to buffer before generating audio
            
        Yields:
            Tuples of (audio_samples, sample_rate, text_chunk)
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
                    if buffer.rstrip().endswith(('.', '!', '?')):
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
                async for samples, sample_rate in self.text_to_speech_stream(
                    sentence, voice, speed, lang
                ):
                    yield (samples, sample_rate, sentence)
                    
        finally:
            # Ensure collection task completes
            await collect_task
    
    def audio_to_base64(self, samples: np.ndarray, sample_rate: int) -> str:
        """
        Convert audio samples to base64-encoded WAV format.
        
        Args:
            samples: Audio samples as numpy array
            sample_rate: Sample rate of the audio
            
        Returns:
            Base64-encoded WAV data
        """
        import io
        import base64
        import wave
        
        # Convert float32 samples to int16
        samples_int16 = (samples * 32767).astype(np.int16)
        
        # Create WAV file in memory
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)   # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples_int16.tobytes())
        
        # Get WAV data and encode to base64
        buffer.seek(0)
        wav_data = buffer.read()
        return base64.b64encode(wav_data).decode('utf-8')
    
    async def close(self):
        """Clean up resources."""
        self._kokoro = None
        self._initialized = False