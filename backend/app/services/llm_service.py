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
            print(f"Error initializing OpenAI client: {e}")
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini-2024-07-18")
    
    def generate_initial_transcript(self, text_content: str, podcast_length_mode: str = "MEDIUM") -> str:
        """
        Generate initial podcast transcript from text content
        
        Args:
            text_content: Input text content
            podcast_length_mode: Podcast length mode (SHORT | MEDIUM | LONG)
            
        Returns:
            Initial transcript as string
        """
        # Replace {SHORT | MEDIUM | LONG} in prompt with actual mode
        prompt_template = TRANSCRIPT_WRITER_PROMPT.replace(
            "{SHORT | MEDIUM | LONG}", 
            podcast_length_mode.upper()
        )
        prompt = f"{prompt_template}\n\nContent to convert:\n{text_content}"
        
        # Calculate max_completion_tokens based on podcast length mode
        # Chinese characters typically require ~2 tokens per character
        # Add significant buffer to ensure we can reach target word count
        # Note: Need extra tokens for formatting, dialogue markers, and natural language overhead
        token_limits = {
            "SHORT": 5000,    # For 1,500-1,800 chars: ~3,000-3,600 tokens, buffer to 5000
            "MEDIUM": 12000,  # For 3,000-3,500 chars: ~6,000-7,000 tokens, buffer to 12000 (almost 2x)
            "LONG": 20000     # For 6,000-7,000 chars: ~12,000-14,000 tokens, buffer to 20000
        }
        max_tokens = token_limits.get(podcast_length_mode.upper(), 12000)
        
        try:
            # Build request parameters
            request_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a world-class podcast writer."},
                    {"role": "user", "content": prompt}
                ],
                "max_completion_tokens": max_tokens
            }
            
            # Only add temperature if model supports it (gpt-5-mini doesn't support custom temperature)
            if not self.model.startswith("gpt-5"):
                request_params["temperature"] = 0.8
            
            response = self.client.chat.completions.create(**request_params)
            
            transcript = response.choices[0].message.content.strip()
            
            # Check word count and retry if insufficient
            word_count = len(transcript)
            min_word_counts = {
                "SHORT": 1500,
                "MEDIUM": 3000,
                "LONG": 6000
            }
            min_words = min_word_counts.get(podcast_length_mode.upper(), 3000)
            
            # If word count is insufficient, try to extend the transcript
            if word_count < min_words:
                print(f"Warning: Generated transcript has {word_count} words, target is {min_words}. Attempting to extend...")
                
                # Create a continuation prompt
                continuation_prompt = f"""The previous transcript has only {word_count} words, but the target is {min_words} words for {podcast_length_mode.upper()} mode.

Please continue the conversation naturally. Add more:
- Detailed explanations and examples
- More interactions between speakers
- Additional questions and follow-ups
- More anecdotes and analogies
- Natural reactions and interruptions

Continue from where the transcript left off. Do NOT repeat what was already said. Just continue the conversation naturally until you reach at least {min_words} total words.

Previous transcript:
{transcript}

Continue the conversation:"""
                
                continuation_params = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "You are a world-class podcast writer."},
                        {"role": "user", "content": continuation_prompt}
                    ],
                    "max_completion_tokens": max_tokens // 2  # Use half tokens for continuation
                }
                
                if not self.model.startswith("gpt-5"):
                    continuation_params["temperature"] = 0.8
                
                try:
                    continuation_response = self.client.chat.completions.create(**continuation_params)
                    continuation = continuation_response.choices[0].message.content.strip()
                    
                    # Append continuation to original transcript
                    transcript = f"{transcript}\n\n{continuation}"
                    print(f"Extended transcript to {len(transcript)} words")
                except Exception as ext_error:
                    print(f"Warning: Failed to extend transcript: {ext_error}")
                    # Return original transcript even if short
            
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
        
        # Estimate required tokens based on input length
        # The optimized output may be similar or slightly longer than input
        # Chinese characters typically require ~2 tokens per character
        input_length = len(initial_transcript)
        estimated_output_tokens = int(input_length * 2.2)  # Add 10% buffer for markers and formatting
        
        # Set reasonable limits: minimum 4000, maximum 16000 (for LONG mode)
        max_tokens = max(4000, min(estimated_output_tokens, 16000))
        
        try:
            # Build request parameters
            request_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are an international oscar winning screenwriter."},
                    {"role": "user", "content": prompt}
                ],
                "max_completion_tokens": max_tokens
            }
            
            # Only add temperature if model supports it (gpt-5-mini doesn't support custom temperature)
            if not self.model.startswith("gpt-5"):
                request_params["temperature"] = 0.7
            
            response = self.client.chat.completions.create(**request_params)
            
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

