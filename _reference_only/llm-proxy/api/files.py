"""
File processing API endpoints for LLM Proxy Service

Handles file uploads, transcription, and processing.
"""

import logging
import os
import tempfile
import uuid
from typing import List

from fastapi import APIRouter, HTTPException, Request, File, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

files_router = APIRouter()


class TranscriptionResponse(BaseModel):
    """Response model for audio transcription."""
    success: bool
    transcription: str
    file_id: str
    file_name: str
    file_path: str


@files_router.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(request: Request, audio: UploadFile = File(...)):
    """Transcribe an audio file to text."""
    try:
        if not audio.filename:
            raise HTTPException(status_code=400, detail="No audio file provided")
        
        logger.info(f"Processing audio file: {audio.filename}, type: {audio.content_type}")
        
        # Create unique filename and save temporarily
        file_id = str(uuid.uuid4())
        filename = f"{file_id}_{audio.filename}"
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(audio.filename)[1]) as tmp_file:
            content = await audio.read()
            tmp_file.write(content)
            file_path = tmp_file.name
        
        # Convert audio to Opus format for better processing
        try:
            # Import audio conversion function
            import sys
            from pathlib import Path
            
            # Add parent directory to path for imports
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent.parent
            sys.path.insert(0, str(project_root))
            
            from mcp_tools.tools.whatsapp.audio import convert_to_opus_ogg_temp
            
            converted_path = convert_to_opus_ogg_temp(file_path)
            logger.info(f"Converted audio file to {converted_path}")
        except Exception as e:
            logger.warning(f"Could not convert audio, using original: {e}")
            converted_path = file_path
        
        # Transcribe the audio
        try:
            # Try faster_whisper first (preferred method)
            try:
                from faster_whisper import WhisperModel
                
                logger.info("Using local faster_whisper model for transcription")
                model = WhisperModel(
                    "medium", device="cuda", compute_type="float32"
                )
                
                # Transcribe with optimized settings
                segments, info = model.transcribe(
                    converted_path,
                    beam_size=10,
                    language="en",  # Force English
                    condition_on_previous_text=False,
                )
                
                # Combine segments
                text = "".join(segment.text for segment in segments)
                
                logger.info(f"Transcribed audio using faster_whisper: {text[:50]}...")
                
            except ImportError:
                # Fallback to speech_recognition
                try:
                    import speech_recognition as sr
                    
                    logger.info("Using speech_recognition for transcription")
                    recognizer = sr.Recognizer()
                    with sr.AudioFile(converted_path) as source:
                        audio_data = recognizer.record(source)
                        text = recognizer.recognize_google(audio_data)
                    
                    logger.info(f"Transcribed audio using Google Speech Recognition: {text[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Local transcription failed: {e}")
                    text = "[Audio transcription failed. Please install faster_whisper or speech_recognition]"
                    
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            text = "[Audio transcription failed]"
        
        # Clean up temporary files
        try:
            os.unlink(file_path)
            if converted_path != file_path:
                os.unlink(converted_path)
        except Exception as e:
            logger.warning(f"Could not clean up temporary files: {e}")
        
        return TranscriptionResponse(
            success=True,
            transcription=text,
            file_id=file_id,
            file_name=audio.filename,
            file_path=file_path
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to transcribe audio: {str(e)}")


@files_router.post("/process")
async def process_file(request: Request, file: UploadFile = File(...)):
    """Process a file and extract its content."""
    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        logger.info(f"Processing file: {file.filename}, type: {file.content_type}")
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            file_path = tmp_file.name
        
        # Process file using LLM service
        llm_service = request.app.state.llm_service
        result = await llm_service.process_file(
            file_path,
            file.filename,
            file.content_type
        )
        
        # Clean up temporary file
        try:
            os.unlink(file_path)
        except Exception as e:
            logger.warning(f"Could not clean up temporary file: {e}")
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")