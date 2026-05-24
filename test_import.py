
import sys
print("Python path:", sys.path)
sys.path.insert(0, 'H:\\GPU')
print("After adding GPU path:", sys.path)

try:
    import fastapi
    print("[OK] fastapi imported")
except Exception as e:
    print("[ERROR] fastapi failed:", e)

try:
    import uvicorn
    print("[OK] uvicorn imported")
except Exception as e:
    print("[ERROR] uvicorn failed:", e)

try:
    import requests
    print("[OK] requests imported")
except Exception as e:
    print("[ERROR] requests failed:", e)

try:
    from sentence_transformers import SentenceTransformer
    print("[OK] sentence_transformers imported")
except Exception as e:
    print("[ERROR] sentence_transformers failed:", e)
    import traceback
    print(traceback.format_exc())

try:
    from mcp_server.cache.semantic import SemanticCache
    print("[OK] SemanticCache imported")
except Exception as e:
    print("[ERROR] SemanticCache failed:", e)
    import traceback
    print(traceback.format_exc())
