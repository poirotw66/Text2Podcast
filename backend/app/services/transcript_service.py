"""
Transcript generation service
Handles two-step process: initial generation and optimization
"""
from typing import List, Tuple
from app.services.llm_service import get_llm_service


class TranscriptService:
    """Service for generating and optimizing podcast transcripts"""
    
    def __init__(self):
        """Initialize transcript service"""
        self.llm_service = get_llm_service()
    
    def generate_transcript(self, text_content: str) -> List[Tuple[str, str]]:
        """
        Generate optimized transcript from text content (two-step process)
        
        Args:
            text_content: Input text content
            
        Returns:
            List of tuples: [("Speaker 1", "text"), ("Speaker 2", "text"), ...]
        """
        # Step 1: Generate initial transcript
        initial_transcript = self.llm_service.generate_initial_transcript(text_content)
        
        # Step 2: Optimize transcript for TTS
        optimized_transcript = self.llm_service.optimize_transcript(initial_transcript)
        
        return optimized_transcript


# Singleton instance
_transcript_service = None


def get_transcript_service() -> TranscriptService:
    """Get or create transcript service instance"""
    global _transcript_service
    if _transcript_service is None:
        _transcript_service = TranscriptService()
    return _transcript_service

