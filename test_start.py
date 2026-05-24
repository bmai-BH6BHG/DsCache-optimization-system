
import sys
sys.path.insert(0, 'H:\\GPU')

try:
    print("--- Testing imports ---")
    print("Importing requests...")
    import requests
    print("Importing fastapi...")
    import fastapi
    print("Importing uvicorn...")
    import uvicorn
    print("Importing mcp_server cache...")
    from mcp_server.cache.semantic import SemanticCache
    from mcp_server.cache.multi_level import MultiLevelCache
    from mcp_server.cache.adaptive_ttl import AdaptiveTTLManager
    print("--- All imports OK ---")

    print("\n--- Testing cache init ---")
    semantic = SemanticCache(similarity_threshold=0.80)
    multi = MultiLevelCache()
    ttl = AdaptiveTTLManager()
    print("--- Cache init OK ---")

    print("\n--- Importing relay_server ---")
    import relay_server
    print("--- Imported ---")
    print("Starting server...")
    import uvicorn
    uvicorn.run(relay_server.app, host="127.0.0.1", port=8001)

except Exception as e:
    print(f"\n--- ERROR ---")
    print(f"Type: {type(e).__name__}")
    print(f"Message: {str(e)}")
    import traceback
    print("\n--- Stack Trace ---")
    traceback.print_exc()
