#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests>=2.25.0",
# ]
# ///

import requests
import sys
import os

def main():
    print("=== UV Script Dependencies Demo ===")
    print("This script demonstrates the uv script dependencies approach.")
    print(f"Python version: {sys.version}")
    print(f"Running from: {os.getcwd()}")
    print(f"Requests version: {requests.__version__}")
    
    print("\n=== Testing HTTP Request ===")
    try:
        response = requests.get("https://httpbin.org/json", timeout=5)
        if response.status_code == 200:
            print("✅ Successfully made HTTP request!")
            print(f"Response: {response.json()}")
        else:
            print(f"❌ HTTP request failed with status {response.status_code}")
    except Exception as e:
        print(f"❌ HTTP request failed: {e}")
    
    print("\n=== beancount-no-sparebank1 Package ===")
    print("In a real scenario, this script would:")
    print("1. Import beancount_no_sparebank1")
    print("2. Configure importers for SpareBank 1 data")
    print("3. Process CSV/PDF files from your bank")
    print("\nFor the actual package usage, see project_example.py")
    print("which uses the package installed in the project environment.")

if __name__ == '__main__':
    main()