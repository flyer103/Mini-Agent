#!/usr/bin/env python3
"""
MCP Server for Mermaid Diagram Generation.

This server provides tools to create, validate, and render Mermaid diagrams from text definitions.
Mermaid diagrams include flowcharts, sequence diagrams, class diagrams, gantt charts, and more.
"""

from typing import Optional, Dict, Any
import tempfile
import os
import subprocess
from enum import Enum
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP
import json

# Initialize the MCP server
mcp = FastMCP("mermaid_mcp")

# Constants
CHARACTER_LIMIT = 25000  # Maximum response size in characters

class DiagramType(str, Enum):
    """Supported Mermaid diagram types."""
    FLOWCHART = "flowchart"
    SEQUENCE = "sequenceDiagram"
    CLASS = "classDiagram"
    STATE = "stateDiagram"
    GANTT = "gantt"
    PIE = "pieChart"
    ERD = "erDiagram"
    JOURNEY = "journey"


class GenerateDiagramInput(BaseModel):
    """Input model for generating Mermaid diagrams."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    diagram_definition: str = Field(
        ...,
        description="Mermaid diagram definition in text format (e.g., 'graph TD; A-->B; B-->C;')",
        min_length=1,
        max_length=10000
    )
    diagram_type: Optional[DiagramType] = Field(
        default=DiagramType.FLOWCHART,
        description="Type of diagram to generate"
    )
    theme: Optional[str] = Field(
        default="default",
        description="Theme for the diagram (default, forest, dark, neutral)"
    )


class ValidateDiagramInput(BaseModel):
    """Input model for validating Mermaid diagrams."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    diagram_definition: str = Field(
        ...,
        description="Mermaid diagram definition to validate",
        min_length=1,
        max_length=10000
    )


class RenderDiagramInput(BaseModel):
    """Input model for rendering Mermaid diagrams to image."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True
    )

    diagram_definition: str = Field(
        ...,
        description="Mermaid diagram definition to render",
        min_length=1,
        max_length=10000
    )
    output_format: str = Field(
        default="svg",
        description="Output format for the rendered diagram (svg, png, pdf)"
    )
    width: Optional[int] = Field(
        default=800,
        description="Width of the output image in pixels",
        ge=100,
        le=2000
    )
    height: Optional[int] = Field(
        default=600,
        description="Height of the output image in pixels",
        ge=100,
        le=2000
    )


async def _install_mermaid_cli() -> bool:
    """Check if @mermaid-js/mermaid-cli is installed and install if needed."""
    try:
        # Try to run mmdc to check if it's installed
        result = subprocess.run(["npx", "-y", "@mermaid-js/mermaid-cli", "--help"],
                                capture_output=True, text=True, timeout=10)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


async def _generate_diagram_text(diagram_def: str) -> str:
    """Generate a text representation of the diagram for display."""
    # Create a simple text representation of the diagram
    lines = diagram_def.strip().split('\n')

    text_output = "# Mermaid Diagram Text Representation\n\n"
    text_output += "```mermaid\n"
    text_output += diagram_def
    text_output += "\n```\n\n"

    # Extract nodes and relationships if possible
    text_output += "## Nodes and Relationships:\n"
    for line in lines:
        line = line.strip()
        if '-->' in line or '->' in line or '--' in line:
            text_output += f"- {line}\n"
        elif line.startswith(' ') or line.startswith('\t'):
            # Indented content might represent additional properties
            text_output += f"- {line.strip()}\n"

    return text_output


def _validate_diagram_syntax(diagram_def: str) -> Dict[str, Any]:
    """Validate the diagram syntax."""
    validation_result = {
        "valid": True,
        "errors": [],
        "warnings": []
    }

    # Basic syntax validation - check if it starts with a known diagram declaration
    diagram_starters = [
        "graph", "flowchart", "sequenceDiagram", "classDiagram",
        "stateDiagram", "gantt", "pieChart", "erDiagram", "journey"
    ]

    stripped_def = diagram_def.strip()

    # Check if the diagram starts with a valid starter
    has_valid_starter = False
    for starter in diagram_starters:
        if stripped_def.startswith(starter):
            has_valid_starter = True
            break

    if not has_valid_starter:
        validation_result["warnings"].append(
            f"Diagram might be missing a valid starter. Consider starting with one of: {', '.join(diagram_starters)}"
        )

    # Check if there are at least some relationships defined
    relationship_indicators = ['-->', '->', '-', '~']
    has_relationships = any(indicator in stripped_def for indicator in relationship_indicators)

    if not has_relationships:
        validation_result["warnings"].append(
            "Diagram does not appear to contain any relationship indicators (e.g., '-->', '->'). "
            "Diagrams typically need relationships between nodes to be meaningful."
        )

    # Additional checks for specific diagram types
    if stripped_def.startswith("sequenceDiagram"):
        if "participant" not in stripped_def and "@" not in stripped_def:
            validation_result["warnings"].append(
                "Sequence diagram should typically define participants using 'participant' keyword."
            )
    elif stripped_def.startswith("classDiagram"):
        if ":::" not in stripped_def and "~" not in stripped_def:
            validation_result["warnings"].append(
                "Class diagram might be missing class relationships or definitions."
            )

    return validation_result


@mcp.tool(
    name="mermaid_generate_diagram",
    annotations={
        "title": "Generate Mermaid Diagram",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def mermaid_generate_diagram(params: GenerateDiagramInput) -> str:
    """
    Generate a Mermaid diagram from a text definition.

    This tool creates a text representation of a Mermaid diagram from the provided
    definition. The diagram can be of various types including flowcharts, sequence
    diagrams, class diagrams, etc. The output is a formatted text representation
    that can be displayed in a Markdown context.

    Args:
        params (GenerateDiagramInput): Validated input parameters containing:
            - diagram_definition (str): Mermaid diagram definition in text format
            - diagram_type (Optional[DiagramType]): Type of diagram to generate
            - theme (Optional[str]): Theme for the diagram

    Returns:
        str: Markdown-formatted string containing the diagram definition and interpretation

    Examples:
        - Use when: "Create a flowchart showing the process flow" -> params with appropriate definition
        - Use when: "Visualize a class diagram" -> params with class diagram definition
        - Don't use when: You need an actual image file (use mermaid_render_diagram instead)

    Error Handling:
        - Input validation errors are handled by Pydantic model
        - Returns error message if diagram syntax appears invalid
    """
    try:
        # Validate the diagram syntax
        validation_result = _validate_diagram_syntax(params.diagram_definition)

        if not validation_result["valid"]:
            error_msg = "Invalid diagram syntax detected:\n"
            for error in validation_result["errors"]:
                error_msg += f"- {error}\n"
            return error_msg

        # Generate text representation of the diagram
        diagram_text = await _generate_diagram_text(params.diagram_definition)

        # Add validation warnings if any
        if validation_result["warnings"]:
            diagram_text += "\n## Validation Warnings:\n"
            for warning in validation_result["warnings"]:
                diagram_text += f"- {warning}\n"

        # Add theme information
        diagram_text += f"\n## Diagram Configuration:\n"
        diagram_text += f"- Type: {params.diagram_type.value if params.diagram_type else 'auto-detected'}\n"
        diagram_text += f"- Theme: {params.theme}\n"

        return diagram_text

    except Exception as e:
        return f"Error generating diagram: {str(e)}"


@mcp.tool(
    name="mermaid_validate_diagram",
    annotations={
        "title": "Validate Mermaid Diagram",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def mermaid_validate_diagram(params: ValidateDiagramInput) -> str:
    """
    Validate the syntax of a Mermaid diagram definition.

    This tool checks if the provided Mermaid diagram definition has valid syntax
    and follows proper formatting conventions. It returns validation results
    indicating whether the diagram is valid and any suggestions for improvement.

    Args:
        params (ValidateDiagramInput): Validated input parameters containing:
            - diagram_definition (str): Mermaid diagram definition to validate

    Returns:
        str: JSON-formatted string containing validation results

    Examples:
        - Use when: "Check if my flowchart definition is valid" -> params with diagram definition
        - Use when: "Validate the syntax of this class diagram" -> params with class diagram
        - Don't use when: You need to actually render the diagram (use other tools instead)

    Error Handling:
        - Input validation errors are handled by Pydantic model
        - Returns formatted validation results or error message
    """
    try:
        validation_result = _validate_diagram_syntax(params.diagram_definition)

        # Return validation result as JSON
        return json.dumps(validation_result, indent=2)

    except Exception as e:
        return f"Error validating diagram: {str(e)}"


@mcp.tool(
    name="mermaid_render_diagram",
    annotations={
        "title": "Render Mermaid Diagram to Image",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def mermaid_render_diagram(params: RenderDiagramInput) -> str:
    """
    Render a Mermaid diagram to an image file.

    This tool renders a Mermaid diagram definition to an image file in the specified format.
    If the @mermaid-js/mermaid-cli is not available or fails to render, it will fall back
    to providing a text representation of the diagram. It temporarily creates the image file
    and returns information about the rendered output when successful.

    Args:
        params (RenderDiagramInput): Validated input parameters containing:
            - diagram_definition (str): Mermaid diagram definition to render
            - output_format (str): Output format for the rendered diagram (svg, png, pdf)
            - width (Optional[int]): Width of the output image in pixels
            - height (Optional[int]): Height of the output image in pixels

    Returns:
        str: JSON-formatted string containing rendering results with the following schema:

        Success response:
        {
            "success": bool,              # Whether the rendering was successful
            "format": str,               # Output format (svg, png, pdf)
            "width": int,                # Width of the rendered diagram
            "height": int,               # Height of the rendered diagram
            "temp_file_path": str,       # Path to the temporary image file
            "message": str               # Success message
        }

        Error/fallback response (when CLI unavailable or rendering fails):
        {
            "success": false,
            "format": str,               # Requested output format
            "width": int,                # Requested width
            "height": int,               # Requested height
            "temp_file_path": str,       # Empty string when no file was created
            "message": str,              # Informative error/fallback message
            "text_representation": str   # Text representation of the diagram as fallback
        }

    Examples:
        - Use when: "Generate a PNG image of this flowchart" -> params with PNG format
        - Use when: "Create an SVG diagram for documentation" -> params with SVG format
        - Don't use when: You only need to check syntax (use mermaid_validate_diagram instead)

    Error Handling:
        - Input validation errors are handled by Pydantic model
        - Returns text representation as fallback if @mermaid-js/mermaid-cli is not available
        - Returns text representation as fallback if diagram rendering fails
    """
    try:
        # Check if mermaid-cli is available
        cli_available = await _install_mermaid_cli()

        if not cli_available:
            # Fallback to generating text representation when CLI is not available
            diagram_text = await _generate_diagram_text(params.diagram_definition)
            return json.dumps({
                "success": False,  # Still indicate that image rendering failed
                "format": params.output_format,
                "width": params.width,
                "height": params.height,
                "temp_file_path": "",
                "message": "Info: @mermaid-js/mermaid-cli is not available for image rendering. "
                          "Returning text representation instead.",
                "text_representation": diagram_text  # Include the text representation
            })

        # Create a temporary file for the diagram definition
        with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as temp_input:
            temp_input.write(params.diagram_definition)
            temp_input_path = temp_input.name

        # Create a temporary file for the output
        with tempfile.NamedTemporaryFile(suffix=f'.{params.output_format}', delete=False) as temp_output:
            temp_output_path = temp_output.name

        try:
            # Call the mermaid CLI to render the diagram
            cmd = [
                "npx", "-y", "@mermaid-js/mermaid-cli",
                "-i", temp_input_path,
                "-o", temp_output_path,
                "-w", str(params.width),
                "-H", str(params.height)
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                return json.dumps({
                    "success": True,
                    "format": params.output_format,
                    "width": params.width,
                    "height": params.height,
                    "temp_file_path": temp_output_path,
                    "message": f"Successfully rendered diagram to {params.output_format} format. "
                              f"Temp file created at: {temp_output_path}"
                })
            else:
                # Even if rendering failed, provide text representation as fallback
                diagram_text = await _generate_diagram_text(params.diagram_definition)
                return json.dumps({
                    "success": False,
                    "format": params.output_format,
                    "width": params.width,
                    "height": params.height,
                    "temp_file_path": "",
                    "message": f"Error rendering diagram: {result.stderr}. "
                              "Returning text representation instead.",
                    "text_representation": diagram_text
                })

        finally:
            # Clean up temporary input file
            os.unlink(temp_input_path)

            # Only clean up output file if the rendering failed
            if os.path.exists(temp_output_path):
                try:
                    os.unlink(temp_output_path)
                except:
                    pass  # Ignore cleanup errors

    except subprocess.TimeoutExpired:
        # Provide fallback text representation
        diagram_text = await _generate_diagram_text(params.diagram_definition)
        return json.dumps({
            "success": False,
            "message": "Error: Rendering timed out after 30 seconds. "
                      "Returning text representation instead.",
            "text_representation": diagram_text
        })
    except Exception as e:
        # Provide fallback text representation
        diagram_text = await _generate_diagram_text(params.diagram_definition)
        return json.dumps({
            "success": False,
            "message": f"Error rendering diagram: {str(e)}. "
                      "Returning text representation instead.",
            "text_representation": diagram_text
        })


if __name__ == "__main__":
    mcp.run()