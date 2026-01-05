"""
LLM service for OpenAI API calls
"""
import os
import sys
from pathlib import Path
from typing import List, Tuple, Optional
from openai import OpenAI

# Add project root to path to import prompts
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

try:
    from src.prompt import TRANSCRIPT_WRITER_PROMPT, TRANSCRIPT_REWRITER_PROMPT
except ImportError:
    # Fallback if import fails
    TRANSCRIPT_WRITER_PROMPT = ""
    TRANSCRIPT_REWRITER_PROMPT = ""

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class LLMService:
    """Service for interacting with OpenAI LLM"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set in environment variables")
        # Initialize client - workaround for httpx 0.28+ compatibility
        # httpx 0.28+ removed 'proxies' parameter, but OpenAI SDK may try to use it
        try:
            # Try standard initialization first
            self.client = OpenAI(api_key=api_key)
        except (TypeError, AttributeError) as e:
            # If that fails, create a custom httpx client
            import httpx
            # Create client with explicit configuration (no proxies)
            http_client = httpx.Client(
                timeout=httpx.Timeout(60.0),
                follow_redirects=True
            )
            self.client = OpenAI(
                api_key=api_key,
                http_client=http_client
            )
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o")
    
    def generate_initial_transcript(self, text_content: str) -> str:
        """
        Generate initial podcast transcript from text content
        
        Args:
            text_content: Input text content
            
        Returns:
            Initial transcript as string
        """
        prompt = f"{TRANSCRIPT_WRITER_PROMPT}\n\nContent to convert:\n{text_content}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a world-class podcast writer."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,
                max_tokens=4000
            )
            
            transcript = response.choices[0].message.content.strip()
            return transcript
            
        except Exception as e:
            raise Exception(f"Failed to generate initial transcript: {str(e)}")
    
    def optimize_transcript(self, initial_transcript: str) -> List[Tuple[str, str]]:
        """
        Optimize transcript for TTS pipeline
        
        Args:
            initial_transcript: Initial transcript text
            
        Returns:
            List of tuples: [("Speaker 1", "text"), ("Speaker 2", "text"), ...]
        """
        prompt = f"{TRANSCRIPT_REWRITER_PROMPT}\n\nTranscript to optimize:\n{initial_transcript}"
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an international oscar winning screenwriter."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=4000
            )
            
            optimized_text = response.choices[0].message.content.strip()
            
            # Parse the response - should be a Python list of tuples
            # Extract the list from the response
            try:
                # Try to find the list in the response
                start_idx = optimized_text.find('[')
                end_idx = optimized_text.rfind(']') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    list_str = optimized_text[start_idx:end_idx]
                    transcript = eval(list_str)
                    
                    # Validate format
                    if isinstance(transcript, list) and all(
                        isinstance(item, tuple) and len(item) == 2 
                        for item in transcript
                    ):
                        return transcript
                    else:
                        raise ValueError("Invalid transcript format")
                else:
                    raise ValueError("Could not find list in response")
                    
            except Exception as parse_error:
                raise Exception(f"Failed to parse optimized transcript: {str(parse_error)}")
            
        except Exception as e:
            raise Exception(f"Failed to optimize transcript: {str(e)}")


# Singleton instance
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """Get or create LLM service instance"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service

