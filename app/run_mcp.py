from app.server import create_mcp_server

mcp = create_mcp_server()

if __name__ == "__main__":
    mcp.run(transport="http",host="0.0.0.0", port=3004)