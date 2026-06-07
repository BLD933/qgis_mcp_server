# QGIS MCP Server

An MCP (Model Context Protocol) server that exposes QGIS capabilities to AI agents. Supports both headless mode (stdio) and live QGIS desktop integration (SSE).

## Features

- **23 tools** covering project management, layer inspection, spatial queries, styling, and map export
- **Headless mode** — standalone process using `qgis_process`-style QGIS session
- **Desktop mode** — live connection to a running QGIS instance via SSE/HTTP
- **Zero-friction setup** — uses system QGIS Python bindings, no extra dependencies

## Tools

| Category | Tools |
|----------|-------|
| **Project** | `get_project_info`, `load_project`, `save_project` |
| **Layers** | `list_layers`, `get_layer_info`, `get_layer_features`, `add_layer`, `export_layer` |
| **Selection** | `select_features`, `extract_selected`, `count_features` |
| **Attributes** | `get_layer_statistics`, `get_unique_values`, `run_expression` |
| **Styling** | `set_graduated_renderer` |
| **Layout** | `create_layout`, `export_layout`, `list_layouts`, `get_layout_info` |
| **Render** | `render_map` |
| **Processing** | `list_algorithms`, `run_processing` |
| **CRS** | `get_crs_info` |

## Quick Start

```bash
# Install
pip install -e .

# Run headless
qgis-mcp

# Or use with opencode — add to .config/opencode/opencode.jsonc:
{
  "mcp": {
    "qgis": {
      "type": "local",
      "command": ["qgis-mcp"]
    }
  }
}
```

## Desktop Plugin

Install the QGIS plugin from `src/qgis_mcp_plugin/` to connect to a live QGIS session:

```bash
ln -s $(pwd)/src/qgis_mcp_plugin ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/
```

Then enable **qgis_mcp_plugin** in QGIS's Plugin Manager and add to your opencode config:

```json
{
  "mcp": {
    "qgis-desktop": {
      "type": "remote",
      "url": "http://127.0.0.1:9876/sse"
    }
  }
}
```

## License

MIT
