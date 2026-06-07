import asyncio
import threading
from pathlib import Path

from mcp.server import Server
import mcp.types as types
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import Response
import uvicorn

from qgis.core import QgsProject


server = Server("qgis-mcp")


def get_project():
    return QgsProject.instance()


def find_layer(project, name):
    for layer in project.mapLayers().values():
        if layer.name() == name:
            return layer
    return None


TRUTHY = True
tool_router = {
    "get_project_info": "_get_project_info",
    "list_layers": "_list_layers",
    "get_layer_info": "_get_layer_info",
    "get_layer_features": "_get_layer_features",
    "run_expression": "_run_expression",
    "load_project": "_load_project",
    "render_map": "_render_map",
    "export_layout": "_export_layout",
    "create_layout": "_create_layout",
    "add_layer": "_add_layer",
    "export_layer": "_export_layer",
    "save_project": "_save_project",
    "get_layer_statistics": "_get_layer_statistics",
    "get_unique_values": "_get_unique_values",
    "count_features": "_count_features",
    "select_features": "_select_features",
    "extract_selected": "_extract_selected",
    "get_crs_info": "_get_crs_info",
    "set_layer_crs": "_set_layer_crs",
    "reproject_layer": "_reproject_layer",
    "set_project_crs": "_set_project_crs",
    "list_layouts": "_list_layouts",
    "get_layout_info": "_get_layout_info",
    "list_algorithms": "_list_algorithms",
    "run_processing": "_run_processing",
    "set_graduated_renderer": "_set_graduated_renderer",
    "set_layer_labels": "_set_layer_labels",
}


@server.list_tools()
async def handle_list_tools():
    from qgis_mcp.server import handle_list_tools as _list
    return await _list()


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict | None):
    project = get_project()

    if name == "get_project_info":
        return await _import_and_call("_get_project_info", project)
    elif name == "list_layers":
        return await _import_and_call("_list_layers", project)
    elif name == "get_layer_info":
        return await _import_and_call("_get_layer_info", project, arguments)
    elif name == "get_layer_features":
        return await _import_and_call("_get_layer_features", project, arguments)
    elif name == "run_expression":
        return await _import_and_call("_run_expression", arguments)
    elif name == "load_project":
        return await _import_and_call("_load_project", arguments)
    elif name == "render_map":
        return await _import_and_call("_render_map", project, arguments)
    elif name == "export_layout":
        return await _import_and_call("_export_layout", project, arguments)
    elif name == "create_layout":
        return await _import_and_call("_create_layout", project, arguments)
    elif name == "add_layer":
        return await _import_and_call("_add_layer", project, arguments)
    elif name == "export_layer":
        return await _import_and_call("_export_layer", project, arguments)
    elif name == "save_project":
        return await _import_and_call("_save_project", project, arguments)
    elif name == "get_layer_statistics":
        return await _import_and_call("_get_layer_statistics", project, arguments)
    elif name == "get_unique_values":
        return await _import_and_call("_get_unique_values", project, arguments)
    elif name == "count_features":
        return await _import_and_call("_count_features", project, arguments)
    elif name == "select_features":
        return await _import_and_call("_select_features", project, arguments)
    elif name == "extract_selected":
        return await _import_and_call("_extract_selected", project, arguments)
    elif name == "set_layer_crs":
        return await _import_and_call("_set_layer_crs", get_project(), arguments)
    elif name == "reproject_layer":
        return await _import_and_call("_reproject_layer", get_project(), arguments)
    elif name == "set_project_crs":
        return await _import_and_call("_set_project_crs", get_project(), arguments)
    elif name == "get_crs_info":
        return await _import_and_call("_get_crs_info", arguments)
    elif name == "list_layouts":
        return await _import_and_call("_list_layouts", project)
    elif name == "get_layout_info":
        return await _import_and_call("_get_layout_info", project, arguments)
    elif name == "list_algorithms":
        return await _import_and_call("_list_algorithms", arguments)
    elif name == "run_processing":
        return await _import_and_call("_run_processing", arguments)
    elif name == "set_layer_labels":
        return await _import_and_call("_set_layer_labels", get_project(), arguments)
    elif name == "set_graduated_renderer":
        return await _import_and_call("_set_graduated_renderer", get_project(), arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def _import_and_call(func_name, *args):
    import qgis_mcp.server as srv
    func = getattr(srv, func_name)
    return await func(*args)


sse = SseServerTransport("/messages/")


async def handle_sse(request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0], streams[1], server.create_initialization_options()
        )
    return Response()


async def run_sse_server(host="127.0.0.1", port=9876, stop_event=None):
    routes = [
        Route("/sse", endpoint=handle_sse, methods=["GET"]),
        Mount("/messages/", app=sse.handle_post_message),
    ]
    app = Starlette(routes=routes)

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="error",
        loop="asyncio",
    )
    uvicorn_server = uvicorn.Server(config)

    if stop_event:
        async def monitor():
            while not stop_event.is_set():
                await asyncio.sleep(1)
            uvicorn_server.should_exit = True
        asyncio.create_task(monitor())

    await uvicorn_server.serve()
