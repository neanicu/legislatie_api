#!/usr/bin/env python3
"""
Test health check for Legislatie API Client.
"""

import sys
import json
from legislatie_client import LegislatieClient


def main():
    print("Initializing LegislatieClient...")
    client = LegislatieClient()

    print("Running health check...")
    health = client.check_health()

    print("\n=== Health Check Report ===")
    print(json.dumps(health, indent=2, default=str))

    # Summary
    print("\n=== Summary ===")
    print(f"Overall: {health['overall']}")
    print(f"SOAP API: {health['soap_api']['status']} - {health['soap_api']['details']}")
    print(f"Scraper: {health['scraper']['status']} - {health['scraper']['details']}")
    print(f"Cache: {health['cache']['status']} - {health['cache']['details']}")

    # Exit code based on overall health
    if health["overall"] == "healthy":
        print("\n✅ All systems operational.")
        sys.exit(0)
    elif health["overall"] == "unhealthy":
        print("\n⚠️  Some components unhealthy.")
        sys.exit(1)
    else:
        print("\n❌ Health check failed.")
        sys.exit(2)


if __name__ == "__main__":
    main()
