"""
Graph Visualization System for Workflow Orchestration

This module provides comprehensive graph visualization features including:
- Pipeline graph rendering
- Interactive visualization
- Dependency visualization
- Real-time graph updates
- Export capabilities
- Visual workflow design

Inspired by: Skorche, Dagster, WALKOFF, Apache Airflow
"""

import json
import logging
import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union

try:
    import matplotlib.patches as patches
    import matplotlib.pyplot as plt
    import networkx as nx

    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    import plotly.graph_objects as go
    import plotly.offline as pyo

    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

try:
    from jinja2 import Template

    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False

logger = logging.getLogger(__name__)


class GraphType(Enum):
    """Graph visualization types"""

    PIPELINE = "pipeline"
    DEPENDENCY = "dependency"
    EXECUTION = "execution"
    DATAFLOW = "dataflow"
    TIMELINE = "timeline"


class NodeType(Enum):
    """Node types for visualization"""

    STAGE = "stage"
    JOB = "job"
    WORKFLOW = "workflow"
    TRIGGER = "trigger"
    SCHEDULE = "schedule"
    DATA = "data"
    CONDITION = "condition"
    PARALLEL = "parallel"
    MERGE = "merge"


@dataclass
class GraphNode:
    """Graph node representation"""

    id: str
    name: str
    node_type: NodeType
    position: tuple[float, float] = (0, 0)
    size: tuple[float, float] = (100, 60)
    color: str = "#4CAF50"
    border_color: str = "#2E7D32"
    text_color: str = "#FFFFFF"
    properties: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """Graph edge representation"""

    source: str
    target: str
    edge_type: str = "default"
    color: str = "#666666"
    width: float = 2.0
    style: str = "solid"
    label: str = ""
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphLayout:
    """Graph layout configuration"""

    layout_type: str = (
        "hierarchical"  # hierarchical, force_directed, circular, etc.
    )
    direction: str = "TB"  # TB, LR, BT, RL
    spacing: float = 50.0
    node_spacing: float = 100.0
    level_spacing: float = 150.0
    auto_layout: bool = True


class GraphRenderer:
    """Base graph renderer"""

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []
        self.layout: GraphLayout = GraphLayout()

    def add_node(self, node: GraphNode):
        """Add node to graph"""
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge):
        """Add edge to graph"""
        self.edges.append(edge)

    def remove_node(self, node_id: str):
        """Remove node from graph"""
        if node_id in self.nodes:
            del self.nodes[node_id]
        # Remove associated edges
        self.edges = [
            e for e in self.edges if e.source != node_id and e.target != node_id
        ]

    def update_node_status(self, node_id: str, status: str):
        """Update node status"""
        if node_id in self.nodes:
            self.nodes[node_id].status = status

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get node by ID"""
        return self.nodes.get(node_id)

    def get_edges_for_node(self, node_id: str) -> list[GraphEdge]:
        """Get edges connected to node"""
        return [
            e for e in self.edges if e.source == node_id or e.target == node_id
        ]

    def clear(self):
        """Clear all nodes and edges"""
        self.nodes.clear()
        self.edges.clear()


class MatplotlibRenderer(GraphRenderer):
    """Matplotlib-based graph renderer"""

    def __init__(self, figsize: tuple[int, int] = (12, 8)):
        super().__init__()
        self.figsize = figsize
        self.figure = None
        self.axes = None

    def render(self, title: str = "Workflow Graph") -> Optional[bytes]:
        """Render graph to image bytes"""
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("Matplotlib not available")
            return None

        try:
            # Create figure
            self.figure, self.axes = plt.subplots(figsize=self.figsize)
            self.axes.set_title(title, fontsize=16, fontweight="bold")
            self.axes.set_xlim(-100, 1200)
            self.axes.set_ylim(-100, 800)
            self.axes.axis("off")

            # Draw edges first
            for edge in self.edges:
                self._draw_edge(edge)

            # Draw nodes
            for node in self.nodes.values():
                self._draw_node(node)

            # Save to bytes
            import io

            buffer = io.BytesIO()
            self.figure.savefig(
                buffer, format="png", dpi=150, bbox_inches="tight"
            )
            buffer.seek(0)
            image_bytes = buffer.getvalue()

            plt.close(self.figure)
            return image_bytes

        except Exception as e:
            logger.error(f"Failed to render graph: {e}")
            return None

    def _draw_node(self, node: GraphNode):
        """Draw a node"""
        x, y = node.position
        width, height = node.size

        # Node color based on status
        color_map = {
            "pending": "#FFA726",
            "running": "#42A5F5",
            "completed": "#4CAF50",
            "failed": "#F44336",
            "skipped": "#9E9E9E",
        }
        color = color_map.get(node.status, node.color)

        # Draw rectangle
        rect = patches.Rectangle(
            (x - width / 2, y - height / 2),
            width,
            height,
            linewidth=2,
            edgecolor=node.border_color,
            facecolor=color,
            alpha=0.8,
            zorder=2,
        )
        self.axes.add_patch(rect)

        # Draw text
        self.axes.text(
            x,
            y,
            node.name,
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
            color=node.text_color,
            zorder=3,
        )

        # Draw node type indicator
        type_text = node.node_type.value.upper()
        self.axes.text(
            x,
            y - height / 2 - 10,
            type_text,
            ha="center",
            va="top",
            fontsize=8,
            color="#666666",
            zorder=3,
        )

    def _draw_edge(self, edge: GraphEdge):
        """Draw an edge"""
        source_node = self.nodes.get(edge.source)
        target_node = self.nodes.get(edge.target)

        if not source_node or not target_node:
            return

        x1, y1 = source_node.position
        x2, y2 = target_node.position

        # Draw arrow
        self.axes.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(
                arrowstyle="->",
                color=edge.color,
                lw=edge.width,
                alpha=0.7,
                zorder=1,
            ),
        )

        # Draw edge label if present
        if edge.label:
            mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
            self.axes.text(
                mid_x,
                mid_y,
                edge.label,
                ha="center",
                va="center",
                fontsize=8,
                color=edge.color,
                bbox=dict(
                    boxstyle="round,pad=0.3", facecolor="white", alpha=0.8
                ),
                zorder=4,
            )


class PlotlyRenderer(GraphRenderer):
    """Plotly-based interactive graph renderer"""

    def __init__(self):
        super().__init__()

    def render(
        self, title: str = "Interactive Workflow Graph"
    ) -> Optional[str]:
        """Render interactive graph to HTML"""
        if not PLOTLY_AVAILABLE:
            logger.warning("Plotly not available")
            return None

        try:
            # Prepare node data
            node_x = []
            node_y = []
            node_text = []
            node_colors = []
            node_sizes = []

            for node in self.nodes.values():
                x, y = node.position
                node_x.append(x)
                node_y.append(y)
                node_text.append(
                    f"{node.name}<br>Type: {node.node_type.value}<br>Status: {node.status}"
                )

                # Color based on status
                color_map = {
                    "pending": "#FFA726",
                    "running": "#42A5F5",
                    "completed": "#4CAF50",
                    "failed": "#F44336",
                    "skipped": "#9E9E9E",
                }
                node_colors.append(color_map.get(node.status, node.color))
                node_sizes.append(20)

            # Prepare edge data
            edge_x = []
            edge_y = []

            for edge in self.edges:
                source_node = self.nodes.get(edge.source)
                target_node = self.nodes.get(edge.target)

                if source_node and target_node:
                    x1, y1 = source_node.position
                    x2, y2 = target_node.position

                    edge_x.extend([x1, x2, None])
                    edge_y.extend([y1, y2, None])

            # Create figure
            fig = go.Figure()

            # Add edges
            if edge_x:
                fig.add_trace(
                    go.Scatter(
                        x=edge_x,
                        y=edge_y,
                        mode="lines",
                        line=dict(color="#666666", width=2),
                        hoverinfo="none",
                        showlegend=False,
                    )
                )

            # Add nodes
            fig.add_trace(
                go.Scatter(
                    x=node_x,
                    y=node_y,
                    mode="markers+text",
                    marker=dict(
                        size=node_sizes,
                        color=node_colors,
                        line=dict(color="#2E7D32", width=2),
                    ),
                    text=[node.name for node in self.nodes.values()],
                    textposition="middle center",
                    hovertext=node_text,
                    hoverinfo="text",
                    showlegend=False,
                )
            )

            # Update layout
            fig.update_layout(
                title=title,
                showlegend=False,
                hovermode="closest",
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(
                    showgrid=False, zeroline=False, showticklabels=False
                ),
                yaxis=dict(
                    showgrid=False, zeroline=False, showticklabels=False
                ),
                plot_bgcolor="white",
            )

            # Convert to HTML
            html = pyo.plot(fig, output_type="div", include_plotlyjs=True)
            return html

        except Exception as e:
            logger.error(f"Failed to render interactive graph: {e}")
            return None


class WorkflowVisualizer:
    """Main workflow visualizer"""

    def __init__(self):
        self.renderers = {
            "matplotlib": MatplotlibRenderer(),
            "plotly": PlotlyRenderer(),
        }
        self.current_renderer = "plotly"

    def visualize_workflow(
        self, workflow: dict[str, Any], renderer_type: str = "plotly"
    ) -> Union[str, bytes, None]:
        """Visualize workflow as graph"""
        self.current_renderer = renderer_type
        renderer = self.renderers.get(renderer_type)

        if not renderer:
            logger.error(f"Renderer {renderer_type} not available")
            return None

        # Clear previous graph
        renderer.clear()

        # Convert workflow to graph
        self._workflow_to_graph(workflow, renderer)

        # Auto-layout if enabled
        if renderer.layout.auto_layout:
            self._auto_layout(renderer)

        # Render graph
        return renderer.render(f"Workflow: {workflow.get('name', 'Unknown')}")

    def _workflow_to_graph(
        self, workflow: dict[str, Any], renderer: GraphRenderer
    ):
        """Convert workflow to graph nodes and edges"""
        workflow_name = workflow.get("name", "Unknown")

        # Add workflow node
        workflow_node = GraphNode(
            id="workflow",
            name=workflow_name,
            node_type=NodeType.WORKFLOW,
            position=(400, 50),
            color="#2196F3",
            border_color="#1976D2",
        )
        renderer.add_node(workflow_node)

        # Process jobs
        jobs = workflow.get("jobs", {})
        job_positions = self._calculate_job_positions(jobs)

        for job_name, job_data in jobs.items():
            # Add job node
            job_x, job_y = job_positions[job_name]
            job_node = GraphNode(
                id=f"job_{job_name}",
                name=job_name,
                node_type=NodeType.JOB,
                position=(job_x, job_y),
                color="#FF9800",
                border_color="#F57C00",
            )
            renderer.add_node(job_node)

            # Add edge from workflow to job
            renderer.add_edge(
                GraphEdge(
                    source="workflow",
                    target=f"job_{job_name}",
                    edge_type="contains",
                )
            )

            # Process stages
            stages = job_data.get("stages", [])
            stage_positions = self._calculate_stage_positions(
                stages, job_x, job_y
            )

            for i, stage in enumerate(stages):
                stage_name = stage.get("name", f"stage_{i}")
                stage_x, stage_y = stage_positions[i]

                stage_node = GraphNode(
                    id=f"stage_{job_name}_{i}",
                    name=stage_name,
                    node_type=NodeType.STAGE,
                    position=(stage_x, stage_y),
                    color="#4CAF50",
                    border_color="#2E7D32",
                    properties=stage,
                )
                renderer.add_node(stage_node)

                # Add edge from job to stage
                renderer.add_edge(
                    GraphEdge(
                        source=f"job_{job_name}",
                        target=f"stage_{job_name}_{i}",
                        edge_type="contains",
                    )
                )

                # Add edges between stages if dependencies exist
                if i > 0:
                    renderer.add_edge(
                        GraphEdge(
                            source=f"stage_{job_name}_{i-1}",
                            target=f"stage_{job_name}_{i}",
                            edge_type="depends_on",
                        )
                    )

    def _calculate_job_positions(
        self, jobs: dict[str, Any]
    ) -> dict[str, tuple[float, float]]:
        """Calculate positions for job nodes"""
        positions = {}
        num_jobs = len(jobs)

        if num_jobs == 0:
            return positions

        # Arrange jobs horizontally
        spacing = 200
        start_x = 400 - (num_jobs - 1) * spacing / 2

        for i, job_name in enumerate(jobs.keys()):
            x = start_x + i * spacing
            y = 150
            positions[job_name] = (x, y)

        return positions

    def _calculate_stage_positions(
        self, stages: list[dict[str, Any]], job_x: float, job_y: float
    ) -> list[tuple[float, float]]:
        """Calculate positions for stage nodes within a job"""
        positions = []
        num_stages = len(stages)

        if num_stages == 0:
            return positions

        # Arrange stages vertically below job
        spacing = 80
        start_y = job_y + 100

        for i in range(num_stages):
            x = job_x
            y = start_y + i * spacing
            positions.append((x, y))

        return positions

    def _auto_layout(self, renderer: GraphRenderer):
        """Apply automatic layout to graph"""
        if not MATPLOTLIB_AVAILABLE:
            return

        try:
            # Create NetworkX graph for layout
            G = nx.DiGraph()

            # Add nodes
            for node_id in renderer.nodes:
                G.add_node(node_id)

            # Add edges
            for edge in renderer.edges:
                G.add_edge(edge.source, edge.target)

            # Apply hierarchical layout
            pos = nx.spring_layout(G, k=3, iterations=50)

            # Update node positions
            for node_id, position in pos.items():
                if node_id in renderer.nodes:
                    # Scale and center positions
                    x = position[0] * 300 + 400
                    y = position[1] * 200 + 300
                    renderer.nodes[node_id].position = (x, y)

        except Exception as e:
            logger.error(f"Failed to apply auto layout: {e}")


class DependencyVisualizer:
    """Dependency visualization system"""

    def __init__(self):
        self.visualizer = WorkflowVisualizer()

    def visualize_dependencies(
        self,
        dependencies: dict[str, list[str]],
        title: str = "Dependency Graph",
    ) -> Union[str, bytes, None]:
        """Visualize dependency graph"""
        renderer = self.visualizer.renderers["plotly"]
        renderer.clear()

        # Create nodes for each dependency
        nodes = set()
        for source, targets in dependencies.items():
            nodes.add(source)
            nodes.add_all(targets)

        # Calculate positions
        positions = self._calculate_dependency_positions(dependencies)

        # Add nodes
        for node_name in nodes:
            node = GraphNode(
                id=node_name,
                name=node_name,
                node_type=NodeType.DATA,
                position=positions.get(node_name, (0, 0)),
                color="#9C27B0",
                border_color="#7B1FA2",
            )
            renderer.add_node(node)

        # Add edges
        for source, targets in dependencies.items():
            for target in targets:
                renderer.add_edge(
                    GraphEdge(
                        source=source,
                        target=target,
                        edge_type="depends_on",
                        color="#E91E63",
                    )
                )

        return renderer.render(title)

    def _calculate_dependency_positions(
        self, dependencies: dict[str, list[str]]
    ) -> dict[str, tuple[float, float]]:
        """Calculate positions for dependency nodes"""
        positions = {}

        # Simple circular layout
        nodes = list(
            set().union(
                *[
                    set([source] + targets)
                    for source, targets in dependencies.items()
                ]
            )
        )
        num_nodes = len(nodes)

        for i, node in enumerate(nodes):
            angle = 2 * 3.14159 * i / num_nodes
            radius = 200
            x = 400 + radius * math.cos(angle)
            y = 300 + radius * math.sin(angle)
            positions[node] = (x, y)

        return positions


class TimelineVisualizer:
    """Timeline visualization system"""

    def __init__(self):
        self.visualizer = WorkflowVisualizer()

    def visualize_timeline(
        self,
        execution_data: list[dict[str, Any]],
        title: str = "Execution Timeline",
    ) -> Union[str, bytes, None]:
        """Visualize execution timeline"""
        if not PLOTLY_AVAILABLE:
            return None

        try:
            # Prepare timeline data
            tasks = []
            start_times = []
            end_times = []
            colors = []

            for data in execution_data:
                task_name = data.get("task_name", "Unknown")
                start_time = data.get("start_time")
                end_time = data.get("end_time")
                status = data.get("status", "completed")

                if start_time and end_time:
                    tasks.append(task_name)
                    start_times.append(start_time)
                    end_times.append(end_time)

                    # Color based on status
                    color_map = {
                        "completed": "#4CAF50",
                        "failed": "#F44336",
                        "running": "#42A5F5",
                        "pending": "#FFA726",
                    }
                    colors.append(color_map.get(status, "#9E9E9E"))

            # Create timeline
            fig = go.Figure()

            for i, task in enumerate(tasks):
                fig.add_trace(
                    go.Bar(
                        name=task,
                        y=[task],
                        x=[(end_times[i] - start_times[i]).total_seconds()],
                        orientation="h",
                        marker_color=colors[i],
                        base=start_times[i],
                        hovertemplate=f"<b>{task}</b><br>"
                        + f"Start: {start_times[i]}<br>"
                        + f"End: {end_times[i]}<br>"
                        + f"Duration: {(end_times[i] - start_times[i]).total_seconds():.2f}s<br>"
                        + "<extra></extra>",
                    )
                )

            fig.update_layout(
                title=title,
                xaxis_title="Time",
                yaxis_title="Tasks",
                barmode="overlay",
                height=400,
            )

            return pyo.plot(fig, output_type="div", include_plotlyjs=True)

        except Exception as e:
            logger.error(f"Failed to create timeline: {e}")
            return None


class GraphExporter:
    """Graph export utilities"""

    @staticmethod
    def export_to_dot(graph: GraphRenderer, filename: str):
        """Export graph to DOT format"""
        try:
            with open(filename, "w") as f:
                f.write("digraph workflow {\n")
                f.write("  rankdir=TB;\n")
                f.write("  node [shape=box, style=filled];\n\n")

                # Write nodes
                for node in graph.nodes.values():
                    color = node.color.replace("#", "")
                    f.write(
                        f'  "{node.id}" [label="{node.name}", fillcolor="#{color}"];\n'
                    )

                f.write("\n")

                # Write edges
                for edge in graph.edges:
                    f.write(f'  "{edge.source}" -> "{edge.target}";\n')

                f.write("}\n")

            logger.info(f"Graph exported to {filename}")

        except Exception as e:
            logger.error(f"Failed to export DOT: {e}")

    @staticmethod
    def export_to_json(graph: GraphRenderer, filename: str):
        """Export graph to JSON format"""
        try:
            data = {
                "nodes": [
                    {
                        "id": node.id,
                        "name": node.name,
                        "type": node.node_type.value,
                        "position": node.position,
                        "color": node.color,
                        "status": node.status,
                        "properties": node.properties,
                    }
                    for node in graph.nodes.values()
                ],
                "edges": [
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "type": edge.edge_type,
                        "color": edge.color,
                        "label": edge.label,
                    }
                    for edge in graph.edges
                ],
            }

            with open(filename, "w") as f:
                json.dump(data, f, indent=2)

            logger.info(f"Graph exported to {filename}")

        except Exception as e:
            logger.error(f"Failed to export JSON: {e}")


# Global visualizer instances
workflow_visualizer = WorkflowVisualizer()
dependency_visualizer = DependencyVisualizer()
timeline_visualizer = TimelineVisualizer()


# Convenience functions
def visualize_workflow(
    workflow: dict[str, Any], renderer_type: str = "plotly"
) -> Union[str, bytes, None]:
    """Visualize workflow as graph"""
    return workflow_visualizer.visualize_workflow(workflow, renderer_type)


def visualize_dependencies(
    dependencies: dict[str, list[str]], title: str = "Dependency Graph"
) -> Union[str, bytes, None]:
    """Visualize dependency graph"""
    return dependency_visualizer.visualize_dependencies(dependencies, title)


def visualize_timeline(
    execution_data: list[dict[str, Any]], title: str = "Execution Timeline"
) -> Union[str, bytes, None]:
    """Visualize execution timeline"""
    return timeline_visualizer.visualize_timeline(execution_data, title)


def export_graph(graph: GraphRenderer, filename: str, format: str = "json"):
    """Export graph to file"""
    if format.lower() == "dot":
        GraphExporter.export_to_dot(graph, filename)
    elif format.lower() == "json":
        GraphExporter.export_to_json(graph, filename)
    else:
        logger.error(f"Unsupported export format: {format}")


# Example usage
if __name__ == "__main__":
    # Example workflow
    example_workflow = {
        "name": "Data Processing Pipeline",
        "jobs": {
            "extract": {
                "stages": [
                    {"name": "fetch_data", "type": "python"},
                    {"name": "validate_data", "type": "python"},
                ]
            },
            "transform": {
                "stages": [
                    {"name": "clean_data", "type": "python"},
                    {"name": "aggregate_data", "type": "python"},
                ]
            },
            "load": {
                "stages": [{"name": "save_to_database", "type": "python"}]
            },
        },
    }

    # Visualize workflow
    html = visualize_workflow(example_workflow, "plotly")
    if html:
        with open("workflow_visualization.html", "w") as f:
            f.write(html)
        print("Workflow visualization saved to workflow_visualization.html")
