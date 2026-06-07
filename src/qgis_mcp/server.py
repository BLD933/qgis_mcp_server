import asyncio
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types

QGIS_AVAILABLE = False
QGIS_INITIALIZED = False
qgs_app = None

try:
    from qgis.core import (
        QgsApplication,
        QgsProject,
        QgsWkbTypes,
        QgsExpression,
        QgsFeatureRequest,
        QgsFeature,
        QgsGeometry,
        QgsFields,
        QgsField,
        QgsMapSettings,
        QgsMapRendererSequentialJob,
        QgsPrintLayout,
        QgsLayoutItemMap,
        QgsLayoutItemLegend,
        QgsLayoutItemPicture,
        QgsLayoutExporter,
        QgsLayoutPoint,
        QgsLayoutSize,
        QgsUnitTypes,
        QgsVectorLayer,
        QgsRasterLayer,
        QgsVectorFileWriter,
        QgsCoordinateReferenceSystem,
        QgsCoordinateTransform,
        QgsStatisticalSummary,
        QgsCoordinateTransformContext,
        QgsGraduatedSymbolRenderer,
        QgsRendererRange,
        QgsSymbol,
        QgsVectorLayerSimpleLabeling,
        QgsPalLayerSettings,
        QgsTextFormat,
    )
    from PyQt5.QtGui import QImage, QColor, QFont
    from PyQt5.QtCore import QSize, QRectF
    QGIS_AVAILABLE = True
except ImportError:
    pass


def init_qgis() -> str | None:
    global QGIS_INITIALIZED, qgs_app
    if QGIS_INITIALIZED:
        return None
    if not QGIS_AVAILABLE:
        return "QGIS Python bindings (qgis.core) not available. Install qgis or use a QGIS environment."

    try:
        qgs_prefix = os.environ.get("QGIS_PREFIX_PATH", "/usr")
        QgsApplication.setPrefixPath(qgs_prefix, True)
        qgs_app = QgsApplication([], False)
        qgs_app.initQgis()
        QGIS_INITIALIZED = True
        return None
    except Exception as e:
        return f"Failed to initialize QGIS: {e}"


def get_project() -> QgsProject | None:
    return QgsProject.instance()


def find_layer(project: QgsProject, name: str):
    for layer in project.mapLayers().values():
        if layer.name() == name:
            return layer
    return None


server = Server("qgis-mcp")


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    tools = [
        types.Tool(
            name="get_project_info",
            description="Get current QGIS project metadata (title, CRS, file path, extent)",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="list_layers",
            description="List all layers in the current QGIS project with their type and visibility",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_layer_info",
            description="Get detailed information about a specific layer",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the layer",
                    }
                },
                "required": ["layer_name"],
            },
        ),
        types.Tool(
            name="get_layer_features",
            description="Query features from a vector layer with optional filter expression",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the layer",
                    },
                    "filter": {
                        "type": "string",
                        "description": "Optional QGIS expression filter (e.g. \"population > 10000\")",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of features to return (default 100)",
                        "default": 100,
                    },
                },
                "required": ["layer_name"],
            },
        ),
        types.Tool(
            name="run_expression",
            description="Evaluate a QGIS expression and return the result",
            inputSchema={
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "QGIS expression to evaluate",
                    }
                },
                "required": ["expression"],
            },
        ),
        types.Tool(
            name="load_project",
            description="Load a QGIS project file (.qgz or .qgs)",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the .qgz or .qgs project file",
                    }
                },
                "required": ["project_path"],
            },
        ),
        types.Tool(
            name="render_map",
            description="Render the current map to a PNG image file",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the PNG image",
                    },
                    "width": {
                        "type": "integer",
                        "description": "Image width in pixels (default 1920)",
                        "default": 1920,
                    },
                    "height": {
                        "type": "integer",
                        "description": "Image height in pixels (default 1080)",
                        "default": 1080,
                    },
                    "layer_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of layer names to include. Defaults to all visible layers.",
                    },
                    "dpi": {
                        "type": "integer",
                        "description": "Output DPI (default 96)",
                        "default": 96,
                    },
                },
            },
        ),
        types.Tool(
            name="export_layout",
            description="Export a print layout as PDF or PNG",
            inputSchema={
                "type": "object",
                "properties": {
                    "layout_name": {
                        "type": "string",
                        "description": "Name of the print layout to export",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the exported file (.pdf or .png)",
                    },
                },
                "required": ["layout_name", "output_path"],
            },
        ),
        types.Tool(
            name="create_layout",
            description="Create a new print layout with a map, legend, and north arrow",
            inputSchema={
                "type": "object",
                "properties": {
                    "layout_name": {
                        "type": "string",
                        "description": "Name for the new layout",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to save the exported PDF or PNG",
                    },
                    "page_width": {
                        "type": "number",
                        "description": "Page width in mm (default 297 for A3)",
                        "default": 297,
                    },
                    "page_height": {
                        "type": "number",
                        "description": "Page height in mm (default 420 for A3)",
                        "default": 420,
                    },
                    "dpi": {
                        "type": "integer",
                        "description": "Export DPI (default 300)",
                        "default": 300,
                    },
                    "add_legend": {
                        "type": "boolean",
                        "description": "Add a legend to the layout (default true)",
                        "default": True,
                    },
                    "add_north_arrow": {
                        "type": "boolean",
                        "description": "Add a north arrow to the layout (default true)",
                        "default": True,
                    },
                },
                "required": ["layout_name", "output_path"],
            },
        ),
        types.Tool(
            name="add_layer",
            description="Add a vector or raster layer from a file to the project",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the vector/raster file",
                    },
                    "layer_name": {
                        "type": "string",
                        "description": "Optional custom name for the layer (defaults to filename)",
                    },
                    "provider": {
                        "type": "string",
                        "description": "Data provider (ogr for vectors, gdal for rasters). Auto-detected if not set.",
                    },
                },
                "required": ["file_path"],
            },
        ),
        types.Tool(
            name="export_layer",
            description="Export a vector layer to GeoJSON, GPKG, Shapefile, or other formats",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the layer to export",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Output file path (.geojson, .gpkg, .shp, etc.)",
                    },
                    "filter_expression": {
                        "type": "string",
                        "description": "Optional QGIS expression filter to export a subset of features",
                    },
                    "crs": {
                        "type": "string",
                        "description": "Optional target CRS (e.g. EPSG:4326). Defaults to layer CRS.",
                    },
                },
                "required": ["layer_name", "output_path"],
            },
        ),
        types.Tool(
            name="save_project",
            description="Save the current QGIS project to its file path or a new path",
            inputSchema={
                "type": "object",
                "properties": {
                    "output_path": {
                        "type": "string",
                        "description": "Optional path to save to. Defaults to the current project path.",
                    },
                },
            },
        ),
        types.Tool(
            name="get_layer_statistics",
            description="Get statistics (count, sum, mean, min, max, stdev) for a numeric field",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the vector layer",
                    },
                    "field_name": {
                        "type": "string",
                        "description": "Name of the numeric field",
                    },
                    "filter_expression": {
                        "type": "string",
                        "description": "Optional QGIS expression to filter features before computing stats",
                    },
                },
                "required": ["layer_name", "field_name"],
            },
        ),
        types.Tool(
            name="get_unique_values",
            description="Get unique values from a field in a vector layer",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the vector layer",
                    },
                    "field_name": {
                        "type": "string",
                        "description": "Name of the field",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of unique values to return (default 100)",
                        "default": 100,
                    },
                },
                "required": ["layer_name", "field_name"],
            },
        ),
        types.Tool(
            name="count_features",
            description="Count features in a layer, optionally filtered by an expression",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the layer",
                    },
                    "filter_expression": {
                        "type": "string",
                        "description": "Optional QGIS expression to filter features",
                    },
                },
                "required": ["layer_name"],
            },
        ),
        types.Tool(
            name="get_crs_info",
            description="Get details about a Coordinate Reference System by EPSG code",
            inputSchema={
                "type": "object",
                "properties": {
                    "crs_id": {
                        "type": "string",
                        "description": "CRS identifier (e.g. EPSG:4326, EPSG:3857)",
                    },
                },
                "required": ["crs_id"],
            },
        ),
        types.Tool(
            name="set_layer_crs",
            description="Assign a different CRS to a layer without reprojecting geometries",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {"type": "string", "description": "Name of the layer"},
                    "crs_id": {"type": "string", "description": "Target CRS (e.g. EPSG:4326, EPSG:3857)"},
                },
                "required": ["layer_name", "crs_id"],
            },
        ),
        types.Tool(
            name="reproject_layer",
            description="Reproject a layer's geometries to a different CRS, creating a new memory layer",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {"type": "string", "description": "Name of the source layer"},
                    "target_crs": {"type": "string", "description": "Target CRS (e.g. EPSG:4326, EPSG:3857)"},
                    "new_layer_name": {"type": "string", "description": "Name for the new reprojected layer (default: source + '_reprojected')"},
                },
                "required": ["layer_name", "target_crs"],
            },
        ),
        types.Tool(
            name="set_project_crs",
            description="Change the project's coordinate reference system",
            inputSchema={
                "type": "object",
                "properties": {
                    "crs_id": {"type": "string", "description": "Target CRS (e.g. EPSG:4326, EPSG:3857)"},
                },
                "required": ["crs_id"],
            },
        ),
        types.Tool(
            name="select_features",
            description="Select features in a vector layer by expression, location, or attribute",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the vector layer",
                    },
                    "method": {
                        "type": "string",
                        "description": "Selection method: 'by_expression', 'by_location', 'by_attribute'",
                    },
                    "expression": {
                        "type": "string",
                        "description": "QGIS expression for 'by_expression' method (e.g. \"population > 10000\")",
                    },
                    "select_layer_name": {
                        "type": "string",
                        "description": "Reference layer for 'by_location' method",
                    },
                    "predicate": {
                        "type": "string",
                        "description": "Spatial predicate for 'by_location': intersect, contain, within, equal, touch, overlap, cross, disjoint",
                    },
                    "attribute_field": {
                        "type": "string",
                        "description": "Field name for 'by_attribute' method",
                    },
                    "attribute_value": {
                        "type": "string",
                        "description": "Value to match for 'by_attribute' method",
                    },
                    "attribute_operator": {
                        "type": "string",
                        "description": "Comparison operator for 'by_attribute': =, !=, <, >, <=, >=, like, not_like (default =)",
                    },
                    "selection_type": {
                        "type": "string",
                        "description": "How to modify selection: 'new', 'add', 'remove', 'intersect' (default 'new')",
                    },
                },
                "required": ["layer_name", "method"],
            },
        ),
        types.Tool(
            name="extract_selected",
            description="Extract selected features from a layer into a new memory layer added to the project",
            inputSchema={
                "type": "object",
                "properties": {
                    "source_layer": {
                        "type": "string",
                        "description": "Name of the source layer with selected features",
                    },
                    "new_layer_name": {
                        "type": "string",
                        "description": "Name for the new layer (defaults to source name + '_selected')",
                    },
                },
                "required": ["source_layer"],
            },
        ),
        types.Tool(
            name="list_layouts",
            description="List all print layouts in the current project",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        types.Tool(
            name="get_layout_info",
            description="Get detailed information about a print layout",
            inputSchema={
                "type": "object",
                "properties": {
                    "layout_name": {
                        "type": "string",
                        "description": "Name of the layout",
                    },
                },
                "required": ["layout_name"],
            },
        ),
        types.Tool(
            name="set_layer_labels",
            description="Configure labels on a vector layer showing values from a field",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the vector layer",
                    },
                    "field_name": {
                        "type": "string",
                        "description": "Field to use for label text",
                    },
                    "font_size": {
                        "type": "number",
                        "description": "Font size in points (default 10)",
                        "default": 10,
                    },
                    "color": {
                        "type": "string",
                        "description": "Text color as hex (default #000000)",
                        "default": "#000000",
                    },
                    "placement": {
                        "type": "string",
                        "description": "Label placement: auto, over, above, below, left, right (default auto)",
                        "default": "auto",
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable or disable labels (default true)",
                        "default": True,
                    },
                },
                "required": ["layer_name", "field_name"],
            },
        ),
        types.Tool(
            name="set_graduated_renderer",
            description="Apply a graduated symbol renderer to a vector layer with growing circles scaled by a numeric field",
            inputSchema={
                "type": "object",
                "properties": {
                    "layer_name": {
                        "type": "string",
                        "description": "Name of the vector layer",
                    },
                    "field_name": {
                        "type": "string",
                        "description": "Numeric field to classify (default: pop_2024)",
                        "default": "pop_2024",
                    },
                    "classes": {
                        "type": "integer",
                        "description": "Number of classes (default 5)",
                        "default": 5,
                    },
                    "min_size": {
                        "type": "number",
                        "description": "Minimum symbol size in mm (default 3)",
                        "default": 3,
                    },
                    "max_size": {
                        "type": "number",
                        "description": "Maximum symbol size in mm (default 14)",
                        "default": 14,
                    },
                },
                "required": ["layer_name"],
            },
        ),
        types.Tool(
            name="list_algorithms",
            description="List available QGIS processing algorithms, optionally filtered by provider",
            inputSchema={
                "type": "object",
                "properties": {
                    "provider": {
                        "type": "string",
                        "description": "Optional provider filter (e.g. native, gdal, qgis)",
                    },
                },
            },
        ),
        types.Tool(
            name="run_processing",
            description="Run a QGIS processing algorithm via qgis_process. Use list_algorithms first to see available algorithms and their parameters.",
            inputSchema={
                "type": "object",
                "properties": {
                    "algorithm": {
                        "type": "string",
                        "description": "Algorithm ID (e.g. native:buffer, gdal:dissolve)",
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameter values as a JSON object. Use qgis_process help <algorithm> to see required params.",
                        "additionalProperties": True,
                    },
                    "project_path": {
                        "type": "string",
                        "description": "Optional QGIS project file to load before running",
                    },
                },
                "required": ["algorithm", "params"],
            },
        ),
    ]
    return tools


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent]:
    if not QGIS_AVAILABLE:
        return [types.TextContent(type="text", text="QGIS Python bindings not available. Install QGIS or run in a QGIS Python environment.")]

    err = init_qgis()
    if err:
        return [types.TextContent(type="text", text=err)]

    project = get_project()

    if name == "get_project_info":
        return await _get_project_info(project)
    elif name == "list_layers":
        return await _list_layers(project)
    elif name == "get_layer_info":
        return await _get_layer_info(project, arguments)
    elif name == "get_layer_features":
        return await _get_layer_features(project, arguments)
    elif name == "run_expression":
        return await _run_expression(arguments)
    elif name == "load_project":
        return await _load_project(arguments)
    elif name == "render_map":
        return await _render_map(project, arguments)
    elif name == "export_layout":
        return await _export_layout(project, arguments)
    elif name == "create_layout":
        return await _create_layout(project, arguments)
    elif name == "add_layer":
        return await _add_layer(project, arguments)
    elif name == "export_layer":
        return await _export_layer(project, arguments)
    elif name == "save_project":
        return await _save_project(project, arguments)
    elif name == "get_layer_statistics":
        return await _get_layer_statistics(project, arguments)
    elif name == "get_unique_values":
        return await _get_unique_values(project, arguments)
    elif name == "count_features":
        return await _count_features(project, arguments)
    elif name == "select_features":
        return await _select_features(project, arguments)
    elif name == "extract_selected":
        return await _extract_selected(project, arguments)
    elif name == "set_layer_crs":
        return await _set_layer_crs(project, arguments)
    elif name == "reproject_layer":
        return await _reproject_layer(project, arguments)
    elif name == "set_project_crs":
        return await _set_project_crs(project, arguments)
    elif name == "get_crs_info":
        return await _get_crs_info(arguments)
    elif name == "list_layouts":
        return await _list_layouts(project)
    elif name == "get_layout_info":
        return await _get_layout_info(project, arguments)
    elif name == "set_layer_labels":
        return await _set_layer_labels(project, arguments)
    elif name == "set_graduated_renderer":
        return await _set_graduated_renderer(project, arguments)
    elif name == "list_algorithms":
        return await _list_algorithms(arguments)
    elif name == "run_processing":
        return await _run_processing(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def _get_project_info(project) -> list[types.TextContent]:
    info = {
        "title": project.title() or "Untitled",
        "file_name": Path(project.fileName()).name if project.fileName() else "Not saved",
        "file_path": project.fileName() or "N/A",
        "crs": project.crs().authid() if project.crs().isValid() else "None",
        "ellipsoid": project.ellipsoid() or "None",
        "layer_count": project.count(),
    }

    extent = project.viewSettings().defaultViewExtent()
    if extent:
        info["extent"] = {
            "xmin": extent.xMinimum(),
            "ymin": extent.yMinimum(),
            "xmax": extent.xMaximum(),
            "ymax": extent.yMaximum(),
        }

    return [types.TextContent(type="text", text=str(info))]


async def _list_layers(project) -> list[types.TextContent]:
    layers = []
    for layer in project.mapLayers().values():
        layer_type = "vector" if layer.type() == 0 else "raster"
        wkt = ""
        if layer_type == "vector":
            wkt = QgsWkbTypes.displayString(layer.wkbType()) if hasattr(layer, "wkbType") else ""
        layers.append({
            "name": layer.name(),
            "type": layer_type,
            "geometry": wkt,
            "crs": layer.crs().authid() if layer.crs().isValid() else "None",
            "visible": True,
            "feature_count": layer.featureCount() if layer_type == "vector" else "N/A",
        })

    return [types.TextContent(type="text", text=str(layers))]


async def _get_layer_info(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: layer_name")]

    layer_name = arguments["layer_name"]
    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]

    info = {
        "name": layer.name(),
        "source": layer.source(),
        "crs": layer.crs().authid() if layer.crs().isValid() else "None",
        "extent": {
            "xmin": layer.extent().xMinimum(),
            "ymin": layer.extent().yMinimum(),
            "xmax": layer.extent().xMaximum(),
            "ymax": layer.extent().yMaximum(),
        },
    }

    if layer.type() == 0:
        vl = layer
        info["type"] = "vector"
        info["geometry"] = QgsWkbTypes.displayString(vl.wkbType())
        info["feature_count"] = vl.featureCount()
        info["fields"] = [
            {"name": f.name(), "type": f.typeName()} for f in vl.fields()
        ]
    else:
        info["type"] = "raster"
        info["width"] = layer.width()
        info["height"] = layer.height()
        info["band_count"] = layer.bandCount()

    return [types.TextContent(type="text", text=str(info))]


async def _get_layer_features(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: layer_name")]

    layer_name = arguments["layer_name"]
    filter_exp = arguments.get("filter", "")
    limit = arguments.get("limit", 100)

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' is not a vector layer.")]

    request = QgsFeatureRequest()
    if filter_exp:
        expr = QgsExpression(filter_exp)
        if expr.hasParserError():
            return [types.TextContent(type="text", text=f"Filter expression error: {expr.parserError()}")]
        request.setFilterExpression(filter_exp)
    request.setLimit(limit)

    features = []
    field_names = [f.name() for f in layer.fields()]
    for feat in layer.getFeatures(request):
        attrs = {name: feat.attribute(name) for name in field_names}
        geom = feat.geometry()
        features.append({
            "id": feat.id(),
            "attributes": attrs,
            "geometry": geom.asWkt() if geom and not geom.isEmpty() else None,
        })

    result = {
        "layer": layer_name,
        "filter": filter_exp or "None",
        "returned": len(features),
        "features": features,
    }
    return [types.TextContent(type="text", text=str(result))]


async def _run_expression(arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "expression" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: expression")]

    expr_str = arguments["expression"]
    expr = QgsExpression(expr_str)
    if expr.hasParserError():
        return [types.TextContent(type="text", text=f"Parse error: {expr.parserError()}")]

    result = expr.evaluate()
    return [types.TextContent(type="text", text=f"Result: {result}")]


async def _load_project(arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "project_path" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: project_path")]

    project_path = arguments["project_path"]
    if not os.path.exists(project_path):
        return [types.TextContent(type="text", text=f"File not found: {project_path}")]

    project = get_project()
    success = project.read(project_path)
    if not success:
        return [types.TextContent(type="text", text=f"Failed to load project: {project_path}")]

    return [types.TextContent(type="text", text=f"Loaded project: {Path(project_path).name}")]


async def _render_map(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "output_path" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: output_path")]

    output_path = arguments["output_path"]
    width = int(arguments.get("width", 1920))
    height = int(arguments.get("height", 1080))
    dpi = int(arguments.get("dpi", 96))
    layer_names = arguments.get("layer_names")

    settings = QgsMapSettings()
    settings.setOutputSize(QSize(width, height))
    settings.setOutputDpi(dpi)

    if layer_names:
        layers = []
        for name in layer_names:
            layer = find_layer(project, name)
            if layer:
                layers.append(layer)
        if not layers:
            return [types.TextContent(type="text", text="No valid layers found matching the provided names.")]
        settings.setLayers(layers)
    else:
        layers = list(project.mapLayers().values())
        settings.setLayers(layers)

    extent = project.viewSettings().defaultViewExtent()
    if extent and not extent.isNull():
        settings.setExtent(extent)
    elif layers:
        settings.setExtent(layers[0].extent())
    else:
        return [types.TextContent(type="text", text="No extent available to render.")]

    settings.setBackgroundColor(QColor(255, 255, 255))
    settings.setOutputImageFormat(QImage.Format_ARGB32)

    job = QgsMapRendererSequentialJob(settings)
    job.start()
    job.waitForFinished()

    image = job.renderedImage()
    image.save(output_path, "PNG")

    file_size = os.path.getsize(output_path)
    return [types.TextContent(type="text", text=f"Map rendered to {output_path} ({width}x{height}, {file_size} bytes)")]


async def _export_layout(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layout_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: layout_name")]
    if "output_path" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: output_path")]

    layout_name = arguments["layout_name"]
    output_path = arguments["output_path"]

    layout_manager = project.layoutManager()
    layout = layout_manager.layoutByName(layout_name)
    if not layout:
        return [types.TextContent(type="text", text=f"Layout '{layout_name}' not found.")]

    exporter = QgsLayoutExporter(layout)
    ext = Path(output_path).suffix.lower()

    if ext == ".pdf":
        result = exporter.exportToPdf(output_path, QgsLayoutExporter.PdfExportSettings())
        if result != QgsLayoutExporter.Success:
            return [types.TextContent(type="text", text=f"PDF export failed with code {result}")]
    elif ext == ".png":
        result = exporter.exportToImage(output_path, QgsLayoutExporter.ImageExportSettings())
        if result != QgsLayoutExporter.Success:
            return [types.TextContent(type="text", text=f"PNG export failed with code {result}")]
    else:
        return [types.TextContent(type="text", text="Unsupported format. Use .pdf or .png")]

    file_size = os.path.getsize(output_path)
    return [types.TextContent(type="text", text=f"Layout '{layout_name}' exported to {output_path} ({file_size} bytes)")]


async def _create_layout(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layout_name" not in arguments or "output_path" not in arguments:
        return [types.TextContent(type="text", text="Missing required arguments: layout_name, output_path")]

    layout_name = arguments["layout_name"]
    output_path = arguments["output_path"]
    page_width = float(arguments.get("page_width", 297))
    page_height = float(arguments.get("page_height", 420))
    dpi = int(arguments.get("dpi", 300))
    add_legend = bool(arguments.get("add_legend", True))
    add_north_arrow = bool(arguments.get("add_north_arrow", True))

    if not Path(output_path).suffix:
        output_path += ".pdf"

    layout_manager = project.layoutManager()
    existing = layout_manager.layoutByName(layout_name)
    if existing:
        layout_manager.removeLayout(existing)

    layout = QgsPrintLayout(project)
    layout.setName(layout_name)
    layout.initializeDefaults()

    pc = layout.pageCollection()
    pc.beginPageSizeChange()
    page = pc.page(0)
    if page:
        page.setPageSize(QgsLayoutSize(page_width, page_height, QgsUnitTypes.LayoutMillimeters))
    pc.endPageSizeChange()

    margin = 20
    legend_height = 35 if add_legend else 0
    map_bottom_margin = margin + legend_height + 10
    map_height = page_height - margin - map_bottom_margin
    map_width = page_width - 2 * margin

    map_item = QgsLayoutItemMap(layout)
    map_item.attemptSetSceneRect(QRectF(margin, margin, map_width, map_height))

    all_layers = list(project.mapLayers().values())
    if all_layers:
        map_item.setLayers(all_layers)
        extent = project.viewSettings().defaultViewExtent()
        if extent and not extent.isNull():
            map_item.setExtent(extent)
        else:
            combined = all_layers[0].extent()
            for l in all_layers[1:]:
                combined.combineExtentWith(l.extent())
            map_item.setExtent(combined)

    layout.addLayoutItem(map_item)

    if add_north_arrow:
        north = QgsLayoutItemPicture(layout)
        north.setPicturePath("/usr/share/qgis/svg/arrows/NorthArrow_01.svg")
        north.setLinkedMap(map_item)
        north.setNorthMode(QgsLayoutItemPicture.GridNorth)
        north_size = 18
        north.attemptSetSceneRect(QRectF(page_width - margin - north_size - 5, margin + 5, north_size, north_size))
        layout.addLayoutItem(north)

    if add_legend:
        legend = QgsLayoutItemLegend(layout)
        legend.setTitle("Legend")
        legend.attemptSetSceneRect(QRectF(margin, page_height - margin - legend_height, page_width - 2 * margin, legend_height))
        layout.addLayoutItem(legend)

    layout_manager.addLayout(layout)

    ext = Path(output_path).suffix.lower()
    exporter = QgsLayoutExporter(layout)

    if ext == ".pdf":
        result = exporter.exportToPdf(output_path, QgsLayoutExporter.PdfExportSettings())
    elif ext == ".png":
        result = exporter.exportToImage(output_path, QgsLayoutExporter.ImageExportSettings())
    else:
        return [types.TextContent(type="text", text="Unsupported format. Use .pdf or .png")]

    if result != QgsLayoutExporter.Success:
        return [types.TextContent(type="text", text=f"Export failed with code {result}")]

    file_size = os.path.getsize(output_path)
    return [types.TextContent(type="text", text=f"Layout '{layout_name}' created and exported to {output_path} ({file_size} bytes)")]


async def _add_layer(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "file_path" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: file_path")]

    file_path = arguments["file_path"]
    if not os.path.exists(file_path):
        return [types.TextContent(type="text", text=f"File not found: {file_path}")]

    layer_name = arguments.get("layer_name", Path(file_path).stem)
    provider = arguments.get("provider", "")

    layer = None
    if provider == "ogr" or not provider:
        layer = QgsVectorLayer(file_path, layer_name, "ogr")
        if not layer or not layer.isValid():
            layer = None

    if not layer and (provider == "gdal" or not provider):
        layer = QgsRasterLayer(file_path, layer_name, "gdal")
        if layer and layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            return [types.TextContent(type="text", text=f"Added raster layer: {layer_name}")]

    if layer and layer.isValid():
        QgsProject.instance().addMapLayer(layer)
        return [types.TextContent(type="text", text=f"Added vector layer: {layer_name} ({layer.featureCount()} features)")]

    return [types.TextContent(type="text", text=f"Failed to load layer from {file_path}. Unsupported or invalid file.")]


async def _export_layer(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: layer_name")]
    if "output_path" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: output_path")]

    layer_name = arguments["layer_name"]
    output_path = arguments["output_path"]
    filter_exp = arguments.get("filter_expression", "")
    target_crs = arguments.get("crs", "")

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' is a raster layer. Only vector layers can be exported.")]

    source = layer
    if filter_exp:
        request = QgsFeatureRequest()
        request.setFilterExpression(filter_exp)
        source = layer.materialize(QgsFields(), request, layer.crs())

    crs = QgsCoordinateReferenceSystem(target_crs) if target_crs else layer.crs()
    if target_crs and not crs.isValid():
        return [types.TextContent(type="text", text=f"Invalid CRS: {target_crs}")]

    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = QgsVectorFileWriter.driverForExtension(Path(output_path).suffix)
    if crs.isValid():
        options.destinationCrs = crs

    transform_context = QgsCoordinateTransformContext()

    error = QgsVectorFileWriter.writeAsVectorFormatV3(
        source, output_path, transform_context, options
    )
    if error[0] != QgsVectorFileWriter.NoError:
        return [types.TextContent(type="text", text=f"Export failed: {error[1]}")]

    file_size = os.path.getsize(output_path)
    return [types.TextContent(type="text", text=f"Layer '{layer_name}' exported to {output_path} ({file_size} bytes)")]


async def _save_project(project, arguments: dict | None) -> list[types.TextContent]:
    output_path = arguments.get("output_path", "") if arguments else ""

    if output_path:
        success = project.write(output_path)
        if not success:
            return [types.TextContent(type="text", text=f"Failed to save project to {output_path}")]
        return [types.TextContent(type="text", text=f"Project saved to {output_path}")]

    if project.fileName():
        success = project.write()
        if not success:
            return [types.TextContent(type="text", text="Failed to save project")]
        return [types.TextContent(type="text", text=f"Project saved to {project.fileName()}")]

    return [types.TextContent(type="text", text="No project file path set. Provide output_path to save.")]


async def _get_layer_statistics(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments or "field_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required arguments: layer_name, field_name")]

    layer_name = arguments["layer_name"]
    field_name = arguments["field_name"]
    filter_exp = arguments.get("filter_expression", "")

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' is not a vector layer.")]

    field_idx = layer.fields().indexOf(field_name)
    if field_idx < 0:
        return [types.TextContent(type="text", text=f"Field '{field_name}' not found in layer '{layer_name}'.")]

    stats = QgsStatisticalSummary()
    request = QgsFeatureRequest()
    if filter_exp:
        request.setFilterExpression(filter_exp)
    for feat in layer.getFeatures(request):
        val = feat.attribute(field_idx)
        if val is not None:
            stats.addValue(float(val))
    stats.finalize()

    result = {
        "layer": layer_name,
        "field": field_name,
        "count": stats.count(),
        "sum": stats.sum(),
        "mean": stats.mean(),
        "min": stats.min(),
        "max": stats.max(),
        "stdev": stats.stDev(),
    }
    return [types.TextContent(type="text", text=str(result))]


async def _get_unique_values(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments or "field_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required arguments: layer_name, field_name")]

    layer_name = arguments["layer_name"]
    field_name = arguments["field_name"]
    limit = int(arguments.get("limit", 100))

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' is not a vector layer.")]

    field_idx = layer.fields().indexOf(field_name)
    if field_idx < 0:
        return [types.TextContent(type="text", text=f"Field '{field_name}' not found in layer '{layer_name}'.")]

    values = []
    seen = set()
    for feat in layer.getFeatures():
        val = feat.attribute(field_name)
        key = str(val)
        if key not in seen:
            seen.add(key)
            values.append(val)
            if len(values) >= limit:
                break

    result = {
        "layer": layer_name,
        "field": field_name,
        "count": len(values),
        "values": [str(v) for v in values[:limit]],
    }
    return [types.TextContent(type="text", text=str(result))]


async def _count_features(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: layer_name")]

    layer_name = arguments["layer_name"]
    filter_exp = arguments.get("filter_expression", "")

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]

    if filter_exp:
        expr = QgsExpression(filter_exp)
        if expr.hasParserError():
            return [types.TextContent(type="text", text=f"Filter expression error: {expr.parserError()}")]
        count = sum(1 for _ in layer.getFeatures(QgsFeatureRequest().setFilterExpression(filter_exp)))
    else:
        count = layer.featureCount()

    return [types.TextContent(type="text", text=str({"layer": layer_name, "filter": filter_exp or "None", "count": count}))]


async def _extract_selected(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "source_layer" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: source_layer")]

    source_name = arguments["source_layer"]
    new_name = arguments.get("new_layer_name", f"{source_name}_selected")

    layer = find_layer(project, source_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{source_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{source_name}' is not a vector layer.")]

    selected = layer.selectedFeatures()
    if not selected:
        return [types.TextContent(type="text", text=f"No selected features in '{source_name}'.")]

    fields = layer.fields()
    geom_type = QgsWkbTypes.displayString(layer.wkbType())
    crs_authid = layer.crs().authid()

    mem_layer = QgsVectorLayer(f"{geom_type}?crs={crs_authid}", new_name, "memory")
    mem_layer.dataProvider().addAttributes(fields)
    mem_layer.updateFields()

    mem_layer.dataProvider().addFeatures(selected)
    mem_layer.updateExtents()

    QgsProject.instance().addMapLayer(mem_layer)

    return [types.TextContent(type="text", text=str({
        "action": "extracted",
        "source": source_name,
        "new_layer": new_name,
        "feature_count": len(selected),
    }))]


async def _select_features(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments or "method" not in arguments:
        return [types.TextContent(type="text", text="Missing required arguments: layer_name, method")]

    layer_name = arguments["layer_name"]
    method = arguments["method"]
    sel_type = arguments.get("selection_type", "new")

    sel_types = {
        "new": QgsVectorLayer.SetSelection,
        "add": QgsVectorLayer.AddToSelection,
        "remove": QgsVectorLayer.RemoveFromSelection,
        "intersect": QgsVectorLayer.IntersectSelection,
    }
    sel_action = sel_types.get(sel_type, QgsVectorLayer.SetSelection)

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' is not a vector layer.")]

    if method == "by_expression":
        expression = arguments.get("expression", "")
        if not expression:
            return [types.TextContent(type="text", text="Missing 'expression' for by_expression method.")]
        expr = QgsExpression(expression)
        if expr.hasParserError():
            return [types.TextContent(type="text", text=f"Expression error: {expr.parserError()}")]
        layer.selectByExpression(expression, sel_action)
        count = layer.selectedFeatureCount()
        return [types.TextContent(type="text", text=str({
            "method": "by_expression",
            "expression": expression,
            "selected": count,
        }))]

    elif method == "by_location":
        ref_name = arguments.get("select_layer_name", "")
        if not ref_name:
            return [types.TextContent(type="text", text="Missing 'select_layer_name' for by_location method.")]
        ref_layer = find_layer(project, ref_name)
        if not ref_layer:
            return [types.TextContent(type="text", text=f"Reference layer '{ref_name}' not found.")]

        predicate_map = {
            "intersect": 0, "contain": 1, "within": 2, "equal": 3,
            "touch": 4, "overlap": 5, "cross": 6, "disjoint": 7,
        }
        pred = predicate_map.get(arguments.get("predicate", "intersect"), 0)

        from qgis.core import QgsSpatialIndex
        idx = QgsSpatialIndex(ref_layer.getFeatures())
        selected = 0
        request = QgsFeatureRequest()
        for feat in layer.getFeatures(request):
            candidate_geom = feat.geometry()
            if not candidate_geom:
                continue
            if pred == 0:
                matches = idx.intersects(candidate_geom.boundingBox())
                select = False
                for id in matches:
                    ref_feat = ref_layer.getFeature(id)
                    if ref_feat and candidate_geom.intersects(ref_feat.geometry()):
                        select = True
                        break
                if select:
                    layer.select(feat.id())
                    selected += 1
            # For simplicity, only intersect is fully implemented
        if pred != 0:
            import warnings
            warnings.warn(f"Predicate '{arguments.get('predicate', 'intersect')}' not fully implemented, using native:extractbylocation via qgis_process instead")
            return await _run_processing({
                "algorithm": "native:extractbylocation",
                "params": {
                    "INPUT": layer.source(),
                    "PREDICATE": pred,
                    "INTERSECT": ref_layer.source(),
                }
            })

        return [types.TextContent(type="text", text=str({
            "method": "by_location",
            "reference_layer": ref_name,
            "predicate": arguments.get("predicate", "intersect"),
            "selected": selected,
        }))]

    elif method == "by_attribute":
        field = arguments.get("attribute_field", "")
        value = arguments.get("attribute_value", "")
        op = arguments.get("attribute_operator", "=")
        if not field or not value:
            return [types.TextContent(type="text", text="Missing 'attribute_field' or 'attribute_value' for by_attribute method.")]
        op_map = {"=": "=", "!=": "!=", "<": "<", ">": ">", "<=": "<=", ">=": ">=", "like": "LIKE", "not_like": "NOT LIKE"}
        sql_op = op_map.get(op, "=")
        if value.isdigit():
            escaped_value = value
        else:
            escaped_value = f"'{value}'"
        expression = f'"{field}" {sql_op} {escaped_value}'
        count = layer.selectByExpression(expression, sel_action)
        return [types.TextContent(type="text", text=str({
            "method": "by_attribute",
            "field": field,
            "value": value,
            "operator": op,
            "expression": expression,
            "selected": count,
        }))]

    else:
        return [types.TextContent(type="text", text=f"Unknown selection method: {method}. Use: by_expression, by_location, by_attribute")]


async def _set_layer_crs(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments or "crs_id" not in arguments:
        return [types.TextContent(type="text", text="Missing required arguments: layer_name, crs_id")]

    layer_name = arguments["layer_name"]
    crs_id = arguments["crs_id"]

    crs = QgsCoordinateReferenceSystem(crs_id)
    if not crs.isValid():
        return [types.TextContent(type="text", text=f"Invalid CRS: {crs_id}")]

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]

    layer.setCrs(crs)
    return [types.TextContent(type="text", text=str({
        "action": "set_layer_crs",
        "layer": layer_name,
        "crs": crs.authid(),
    }))]


async def _reproject_layer(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments or "target_crs" not in arguments:
        return [types.TextContent(type="text", text="Missing required arguments: layer_name, target_crs")]

    layer_name = arguments["layer_name"]
    target_crs_id = arguments["target_crs"]
    new_name = arguments.get("new_layer_name", f"{layer_name}_reprojected")

    target_crs = QgsCoordinateReferenceSystem(target_crs_id)
    if not target_crs.isValid():
        return [types.TextContent(type="text", text=f"Invalid CRS: {target_crs_id}")]

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' is not a vector layer. Raster reprojection not supported.")]

    request = QgsFeatureRequest()
    request.setDestinationCrs(target_crs, QgsCoordinateTransformContext())
    reprojected = layer.materialize(request)
    if not reprojected:
        return [types.TextContent(type="text", text="Reprojection failed.")]

    reprojected.setName(new_name)
    QgsProject.instance().addMapLayer(reprojected)

    return [types.TextContent(type="text", text=str({
        "action": "reproject_layer",
        "source": layer_name,
        "new_layer": new_name,
        "target_crs": target_crs.authid(),
        "feature_count": reprojected.featureCount(),
    }))]


async def _set_project_crs(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "crs_id" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: crs_id")]

    crs = QgsCoordinateReferenceSystem(arguments["crs_id"])
    if not crs.isValid():
        return [types.TextContent(type="text", text=f"Invalid CRS: {arguments['crs_id']}")]

    project.setCrs(crs)
    return [types.TextContent(type="text", text=str({
        "action": "set_project_crs",
        "crs": crs.authid(),
    }))]


async def _get_crs_info(arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "crs_id" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: crs_id")]

    crs = QgsCoordinateReferenceSystem(arguments["crs_id"])
    if not crs.isValid():
        return [types.TextContent(type="text", text=f"Invalid CRS: {arguments['crs_id']}")]

    info = {
        "id": crs.authid(),
        "description": crs.description(),
        "type": crs.type(),
        "projection_acronym": crs.projectionAcronym(),
        "ellipsoid_acronym": crs.ellipsoidAcronym(),
        "srs_id": crs.srsid(),
        "proj_wkt": crs.toProj(),
        "is_geographic": crs.isGeographic(),
    }
    return [types.TextContent(type="text", text=str(info))]


async def _list_layouts(project) -> list[types.TextContent]:
    layouts = []
    for layout in project.layoutManager().printLayouts():
        layouts.append({
            "name": layout.name(),
            "page_count": layout.pageCollection().pageCount(),
        })
    return [types.TextContent(type="text", text=str(layouts or []))]


async def _get_layout_info(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layout_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: layout_name")]

    layout = project.layoutManager().layoutByName(arguments["layout_name"])
    if not layout:
        return [types.TextContent(type="text", text=f"Layout '{arguments['layout_name']}' not found.")]

    items_info = []
    for item in layout.items():
        items_info.append({
            "type": item.type(),
            "id": item.id(),
            "position": {"x": item.positionWithUnits().x(), "y": item.positionWithUnits().y()},
            "size": {"width": item.sizeWithUnits().width(), "height": item.sizeWithUnits().height()},
        })

    info = {
        "name": layout.name(),
        "page_count": layout.pageCollection().pageCount(),
        "item_count": len(items_info),
        "items": items_info,
    }

    pc = layout.pageCollection()
    if pc.pageCount() > 0:
        page = pc.page(0)
        info["page_size"] = {
            "width": page.pageSize().width(),
            "height": page.pageSize().height(),
        }

    return [types.TextContent(type="text", text=str(info))]


async def _set_layer_labels(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments or "field_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required arguments: layer_name, field_name")]

    layer_name = arguments["layer_name"]
    field_name = arguments["field_name"]
    font_size = float(arguments.get("font_size", 10))
    color_hex = str(arguments.get("color", "#000000"))
    placement = str(arguments.get("placement", "auto"))
    enabled = bool(arguments.get("enabled", True))

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' is not a vector layer.")]

    field_idx = layer.fields().indexOf(field_name)
    if field_idx < 0:
        return [types.TextContent(type="text", text=f"Field '{field_name}' not found in layer '{layer_name}'.")]

    placement_map = {
        "auto": QgsPalLayerSettings.PlacementFlags(QgsPalLayerSettings.AboveLine | QgsPalLayerSettings.BelowLine),
        "over": QgsPalLayerSettings.OverPoint,
        "above": QgsPalLayerSettings.AboveLine,
        "below": QgsPalLayerSettings.BelowLine,
        "left": QgsPalLayerSettings.LeftOfPoint,
        "right": QgsPalLayerSettings.RightOfPoint,
    }
    placement_flags = placement_map.get(placement, placement_map["auto"])

    settings = QgsPalLayerSettings()
    settings.fieldName = field_name
    settings.isExpression = False
    settings.enabled = enabled
    settings.placement = placement_flags
    settings.centroidWhole = True

    try:
        color = QColor(color_hex)
    except Exception:
        color = QColor(0, 0, 0)

    text_format = QgsTextFormat()
    text_format.setFont(QFont("Arial", int(font_size)))
    text_format.setSize(font_size)
    text_format.setSizeUnit(QgsUnitTypes.RenderPoints)
    text_format.setColor(color)

    settings.setFormat(text_format)

    labeling = QgsVectorLayerSimpleLabeling(settings)
    layer.setLabelsEnabled(enabled)
    layer.setLabeling(labeling)
    layer.triggerRepaint()

    return [types.TextContent(type="text", text=str({
        "action": "set_layer_labels",
        "layer": layer_name,
        "field": field_name,
        "font_size": font_size,
        "color": color_hex,
        "placement": placement,
        "enabled": enabled,
    }))]


async def _set_graduated_renderer(project, arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "layer_name" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: layer_name")]

    layer_name = arguments["layer_name"]
    field_name = arguments.get("field_name", "pop_2024")
    classes = int(arguments.get("classes", 5))
    min_size = float(arguments.get("min_size", 3))
    max_size = float(arguments.get("max_size", 14))

    layer = find_layer(project, layer_name)
    if not layer:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' not found.")]
    if layer.type() != 0:
        return [types.TextContent(type="text", text=f"Layer '{layer_name}' is not a vector layer.")]

    geom_type = layer.geometryType()
    is_polygon = geom_type == QgsWkbTypes.PolygonGeometry

    field_idx = layer.fields().indexOf(field_name)
    if field_idx < 0:
        return [types.TextContent(type="text", text=f"Field '{field_name}' not found in layer '{layer_name}'.")]

    min_val = float("inf")
    max_val = float("-inf")
    feat_count = 0
    for feat in layer.getFeatures():
        val = feat.attribute(field_idx)
        if val is not None:
            val = float(val)
            min_val = min(min_val, val)
            max_val = max(max_val, val)
            feat_count += 1

    if feat_count == 0:
        return [types.TextContent(type="text", text=f"No data in field '{field_name}'.")]

    target_layer = layer
    result_name = layer_name

    if is_polygon:
        crs_authid = layer.crs().authid()
        centroid_layer = QgsVectorLayer(f"Point?crs={crs_authid}", f"{layer_name}_centroids", "memory")
        centroid_prov = centroid_layer.dataProvider()
        centroid_prov.addAttributes(layer.fields())
        centroid_layer.updateFields()

        new_features = []
        for feat in layer.getFeatures():
            geom = feat.geometry()
            if geom and not geom.isEmpty():
                centroid = geom.centroid()
                if centroid and not centroid.isEmpty():
                    new_feat = QgsFeature()
                    new_feat.setGeometry(centroid)
                    new_feat.setAttributes(feat.attributes())
                    new_features.append(new_feat)

        centroid_prov.addFeatures(new_features)
        centroid_layer.updateExtents()
        QgsProject.instance().addMapLayer(centroid_layer)
        target_layer = centroid_layer
        result_name = centroid_layer.name()

    colors = [
        QColor(255, 247, 188),
        QColor(254, 217, 118),
        QColor(254, 178, 76),
        QColor(253, 141, 60),
        QColor(240, 59, 32),
        QColor(189, 0, 38),
        QColor(128, 0, 38),
    ]

    ranges = []
    interval = (max_val - min_val) / classes
    size_step = (max_size - min_size) / (classes - 1) if classes > 1 else 0

    for i in range(classes):
        lower = min_val + i * interval
        upper = min_val + (i + 1) * interval if i < classes - 1 else max_val * 1.001

        symbol = QgsSymbol.defaultSymbol(target_layer.geometryType())
        symbol.setSize(min_size + i * size_step)
        symbol.setColor(colors[i % len(colors)])

        label = f"{lower:,.0f} - {upper:,.0f}"
        ranges.append(QgsRendererRange(lower, upper, symbol, label))

    renderer = QgsGraduatedSymbolRenderer(field_name, ranges)
    target_layer.setRenderer(renderer)
    target_layer.triggerRepaint()

    return [types.TextContent(type="text", text=str({
        "action": "set_graduated_renderer",
        "layer": result_name,
        "source_layer": layer_name if is_polygon else layer_name,
        "field": field_name,
        "classes": classes,
        "min": min_val,
        "max": max_val,
        "feature_count": feat_count,
    }))]


async def _list_algorithms(arguments: dict | None) -> list[types.TextContent]:
    import subprocess
    import json
    import shutil

    qp = shutil.which("qgis_process") or "qgis_process"
    provider = arguments.get("provider", "") if arguments else ""

    cmd = [qp, "list", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

    if result.returncode != 0:
        return [types.TextContent(type="text", text=f"Failed to list algorithms: {result.stderr[:500]}")]

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [types.TextContent(type="text", text="Failed to parse qgis_process output")]

    alg_list = []
    for prov_id, prov_data in data.get("providers", {}).items():
        if provider and provider not in prov_id:
            continue
        for alg_id, alg_info in prov_data.get("algorithms", {}).items():
            alg_list.append({
                "id": alg_id,
                "name": alg_info.get("name", ""),
                "group": alg_info.get("group", ""),
                "description": alg_info.get("short_description", ""),
            })

    return [types.TextContent(type="text", text=str({
        "total": len(alg_list),
        "provider_filter": provider or "all",
        "algorithms": alg_list,
    }))]


async def _run_processing(arguments: dict | None) -> list[types.TextContent]:
    if not arguments or "algorithm" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: algorithm")]
    if "params" not in arguments:
        return [types.TextContent(type="text", text="Missing required argument: params")]

    import subprocess
    import json
    import shutil

    algorithm = arguments["algorithm"]
    params = arguments["params"]
    project_path = arguments.get("project_path", "")
    qp = shutil.which("qgis_process") or "qgis_process"

    payload = {"inputs": params, "ellipsoid": "WGS84"}
    if project_path:
        payload["project_path"] = project_path

    cmd = [qp, "run", algorithm, "-"]
    proc = subprocess.run(
        cmd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=600,
    )

    if proc.returncode != 0:
        return [types.TextContent(type="text", text=f"Algorithm failed:\nSTDERR: {proc.stderr[:2000]}\nSTDOUT: {proc.stdout[:2000]}")]

    try:
        output = json.loads(proc.stdout)
    except json.JSONDecodeError:
        output = {"stdout": proc.stdout[:2000]}

    return [types.TextContent(type="text", text=str(output))]


async def amain():
    async with stdio_server() as (read_stream, write_stream):
        err = init_qgis()
        if err:
            print(f"Warning: {err}", file=sys.stderr)
            print("QGIS features will be unavailable. Install QGIS or set QGIS_PREFIX_PATH.", file=sys.stderr)

        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    asyncio.run(amain())
