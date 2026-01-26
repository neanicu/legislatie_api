import requests
from bs4 import BeautifulSoup
import re
import logging
from datetime import datetime
import time
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import config

logger = logging.getLogger(__name__)


class LegislatieScraper:
    BASE_URL = config.BASE_URL

    def __init__(self):
        self.session = requests.Session()

        # Configure retries for transient errors
        retries = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))
        self.session.mount("http://", HTTPAdapter(max_retries=retries))

        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
        )
        self.token = None
        self.last_request_time = 0
        self.request_delay = config.REQUEST_DELAY  # seconds between requests

    def _rate_limit(self):
        """Enforce delay between requests to be polite to the server"""
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def _parse_date(self, date_str):
        """
        Parse date string in DD/MM/YYYY format to YYYY-MM-DD.
        Returns empty string if parsing fails.
        """
        if not date_str:
            return ""
        # Try DD/MM/YYYY format
        try:
            date_obj = datetime.strptime(date_str, "%d/%m/%Y")
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            pass
        # Try other formats if needed
        return ""

    def _ensure_token(self):
        if self.token:
            return

        self._rate_limit()
        try:
            r = self.session.get(self.BASE_URL, timeout=config.REQUEST_TIMEOUT)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            token_input = soup.find("input", {"name": "__RequestVerificationToken"})
            if token_input:
                self.token = token_input["value"]
                logger.debug(f"Token obtained: {self.token[:20]}...")
            else:
                logger.error("Could not find verification token on homepage")
                # Try alternative selector
                token_input = soup.find("input", {"name": "__RequestVerificationToken"})
                if not token_input:
                    raise ValueError("Verification token not found in homepage")
        except Exception as e:
            logger.error(f"Error fetching token: {e}")
            raise

    def search(
        self,
        numar_pagina=0,
        rezultate_pagina=10,
        an=None,
        numar=None,
        text=None,
        titlu=None,
    ):
        """
        Mimics the SOAP Search method but uses HTML scraping.
        Returns results for the requested page (0-based).
        """
        self._ensure_token()

        # Prepare params - MUST include all fields expected by the server
        params = {
            "__RequestVerificationToken": self.token,
            "TitleText": titlu or "",
            "ContentText_First": text or "",
            "ContentText_Second": "",
            "ContentText_Third": "",
            "ContentText_Fourth": "",
            "opContentText_Second": "",
            "opContentText_Third": "",
            "opContentText_Fourth": "",
            "DocumentType": "",
            "DocumentNumber": numar or "",
            "DataSemnariiTextFrom": "",
            "DataSemnariiTextTo": "",
            "PublishedInName": "",
            "PublishedInNumber": "",
            "DataPublicariiTextFrom": "",
            "DataPublicariiTextTo": "",
            "ActInForceOnDateTextFrom": "",
            "EmitentAct": "",
        }

        if an:
            params["DataSemnariiTextFrom"] = f"{an}/01/01"
            params["DataSemnariiTextTo"] = f"{an}/12/31"

        try:
            self._rate_limit()
            # Post to root with allow_redirects to follow to results page
            r = self.session.post(
                self.BASE_URL + "/",
                data=params,
                allow_redirects=True,
                timeout=config.REQUEST_TIMEOUT,
            )
            r.raise_for_status()

            # Force UTF-8 encoding as the site headers might be missing it or incorrect
            r.encoding = "utf-8"

            # The final URL after redirect contains the search parameters as query string
            # e.g., /Public/RezultateCautare?text1=...
            final_url = r.url

            # For pagination beyond page 1, we need to modify the URL to add page parameter
            # Page numbers are 1-based in the URL, while numar_pagina is 0-based
            target_page = numar_pagina + 1

            if target_page > 1:
                # Parse URL and add/replace page parameter
                from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

                parsed = urlparse(final_url)
                query_dict = parse_qs(parsed.query)
                query_dict["page"] = [str(target_page)]
                # Keep other parameters
                new_query = urlencode(query_dict, doseq=True)
                new_url = urlunparse(parsed._replace(query=new_query))

                # Fetch the paginated page
                self._rate_limit()
                r = self.session.get(new_url, timeout=config.REQUEST_TIMEOUT)
                r.raise_for_status()
                r.encoding = "utf-8"

            return self._parse_results(r.text)
        except Exception as e:
            logger.error(f"Scraper search failed: {e}")
            # If token is invalid, clear it so next call refreshes it
            if "VerificationToken" in str(e) or "token" in str(e).lower():
                self.token = None
            raise

    def _parse_results(self, html_content):
        soup = BeautifulSoup(html_content, "html.parser")
        results = []

        items = soup.find_all("div", class_="search_result_item")
        for item in items:
            try:
                # 1. Parse Link Line: "1. DECRET 15 04/01/2023"
                link_p = item.find("p")
                link_tag = link_p.find("a") if link_p else None

                if not link_tag:
                    continue

                href = str(link_tag.get("href", ""))
                full_link = f"{self.BASE_URL}{href}" if href.startswith("/") else href

                # Regex to extract structured info from link text
                # Format: Index. TYPE NUMBER DATE
                link_text = link_tag.get_text(strip=True)

                # Parsing logic
                # Try to extract Date (DD/MM/YYYY)
                data_vigoare = None
                date_match = re.search(r"(\d{2}/\d{2}/\d{4})", link_text)
                if date_match:
                    # Convert to YYYY-MM-DD for consistency with API
                    d_str = date_match.group(1)
                    try:
                        data_vigoare = datetime.strptime(d_str, "%d/%m/%Y").strftime(
                            "%Y-%m-%d"
                        )
                    except:
                        data_vigoare = d_str

                # Try to extract Numar
                # Usually "TYPE NUMBER DATE" -> "DECRET 15 04/01/2023"
                numar_act = None
                # Remove index "1. "
                clean_text = re.sub(r"^\d+\.\s*", "", link_text)
                # Remove Date
                if date_match:
                    clean_text = clean_text.replace(date_match.group(1), "").strip()

                # Extract last digits as number
                num_match = re.search(r"(\d+)$", clean_text)
                if num_match:
                    numar_act = num_match.group(1)
                    # Remove number from text to get Type
                    tip_act = clean_text[: num_match.start()].strip()
                else:
                    tip_act = clean_text

                # 2. Parse Title and Snippet
                # <span class="S_DEN">...</span>
                title_span = item.find("span", class_="S_DEN")
                titlu = title_span.get_text(strip=True) if title_span else ""

                # 3. Parse Emitent (Issuer) - from S_EMT_BDY span inside S_EMT table
                emitent = None
                emitent_table = item.find("table", class_="S_EMT")
                if emitent_table:
                    emitent_body = emitent_table.find("span", class_="S_EMT_BDY")
                    if emitent_body:
                        # Extract text, remove HTML tags
                        emitent = emitent_body.get_text(strip=True)
                        # Clean up list items if present
                        emitent = re.sub(r"\s+", " ", emitent)

                # 4. Parse Publicatie (Publication) - from S_PUB_BDY span
                publicatie = None
                pub_span = item.find("span", class_="S_PUB")
                if pub_span:
                    pub_body = pub_span.find("span", class_="S_PUB_BDY")
                    if pub_body:
                        publicatie = pub_body.get_text(strip=True)

                # 5. Parse Snippet
                # <span class="S_PAR">...</span>
                snippet_span = item.find("span", class_="S_PAR")
                text_preview = snippet_span.get_text(strip=True) if snippet_span else ""

                results.append(
                    {
                        "Titlu": titlu or tip_act,  # Fallback
                        "Numar": numar_act,
                        "DataVigoare": data_vigoare,
                        "Emitent": emitent,
                        "Publicatie": publicatie,
                        "Text": text_preview,
                        "LinkHtml": full_link,
                        "TipAct": tip_act,
                    }
                )

            except Exception as e:
                logger.warning(f"Failed to parse item: {e}")
                continue

        return results


if __name__ == "__main__":
    # Test
    scraper = LegislatieScraper()
    print("Testing Scraper...")
    res = scraper.search(numar="15", an="2023")
    print(f"Found {len(res)} results")
    for r in res[:3]:
        print(r)
