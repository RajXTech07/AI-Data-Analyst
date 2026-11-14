"""Quick verification script for your Gemini API Key.

Run with:
    python test_key.py
"""
import os
import sys
from dotenv import load_dotenv

# Load .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in .env file.")
    sys.exit(1)

print("=" * 60)
print(" GEMINI API KEY VERIFICATION")
print("=" * 60)
print(f"API Key Detected: True (length: {len(api_key)})")
print(f"Key Prefix: {api_key[:6]}... Suffix: ...{api_key[-4:]}")

try:
    from google import genai

    client = genai.Client(api_key=api_key)
    
    # 1. Test basic prompt
    model_name = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
    print(f"\n1. Sending test prompt to model '{model_name}'...")
    response = client.models.generate_content(
        model=model_name,
        contents="Say 'API Key is active and working!' in exactly one line."
    )
    print(f"\n>>> GEMINI OUTPUT RECEIVED:\n{response.text.strip()}\n")
    
    # 2. Check token usage metadata
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        um = response.usage_metadata
        print(f"Tokens consumed: prompt={um.prompt_token_count}, response={um.candidates_token_count}, total={um.total_token_count}")
    
    print("\n[SUCCESS] Your Gemini API key is valid, authentic, and responding.")
    print("=" * 60)

except Exception as err:
    print(f"\n[FAILURE] Error connecting with Gemini API: {err}")
    sys.exit(1)
