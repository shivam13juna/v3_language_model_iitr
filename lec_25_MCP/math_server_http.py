from mcp.server.fastmcp import FastMCP


# FastMCP takes host/port for HTTP transports.
mcp = FastMCP("math", host="127.0.0.1", port=8001)


@mcp.tool()
def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


@mcp.tool()
def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b

@mcp.tool()
def power(base: float, exponent: float) -> float:
    """Raise base to the given exponent."""
    return base ** exponent

@mcp.tool()
def modulo(a: float, b: float) -> float:
    """Return the remainder of a divided by b."""
    return a % b

if __name__ == "__main__":
    # Exposes the MCP endpoint at http://127.0.0.1:8001/mcp
    mcp.run(transport="streamable-http")