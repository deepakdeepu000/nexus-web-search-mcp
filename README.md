# MCP Web Search

A production-ready [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that gives AI assistants clean, LLM-ready web search with automatic page content extraction.

## Features

- **Multi-provider search**: Serper (Google), Tavily, or self-hosted SearXNG
- **Smart content extraction**: Specialized handlers for StackOverflow, Wikipedia, GitHub Issues, and arXiv; universal HTML fallback for everything else  
- **Clean Markdown output**: trafilatura + markdownify pipeline strips boilerplate
- **Concurrent enrichment**: Fetches multiple result pages in parallel (configurable)
- **Robust error handling**: Failures become descriptive Markdown notes, never exceptions
- **Three transports**: stdio, SSE, or Streamable HTTP

## Tools

### `web_search(query, num_results=3)`
Search the web and return top results with extracted page content.

### `get_content(url)`
Fetch and extract a single URL.

## Quick Start

```bash
pip install -e .
cp .env.example .env   # add your SERPER_API_KEY or TAVILY_API_KEY
mcp-web-search --http  # manual testing
mcp-web-search --stdio # for MCP clients
```

## Claude Desktop Configuration

```json
{
  "mcpServers": {
    "web-search": {
      "command": "mcp-web-search",
      "args": ["--stdio"],
      "env": { "SERPER_API_KEY": "your_key_here" }
    }
  }
}
```

## Docker

```bash
docker build -t mcp-web-search .
docker run -p 8000:8000 -e SERPER_API_KEY=your_key mcp-web-search
```

## Architecture

```
src/mcp_web_search/
├── server.py              # FastMCP server + tool definitions
├── models.py              # Pydantic response types  
├── search/                # Provider router + Serper/Tavily/SearXNG
├── content/               # Resolution pipeline: SE/GitHub/Wikipedia/arXiv/HTML
└── utils/                 # Diagnostics + logging
```

## Development

```bash
pip install -e ".[dev]"
pytest           # 60 tests
ruff check src/  # lint
```
