#!/usr/bin/env python3
"""
Load testing for Legislatie API Client using Locust.

This file defines user behavior for load testing the Romanian Legislative API Client.
Tests both SOAP API and HTML scraper fallback under various load conditions.
"""

import random
import time
from typing import Dict, Any

from locust import User, task, between, events
from locust.env import Environment

# Add project root to path to import legislatie_client
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from legislatie_client import LegislatieClient


class LegislatieUser(User):
    """
    Simulates a user interacting with the Legislatie API.
    """
    
    # Wait time between tasks (1-5 seconds)
    wait_time = between(1, 5)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = LegislatieClient()
        # Cache token to avoid repeated token requests during load test
        self._cached_token = None
        
    def on_start(self):
        """Called when a user starts executing tasks."""
        self.log("Starting legislatie load test user")
        
    def on_stop(self):
        """Called when a user stops executing tasks."""
        self.log("Stopping legislatie load test user")
        
    @task(5)
    def search_simple(self):
        """Perform a simple search with minimal parameters."""
        params = {
            "numar_pagina": 0,
            "rezultate_pagina": random.choice([10, 20, 50]),
            "an": str(random.randint(2010, 2025)) if random.random() > 0.7 else None,
            "text": random.choice(["contract", "lege", "hotărâre", "ordonanță", "decizie"]) 
                   if random.random() > 0.5 else None,
        }
        self._execute_search(params, "simple_search")
        
    @task(3)
    def search_advanced(self):
        """Perform an advanced search with multiple parameters."""
        params = {
            "numar_pagina": random.randint(0, 5),
            "rezultate_pagina": random.choice([10, 20]),
            "an": str(random.randint(2000, 2025)),
            "numar": str(random.randint(1, 100)) if random.random() > 0.7 else None,
            "text": random.choice(["contract de muncă", "cod fiscal", "procedură civilă"]),
            "titlu": random.choice(["LEGE", "HOTĂRÂRE", "ORDONANȚĂ"]),
        }
        self._execute_search(params, "advanced_search")
        
    @task(1)
    def search_empty(self):
        """Perform a search with no filters (returns all recent results)."""
        params = {
            "numar_pagina": 0,
            "rezultate_pagina": 10,
        }
        self._execute_search(params, "empty_search")
        
    @task(2)
    def search_with_diacritics(self):
        """Test search with Romanian diacritics."""
        params = {
            "numar_pagina": 0,
            "rezultate_pagina": 10,
            "text": random.choice(["ăâîșț", "Școală", "Învățământ", "Regulament"]),
            "titlu": random.choice(["HOTĂRÂRE", "ORDONANȚĂ", "DECIZIE"]),
        }
        self._execute_search(params, "diacritics_search")
    
    def _execute_search(self, params: Dict[str, Any], search_type: str):
        """Execute search and record metrics."""
        start_time = time.time()
        
        try:
            # Execute the search
            results = self.client.search(**params)
            duration = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            # Record success
            events.request.fire(
                request_type="SEARCH",
                name=f"search/{search_type}",
                response_time=duration,
                response_length=len(str(results)) if results else 0,
                exception=None,
                context=self.context()
            )
            
            # Log some info about the results
            if results and isinstance(results, dict):
                self.log(f"Search successful: {search_type}, found {results.get('total_rezultate', 0)} results")
            else:
                self.log(f"Search successful: {search_type}, but no results")
                
        except Exception as e:
            duration = (time.time() - start_time) * 1000
            
            # Record failure
            events.request.fire(
                request_type="SEARCH",
                name=f"search/{search_type}",
                response_time=duration,
                response_length=0,
                exception=e,
                context=self.context()
            )
            
            self.log(f"Search failed: {search_type}, error: {str(e)}")
    
    def log(self, message: str):
        """Helper for logging."""
        print(f"[User{id(self)}] {message}")
        
    def context(self) -> Dict[str, Any]:
        """Return context for request events."""
        return {"user_id": id(self)}


@events.init.add_listener
def on_locust_init(environment: Environment, **kwargs):
    """Called when Locust starts."""
    print("=" * 60)
    print("Legislatie API Load Test Initialized")
    print(f"Host: {environment.host if environment.host else 'Using local client'}")
    print(f"Users: {environment.runner.user_count if environment.runner else 'Unknown'}")
    print("=" * 60)


@events.test_start.add_listener
def on_test_start(environment: Environment, **kwargs):
    """Called when a test starts."""
    print(f"Load test started at {time.ctime()}")


@events.test_stop.add_listener
def on_test_stop(environment: Environment, **kwargs):
    """Called when a test stops."""
    print(f"Load test stopped at {time.ctime()}")
    print("Generating report...")


# Configuration for running locally
if __name__ == "__main__":
    import locust.main
    locust.main.main()