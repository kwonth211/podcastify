"""
Content Extractor Module

This module provides functionality to extract content from various sources including
websites, YouTube videos, and PDF files. It serves as a central hub for content
extraction, delegating to specialized extractors based on the source type.
"""

import logging
import re
from typing import List, Union, Optional, Tuple
from urllib.parse import urlparse
from .youtube_transcriber import YouTubeTranscriber
from .website_extractor import WebsiteExtractor
from .pdf_extractor import PDFExtractor
from podcastfy.utils.config import load_config

logger = logging.getLogger(__name__)

class ContentExtractor:
	def __init__(self):
		"""
		Initialize the ContentExtractor.
		"""
		self.youtube_transcriber = YouTubeTranscriber()
		self.website_extractor = WebsiteExtractor()
		self.pdf_extractor = PDFExtractor()
		self.config = load_config()
		self.content_extractor_config = self.config.get('content_extractor', {})

	def is_url(self, source: str) -> bool:
		"""
		Check if the given source is a valid URL.

		Args:
			source (str): The source to check.

		Returns:
			bool: True if the source is a valid URL, False otherwise.
		"""
		try:
			# If the source doesn't start with a scheme, add 'https://'
			if not source.startswith(('http://', 'https://')):
				source = 'https://' + source

			result = urlparse(source)
			return all([result.scheme, result.netloc])
		except ValueError:
			return False

	def extract_content(self, source: str) -> str:
		"""
		Extract content from various sources.

		Args:
			source (str): URL or file path of the content source.

		Returns:
			str: Extracted text content.

		Raises:
			ValueError: If the source type is unsupported.
		"""
		try:
			if source.lower().endswith('.pdf'):
				return self.pdf_extractor.extract_content(source)
			elif self.is_url(source):
				if any(pattern in source for pattern in self.content_extractor_config['youtube_url_patterns']):
					return self.youtube_transcriber.extract_transcript(source)
				else:
					return self.website_extractor.extract_content(source)
			else:
				raise ValueError("Unsupported source type")
		except Exception as e:
			logger.error(f"Error extracting content from {source}: {str(e)}")
			raise

	def extract_content_with_headline(self, source: str) -> Tuple[str, Optional[str]]:
		"""
		Extract content and headline from various sources.

		Args:
			source (str): URL or file path of the content source.

		Returns:
			Tuple[str, Optional[str]]: A tuple of (extracted text content, headline).
				Headline is None for PDFs or if extraction fails.

		Raises:
			ValueError: If the source type is unsupported.
		"""
		try:
			content = self.extract_content(source)
			headline = None
			
			if self.is_url(source) and not any(pattern in source for pattern in self.content_extractor_config['youtube_url_patterns']):
				# Try to extract headline for website URLs
				headline = self.website_extractor.extract_headline(source)
			
			return (content, headline)
		except Exception as e:
			logger.error(f"Error extracting content with headline from {source}: {str(e)}")
			raise
	
	def generate_topic_content(self, topic: str) -> tuple:
		"""
		Generate content based on a given topic using a generative model.

		Args:
			topic (str): The topic to generate content for.

		Returns:
			tuple: (content, sources) where sources is a list of dicts with url and title
		"""
		try:
			import os
			from google import genai
			from google.genai import types
			
			api_key = os.environ.get("GEMINI_API_KEY")
			client = genai.Client(api_key=api_key)
			
			topic_prompt = f'Be detailed. Search for {topic}'
			response = client.models.generate_content(
				model='gemini-2.5-flash',
				contents=topic_prompt,
				config=types.GenerateContentConfig(
					tools=[types.Tool(google_search=types.GoogleSearch())]
				)
			)
			
			# Extract grounding sources from response
			sources = []
			try:
				if hasattr(response, 'candidates') and response.candidates:
					candidate = response.candidates[0]
					if hasattr(candidate, 'grounding_metadata') and candidate.grounding_metadata:
						grounding = candidate.grounding_metadata
						# Extract from grounding_chunks
						if hasattr(grounding, 'grounding_chunks') and grounding.grounding_chunks:
							for chunk in grounding.grounding_chunks:
								if hasattr(chunk, 'web') and chunk.web:
									source = {
										'url': getattr(chunk.web, 'uri', ''),
										'title': getattr(chunk.web, 'title', '')
									}
									if source['url'] and source not in sources:
										sources.append(source)
						# Also try grounding_supports
						if hasattr(grounding, 'grounding_supports') and grounding.grounding_supports:
							for support in grounding.grounding_supports:
								if hasattr(support, 'grounding_chunk_indices'):
									pass  # Already handled in grounding_chunks
						# Try search_entry_point for query info
						if hasattr(grounding, 'search_entry_point') and grounding.search_entry_point:
							logger.info(f"Search entry point: {grounding.search_entry_point}")
			except Exception as e:
				logger.warning(f"Could not extract grounding sources: {e}")
			
			return response.text, sources
		except Exception as e:
			logger.error(f"Error generating content for topic '{topic}': {str(e)}")
			raise
		

def main(seed: int = 42) -> None:
	"""
	Main function to test the ContentExtractor class.
	"""
	logging.basicConfig(level=logging.INFO)

	# Create an instance of ContentExtractor
	extractor = ContentExtractor()

	# Test sources
	test_sources: List[str] = [
		"www.souzatharsis.com",
		"https://www.youtube.com/watch?v=dQw4w9WgXcQ",
		"path/to/sample.pdf"
	]

	for source in test_sources:
		try:
			logger.info(f"Extracting content from: {source}")
			content = extractor.extract_content(source)

			# Print the first 500 characters of the extracted content
			logger.info(f"Extracted content (first 500 characters):\n{content[:500]}...")

			# Print the total length of the extracted content
			logger.info(f"Total length of extracted content: {len(content)} characters")
			logger.info("-" * 50)

		except Exception as e:
			logger.error(f"An error occurred while processing {source}: {str(e)}")

if __name__ == "__main__":
	main()
