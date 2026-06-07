import asyncio
import os
import threading
from pathlib import Path

from qgis.core import QgsProject
from qgis.utils import iface

from qgis_mcp.server import (
    find_layer,
    _get_project_info,
    _list_layers,
    _get_layer_info,
    _get_layer_features,
    _run_expression,
    _load_project,
    _render_map,
    _export_layout,
    _create_layout,
    _add_layer,
    _export_layer,
    _save_project,
    _get_layer_statistics,
    _get_unique_values,
    _count_features,
    _select_features,
    _extract_selected,
    _get_crs_info,
    _list_layouts,
    _get_layout_info,
    _list_algorithms,
    _run_processing,
)

from .mcp_server_plugin import run_sse_server


DEFAULT_PORT = 9876


class QgisMcpPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.server_thread = None
        self.stop_event = threading.Event()
        self.port = int(os.environ.get("QGIS_MCP_PORT", DEFAULT_PORT))

    def initGui(self):
        self.server_thread = threading.Thread(
            target=self._run_server, daemon=True
        )
        self.server_thread.start()

    def unload(self):
        self.stop_event.set()
        if self.server_thread:
            self.server_thread.join(timeout=5)

    def _run_server(self):
        asyncio.run(
            run_sse_server(
                host="127.0.0.1",
                port=self.port,
                stop_event=self.stop_event,
            )
        )
