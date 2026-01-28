#!/usr/bin/env python3
"""
Test that Streamlit app imports correctly.
"""

import sys
import os
import pytest

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

pytestmark = pytest.mark.integration

try:
    from streamlit_app import (
        main,
        clean_legislatie_text,
        generate_akoma_ntoso,
        unpack_results,
    )

    print("OK All imports successful")

    # Test helper functions
    test_text = "Test text"
    cleaned = clean_legislatie_text(test_text)
    print(f"OK clean_legislatie_text works: {cleaned}")

    # Test unpack_results with dummy data
    dummy_results = [
        {
            "Titlu": "Test",
            "Numar": "1",
            "DataVigoare": "2023-01-01",
            "Emitent": "Test",
            "Text": "Test",
            "LinkHtml": "",
            "TipAct": "Test",
            "Publicatie": "",
        }
    ]
    unpacked = unpack_results(dummy_results)
    print(f"OK unpack_results works: {len(unpacked)} items")

    print("\nOK Streamlit app modules are functional.")

except Exception as e:
    print(f"ERROR Import error: {e}")
    sys.exit(1)
