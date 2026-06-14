"""Same text tools as before — over HTTP on a different port."""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("text", host="127.0.0.1", port=8002)

@mcp.tool()
def uppercase(text: str) -> str:
    """Convert text to uppercase."""
    return text.upper()

@mcp.tool()
def word_count(text: str) -> int:
    """Count the number of whitespace-separated words in text."""
    return len(text.split())

@mcp.tool()
def reverse(text: str) -> str:
    """Return the text with its characters reversed."""
    return text[::-1]

if __name__ == "__main__":
    # Exposes the MCP endpoint at http://127.0.0.1:8002/mcp
    mcp.run(transport="streamable-http")
    

#,
#        reasoning={"effort": "minimal"},   # or "none"
#        text={"verbosity": "low"},

# cache a lot, KV caching. 