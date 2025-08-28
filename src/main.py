from js import Response, Request
import json
from mcp_server import generate_tab, analyze_song_structure_tool, get_json_schema

async def on_fetch(request: Request) -> Response:
    """Handle HTTP requests to the Worker."""
    try:
        # Parse the request
        url = request.url
        method = request.method
        
        if method == "GET":
            # Health check or schema endpoint
            if url.endswith("/schema"):
                result = get_json_schema()
                return Response.new(json.dumps(result), {
                    "headers": {"Content-Type": "application/json"},
                    "status": 200
                })
            else:
                return Response.new("Tab Generator MCP Server - Ready", {
                    "status": 200,
                    "headers": {"Content-Type": "text/plain"}
                })
        
        elif method == "POST":
            # Handle MCP tool calls
            body = await request.text()
            request_data = json.loads(body)
            
            tool = request_data.get("tool")
            params = request_data.get("params", {})
            
            if tool == "generate_tab":
                result = generate_tab(params.get("tab_data", ""))
            elif tool == "analyze_song_structure":
                result = analyze_song_structure_tool(params.get("tab_data", ""))
            elif tool == "get_json_schema":
                result = get_json_schema()
            else:
                result = {"error": "Unknown tool"}
            
            return Response.new(json.dumps(result), {
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type"
                },
                "status": 200
            })
        
        else:
            return Response.new("Method not allowed", {"status": 405})
            
    except Exception as e:
        return Response.new(
            json.dumps({"error": str(e)}), 
            {"status": 500, "headers": {"Content-Type": "application/json"}}
        )

# Export the handler
export = {"fetch": on_fetch}
