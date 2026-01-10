"""
Website Extractor Module

This module is responsible for extracting clean text content from websites using
requests and BeautifulSoup for parsing.
"""

import requests
import re
import html
import logging
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from podcastfy.utils.config import load_config
from typing import List, Optional

logger = logging.getLogger(__name__)

class WebsiteExtractor:
	def __init__(self):
		"""
		Initialize the WebsiteExtractor.
		"""
		self.config = load_config()
		self.website_extractor_config = self.config.get('website_extractor', {})
		self.unwanted_tags = self.website_extractor_config.get('unwanted_tags', [])
		self.user_agent = self.website_extractor_config.get('user_agent', 'Mozilla/5.0')
		self.timeout = self.website_extractor_config.get('timeout', 10)
		self.remove_patterns = self.website_extractor_config.get('markdown_cleaning', {}).get('remove_patterns', [])

	def extract_content(self, url: str) -> str:
		"""
		Extract clean text content from a website using BeautifulSoup.

		Args:
			url (str): Website URL.

		Returns:
			str: Extracted clean text content.

		Raises:
			Exception: If there's an error in extracting the content.
		"""
		try:
			normalized_url = self.normalize_url(url)
			html_content = self.fetch_url(normalized_url)
			soup = BeautifulSoup(html_content, 'html.parser')
			self.remove_unwanted_elements(soup)
			raw_text = soup.get_text(separator="\n")
			cleaned_content = self.clean_content(raw_text)
			return cleaned_content
		except requests.RequestException as e:
			logger.error(f"Failed to extract content from {url}: {str(e)}")
			raise Exception(f"Failed to extract content from {url}: {str(e)}")
		except Exception as e:
			logger.error(f"An unexpected error occurred while extracting content from {url}: {str(e)}")
			raise Exception(f"An unexpected error occurred while extracting content from {url}: {str(e)}")

	def extract_headline(self, url: str) -> Optional[str]:
		"""
		Extract headline/title from a website.

		Args:
			url (str): Website URL.

		Returns:
			Optional[str]: Extracted headline, or None if not found.
		"""
		try:
			normalized_url = self.normalize_url(url)
			html_content = self.fetch_url(normalized_url)
			soup = BeautifulSoup(html_content, 'html.parser')

			# 1. Try <title> tag
			title_tag = soup.find('title')
			if title_tag and title_tag.get_text().strip():
				headline = title_tag.get_text().strip()
				headline = re.sub(r'\s*[-|]\s*.*$', '', headline)
				if len(headline) > 10:
					return headline

			# 2. Try <h1> tag
			h1_tag = soup.find('h1')
			if h1_tag and h1_tag.get_text().strip():
				headline = h1_tag.get_text().strip()
				if len(headline) > 10:
					return headline

			# 3. Try meta property="og:title"
			og_title = soup.find('meta', property='og:title')
			if og_title and og_title.get('content'):
				headline = og_title.get('content').strip()
				if len(headline) > 10:
					return headline

			# 4. Try meta name="title"
			meta_title = soup.find('meta', attrs={'name': 'title'})
			if meta_title and meta_title.get('content'):
				headline = meta_title.get('content').strip()
				if len(headline) > 10:
					return headline

			# 5. Try article header
			article_header = soup.find('article')
			if article_header:
				header_h1 = article_header.find('h1')
				if header_h1 and header_h1.get_text().strip():
					headline = header_h1.get_text().strip()
					if len(headline) > 10:
						return headline

			logger.warning(f"Could not extract headline from {url}")
			return None

		except Exception as e:
			logger.error(f"Error extracting headline from {url}: {str(e)}")
			return None

	def fetch_url(self, url: str) -> str:
		"""
		Fetch URL content using requests.

		Args:
			url (str): The URL to fetch.

		Returns:
			str: The page HTML content.
		"""
		headers = {
			'User-Agent': self.user_agent,
			'Accept-Language': 'en-US,en;q=0.9',
		}
		response = requests.get(url, headers=headers, timeout=self.timeout)
		return response.text

	def normalize_url(self, url: str) -> str:
		"""
		Normalize the given URL by adding scheme if missing.

		Args:
			url (str): The URL to normalize.

		Returns:
			str: The normalized URL.

		Raises:
			ValueError: If the URL is invalid after normalization attempts.
		"""
		if not url.startswith(('http://', 'https://')):
			url = 'https://' + url
		parsed = urlparse(url)
		if not all([parsed.scheme, parsed.netloc]):
			raise ValueError(f"Invalid URL: {url}")
		return parsed.geturl()

	def remove_unwanted_elements(self, soup: BeautifulSoup) -> None:
		"""
		Remove unwanted elements from the BeautifulSoup object.

		Args:
			soup (BeautifulSoup): The BeautifulSoup object to clean.
		"""
		for tag in self.unwanted_tags:
			for element in soup.find_all(tag):
				element.decompose()

	def clean_content(self, content: str) -> str:
		"""
		Clean the extracted content.

		Args:
			content (str): The content to clean.

		Returns:
			str: Cleaned text content.
		"""
		cleaned_content = html.unescape(content)
		cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
		cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)
		for pattern in self.remove_patterns:
			cleaned_content = re.sub(pattern, '', cleaned_content)
		return cleaned_content.strip()
