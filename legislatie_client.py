import sys  # noqa: F401
import time
from zeep import Client, Settings
from zeep.exceptions import Fault
from zeep.transports import Transport
import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from legislatie_scraper import LegislatieScraper
import config
from cache import get_cache


class LegislatieClient:
    # Default values (overridden by config)
    WSDL_URL = config.WSDL_URL

    def __init__(
        self,
        status_callback=None,
        use_persistent_cache=None,
        cache_dir=None,
        cache_ttl=None,
    ):
        settings = Settings()

        # Configure session with headers
        session = requests.Session()

        retries = Retry(
            total=config.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Custom Transport cu timeout de 30 secunde pentru a evita blocajele infinite
        self.transport = Transport(session=session, timeout=config.SOAP_TIMEOUT)
        # Set User-Agent AFTER Transport init (zeep overwrites it)
        session.headers["User-Agent"] = "Mozilla/5.0 (compatible; LegislatieAPI/1.0)"

        self.client = Client(
            wsdl=self.WSDL_URL, settings=settings, transport=self.transport
        )
        self.scraper = LegislatieScraper()

        # Callback pentru a notifica UI-ul (ex: st.toast)
        self.status_callback = status_callback

        # Force HTTPS endpoint address
        self.service = self.client.create_service(
            "{http://tempuri.org/}SoapEndPoint", config.SOAP_ENDPOINT
        )
        self.token = None

        # Initialize cache
        use_cache = (
            config.USE_PERSISTENT_CACHE
            if use_persistent_cache is None
            else use_persistent_cache
        )
        cache_dir = config.CACHE_PATH if cache_dir is None else cache_dir
        cache_ttl = config.CACHE_TTL if cache_ttl is None else cache_ttl

        self.cache = get_cache(
            use_persistent=use_cache, cache_dir=cache_dir, ttl=cache_ttl
        )

        self.logger = logging.getLogger(__name__)
        self.logger.info(
            f"LegislatieClient initialized with {'persistent' if use_cache else 'in-memory'} cache"
        )

    def get_token(self):
        try:
            if self.status_callback:
                self.status_callback("Se reînnoiește token-ul de acces...")
            self.token = self.service.GetToken()
            return self.token
        except Fault as e:
            self.logger.error(f"Error calling GetToken: {e}")
            return None

    def search(
        self,
        numar_pagina=0,
        rezultate_pagina=10,
        an=None,
        numar=None,
        text=None,
        titlu=None,
        retry=True,
    ):
        # Generate cache key using cache instance
        cache_key = self.cache.generate_search_key(
            numar_pagina=numar_pagina,
            rezultate_pagina=rezultate_pagina,
            an=an,
            numar=numar,
            text=text,
            titlu=titlu,
        )

        # Check cache first
        cached_results = self.cache.get(cache_key)
        if cached_results is not None:
            self.logger.info(f"Returning cached results for page {numar_pagina}")
            return cached_results

        if not self.token:
            self.get_token()

        if not self.token:
            # Nu ridicam exceptie blocanta, returnam lista goala si logam
            self.logger.warning("Nu s-a putut obtine token-ul de acces.")
            return []

        search_params = {
            "NumarPagina": numar_pagina,
            "RezultatePagina": rezultate_pagina,
            "SearchAn": an,
            "SearchNumar": numar,
            "SearchText": text,
            "SearchTitlu": titlu,
        }

        try:
            # Saving the last response content for debugging is tricky without a custom transport hook
            # but we can trust zeep to decode if the server sends correct bytes.

            response = self.service.Search(
                SearchModel=search_params, tokenKey=self.token
            )

            results = []
            if isinstance(response, list):
                results = response
            elif hasattr(response, "Legi"):
                results = response.Legi
            elif hasattr(response, "SearchResult") and hasattr(
                response.SearchResult, "Legi"
            ):
                results = response.SearchResult.Legi

            # Cache the results
            self.cache.set(cache_key, results)
            self.logger.debug(f"Cached results for page {numar_pagina}")
            return results

        except Fault as e:
            # Check for token expiration error
            error_msg = str(e).upper()
            if retry and ("TOKEN INVALID" in error_msg or "EXPIRAT" in error_msg):
                if self.status_callback:
                    self.status_callback("Sesiune expirată. Se reconectează...")
                else:
                    self.logger.info(
                        "Token expired. Regenerating token and retrying..."
                    )

                self.get_token()
                if self.token:
                    return self.search(
                        numar_pagina,
                        rezultate_pagina,
                        an,
                        numar,
                        text,
                        titlu,
                        retry=False,
                    )

            if "Unable to connect to the remote server" in str(e):
                self.logger.warning(
                    f"SOAP API failed: {e}. Attempting HTML scraping fallback..."
                )
                if self.status_callback:
                    self.status_callback(
                        "API Indisponibil. Se încearcă metoda alternativă (Web Scraping)..."
                    )

                try:
                    scraper_results = self.scraper.search(
                        numar_pagina=numar_pagina,
                        rezultate_pagina=rezultate_pagina,
                        an=an,
                        numar=numar,
                        text=text,
                        titlu=titlu,
                    )
                    # Cache scraper results as well
                    self.cache.set(cache_key, scraper_results)
                    return scraper_results
                except Exception as scraper_err:
                    friendly_msg = (
                        "CRITICAL SERVER ERROR: Both the legislative API and Website search are unavailable. "
                        "The remote server (legislatie.just.ro) is experiencing internal connectivity issues (Solr). "
                        "Please try again later."
                    )
                    self.logger.error(friendly_msg)
                    # Raise the original error but with the friendly message context
                    raise Exception(friendly_msg) from e

            self.logger.error(f"Error calling Search (Fault): {e}")
            raise e  # Propagam eroarea pentru a fi prinsa in UI

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error calling Search: {e}")
            if retry:
                if self.status_callback:
                    self.status_callback("Eroare rețea. Se reîncearcă...")
                # Mai incercam o data
                return self.search(
                    numar_pagina, rezultate_pagina, an, numar, text, titlu, retry=False
                )
            raise e  # Propagam eroarea de retea

        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            raise e

    def check_health(self) -> dict:
        """
        Perform health checks on both SOAP API and HTML scraper.

        Returns:
            Dictionary with health status and details for each component.
        """

        health_report = {
            "timestamp": time.time(),
            "soap_api": {"status": "unknown", "details": ""},
            "scraper": {"status": "unknown", "details": ""},
            "cache": {"status": "unknown", "details": ""},
            "overall": "unknown",
        }

        # Check SOAP API
        start = time.time()
        try:
            token = self.get_token()
        except Exception as e:
            elapsed = time.time() - start
            health_report["soap_api"]["status"] = "error"
            health_report["soap_api"]["details"] = f"Exception: {str(e)}"
            health_report["soap_api"]["response_time"] = elapsed
        else:
            elapsed = time.time() - start
            health_report["soap_api"]["response_time"] = elapsed
            if token:
                health_report["soap_api"]["status"] = "healthy"
                health_report["soap_api"]["details"] = (
                    f"Token obtained in {elapsed:.2f}s"
                )
            else:
                health_report["soap_api"]["status"] = "unhealthy"
                health_report["soap_api"]["details"] = "Failed to obtain token"

        # Check Scraper
        start = time.time()
        try:
            # Try a simple search with minimal parameters
            results = self.scraper.search(numar_pagina=0, rezultate_pagina=1)
        except Exception as e:
            elapsed = time.time() - start
            health_report["scraper"]["status"] = "error"
            health_report["scraper"]["details"] = f"Exception: {str(e)}"
            health_report["scraper"]["response_time"] = elapsed
        else:
            elapsed = time.time() - start
            health_report["scraper"]["response_time"] = elapsed
            if isinstance(results, list):
                health_report["scraper"]["status"] = "healthy"
                health_report["scraper"]["details"] = (
                    f"Retrieved {len(results)} results in {elapsed:.2f}s"
                )
            else:
                health_report["scraper"]["status"] = "unhealthy"
                health_report["scraper"]["details"] = (
                    f"Unexpected result type: {type(results)}"
                )

        # Check Cache
        try:
            stats = self.cache.get_stats()
            health_report["cache"]["status"] = "healthy"
            health_report["cache"]["details"] = stats
        except Exception as e:
            health_report["cache"]["status"] = "error"
            health_report["cache"]["details"] = f"Exception: {str(e)}"

        # Determine overall status
        statuses = [
            health_report["soap_api"]["status"],
            health_report["scraper"]["status"],
            health_report["cache"]["status"],
        ]

        if all(s == "healthy" for s in statuses):
            health_report["overall"] = "healthy"
        elif any(s == "error" for s in statuses):
            health_report["overall"] = "error"
        elif any(s == "unhealthy" for s in statuses):
            health_report["overall"] = "unhealthy"
        else:
            health_report["overall"] = "unknown"

        return health_report


def main():
    import json

    # Simple argument parsing
    if "--health" in sys.argv:
        sys.stdout.reconfigure(encoding="utf-8")
        client = LegislatieClient()
        health = client.check_health()
        print(json.dumps(health, indent=2, default=str))

        # Exit code based on overall health
        if health["overall"] == "healthy":
            sys.exit(0)
        elif health["overall"] == "unhealthy":
            sys.exit(1)
        else:
            sys.exit(2)

    elif "--cache-stats" in sys.argv:
        sys.stdout.reconfigure(encoding="utf-8")
        client = LegislatieClient()
        stats = client.cache.get_stats()
        print(json.dumps(stats, indent=2, default=str))
        sys.exit(0)

    else:
        # Default behavior: run search demo
        sys.stdout.reconfigure(encoding="utf-8")

        client = LegislatieClient()

        print(f"Connecting to {LegislatieClient.WSDL_URL}...")
        token = client.get_token()

        if token:
            print(f"Token received: {token}")

            print("\nCalling Search (Page 0)...")
            results = client.search(numar_pagina=0, rezultate_pagina=10)

            if results:
                print(f"\nFound {len(results)} results:")
                for lege in results:
                    print("-" * 50)

                    # Helper pentru acces sigur la atribute
                    def get_attr(obj, attr):
                        return (
                            obj[attr]
                            if isinstance(obj, dict)
                            else getattr(obj, attr, None)
                        )

                    print(f"Titlu: {get_attr(lege, 'Titlu')}")
                    print(f"Numar: {get_attr(lege, 'Numar')}")
                    print(f"Data: {get_attr(lege, 'DataVigoare')}")
                    print(f"Emitent: {get_attr(lege, 'Emitent')}")

                    text = get_attr(lege, "Text")
                    if text:
                        print(f"Text (preview): {text[:100]}...")
            else:
                print("No results found.")
        else:
            print("Failed to initialize session.")


if __name__ == "__main__":
    main()
