#  !/usr/bin/env python3
"""
Update daily_urls.txt with latest headlines from Naver News Economy section
Extracts links from elements with class "sa_item _SECTION_HEADLINE"
"""
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


def extract_headline_urls(url: str, max_urls: int = 5) -> Tuple[List[str], List[str]]:
    """
    Extract headline URLs and titles from Naver News section page.
    
    Args:
        url: The Naver News section URL
        max_urls: Maximum number of URLs to extract (default: 5)
    
    Returns:
        Tuple of (List of article URLs, List of headline titles)
    """
    urls = []
    titles = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                ignore_https_errors=True,
            )
            page = context.new_page()
            page.set_extra_http_headers({
                "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            })
            
            print(f"🌐 Fetching: {url}")
            page.goto(url, wait_until="networkidle", timeout=30000)
            # Wait a bit for dynamic content to load
            page.wait_for_timeout(2000)
            
            html_content = page.content()
            context.close()
            browser.close()
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all elements with class "sa_item _SECTION_HEADLINE"
            # Handle both string and list class attributes
            def has_headline_class(class_list):
                if not class_list:
                    return False
                if isinstance(class_list, str):
                    return 'sa_item' in class_list and '_SECTION_HEADLINE' in class_list
                if isinstance(class_list, list):
                    classes = ' '.join(class_list)
                    return 'sa_item' in classes and '_SECTION_HEADLINE' in classes
                return False
            
            headline_elements = soup.find_all(class_=has_headline_class)
            
            # Alternative: Try finding by both classes separately
            if not headline_elements:
                headline_elements = soup.find_all(class_='sa_item')
                headline_elements = [el for el in headline_elements if '_SECTION_HEADLINE' in ' '.join(el.get('class', []))]
            
            print(f"📰 Found {len(headline_elements)} headline elements")
            
            # Extract links and titles from each headline element
            for element in headline_elements[:max_urls]:
                # Find <a> tag within the element
                link_tag = element.find('a', href=True)
                if link_tag:
                    href = link_tag.get('href', '').strip()
                    # Extract title from the link text or title attribute
                    title = link_tag.get_text(strip=True) or link_tag.get('title', '')
                    
                    if href:
                        # Convert relative URLs to absolute
                        if href.startswith('/'):
                            href = f"https://news.naver.com{href}"
                        elif not href.startswith('http'):
                            href = f"https://news.naver.com/{href}"
                        
                        # Normalize URL (remove fragments, ensure proper format)
                        if '#' in href:
                            href = href.split('#')[0]
                        
                        # Only add if it's a valid article URL and not already in list
                        if 'article' in href and href not in urls:
                            urls.append(href)
                            titles.append(title)
                            print(f"  ✓ {title[:50]}..." if len(title) > 50 else f"  ✓ {title}")
                            print(f"    {href}")
            
            print(f"✅ Extracted {len(urls)} article URLs with titles")
            
    except Exception as e:
        print(f"❌ Error extracting URLs: {str(e)}")
        import traceback
        traceback.print_exc()
        return [], []
    
    return urls, titles


def update_daily_urls_file(urls: List[str], filepath: str = "data/urls/daily_urls.txt"):
    """
    Update daily_urls.txt file with new URLs, removing existing URL lines.
    
    Args:
        urls: List of URLs to write
        filepath: Path to the daily_urls.txt file
    """
    if not urls:
        print("⚠️  No URLs to write. Skipping file update.")
        return
    
    # Ensure directory exists
    file_path = Path(filepath)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Read existing file to preserve comments
    existing_content = []
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            existing_content = f.readlines()
    
    # Filter out existing URL lines and the auto-update comment
    # Keep only original comments and empty lines
    filtered_content = []
    for line in existing_content:
        line_stripped = line.strip()
        # Skip the auto-update comment line (we'll add it fresh)
        if 'Auto-updated URLs from Naver News Economy section' in line_stripped:
            continue
        # Keep original comments and empty lines
        elif not line_stripped or line_stripped.startswith('#'):
            filtered_content.append(line)
        # Skip lines that contain URLs (http:// or https://)
        elif 'http://' in line_stripped or 'https://' in line_stripped:
            continue  # Remove existing URL lines
        else:
            # Keep other non-URL lines (if any)
            filtered_content.append(line)
    
    # Prepare new content
    new_content = filtered_content
    
    # Add separator comment and newline if needed
    # Remove trailing empty lines first
    while new_content and not new_content[-1].strip():
        new_content.pop()
    
    # Add newline and comment
    if new_content:
        new_content.append("\n")
    new_content.append("# Auto-updated URLs from Naver News Economy section\n")
    
    # Add URLs (comma-separated on a single line)
    url_line = ','.join(urls)
    new_content.append(f"{url_line}\n")
    
    # Write to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_content)
    
    print(f"✅ Updated {filepath} with {len(urls)} URL(s) (removed existing URLs)")


def save_headlines(titles: List[str], filepath: str = "data/urls/daily_headlines.json"):
    """
    Save headline titles to a JSON file for use in Twitter posts.
    
    Args:
        titles: List of headline titles
        filepath: Path to save the headlines
    """
    if not titles:
        print("⚠️  No titles to save. Skipping headlines file.")
        return
    
    file_path = Path(filepath)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    headlines_data = {
        "headlines": titles,
        "count": len(titles)
    }
    
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(headlines_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Saved {len(titles)} headlines to {filepath}")


def main():
    """Main function."""
    # Naver News Economy section URL
    economy_url = "https://news.naver.com/section/101"
    
    # Maximum number of URLs to extract (default: 5)
    max_urls = int(os.environ.get('MAX_URLS', '5'))
    
    print("📰 Naver News Economy Headline Extractor")
    print("=" * 50)
    
    # Extract URLs and titles
    urls, titles = extract_headline_urls(economy_url, max_urls=max_urls)
    
    if not urls:
        print("❌ No URLs extracted. Exiting.")
        sys.exit(1)
    
    # Update files
    update_daily_urls_file(urls)
    save_headlines(titles)
    
    print("=" * 50)
    print("✅ Done!")
    sys.exit(0)


if __name__ == "__main__":
    main()

