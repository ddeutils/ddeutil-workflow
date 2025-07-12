# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""BPMN/DMN Support for Visual Workflow Design.

This module provides support for importing and exporting workflows in BPMN/DMN format,
inspired by SpiffWorkflow and WALKOFF. It enables visual workflow design and
sub-workflow support.

Features:
- BPMN XML parsing and workflow conversion
- DMN decision table support
- Sub-workflow execution
- Visual workflow export
- Gateway and event handling

Classes:
    BPMNParser: Parse BPMN XML files
    BPMNExporter: Export workflows to BPMN format
    DMNParser: Parse DMN decision tables
    SubWorkflowStage: Stage for executing sub-workflows
    BPMNWorkflow: BPMN-based workflow representation

Example:
    ```python
    from ddeutil.workflow.bpmn import BPMNParser, BPMNExporter

    # Import BPMN workflow
    parser = BPMNParser()
    workflow = parser.parse_file("workflow.bpmn")

    # Export workflow to BPMN
    exporter = BPMNExporter()
    exporter.export(workflow, "exported_workflow.bpmn")
    ```
"""
from __future__ import annotations

import logging
from pathlib import Path
from threading import Event
from typing import Any, Optional, Union
from xml.etree import ElementTree as ET

from pydantic import BaseModel, Field

from .__types import DictData
from .result import Result
from .workflow import Workflow

logger = logging.getLogger(__name__)


class BPMNElement(BaseModel):
    """Base class for BPMN elements."""

    id: str
    name: Optional[str] = None
    type: str
    position: Optional[dict[str, float]] = None


class BPMNTask(BPMNElement):
    """BPMN Task element."""

    type: str = "task"
    implementation: Optional[str] = None
    input_output: Optional[dict[str, Any]] = None


class BPMNGateway(BPMNElement):
    """BPMN Gateway element."""

    type: str = "gateway"
    gateway_type: str = "exclusive"  # exclusive, inclusive, parallel
    conditions: Optional[list[dict[str, Any]]] = None


class BPMNEvent(BPMNElement):
    """BPMN Event element."""

    type: str = "event"
    event_type: str = "start"  # start, end, intermediate
    trigger_type: Optional[str] = None  # timer, message, signal, etc.


class BPMNSubProcess(BPMNElement):
    """BPMN SubProcess element."""

    type: str = "subprocess"
    workflow_ref: Optional[str] = None
    embedded: bool = False


class BPMNFlow(BaseModel):
    """BPMN Flow element."""

    id: str
    source: str
    target: str
    condition: Optional[str] = None


class BPMNProcess(BaseModel):
    """BPMN Process representation."""

    id: str
    name: Optional[str] = None
    elements: list[BPMNElement] = Field(default_factory=list)
    flows: list[BPMNFlow] = Field(default_factory=list)


class BPMNParser:
    """Parser for BPMN XML files."""

    def __init__(self):
        self.namespaces = {
            "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
            "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
            "dc": "http://www.omg.org/spec/DD/20100524/DC",
            "di": "http://www.omg.org/spec/DD/20100524/DI",
        }

    def parse_file(self, file_path: Union[str, Path]) -> BPMNProcess:
        """Parse a BPMN XML file."""
        tree = ET.parse(file_path)
        root = tree.getroot()
        return self._parse_process(root)

    def parse_string(self, xml_string: str) -> BPMNProcess:
        """Parse BPMN XML from string."""
        root = ET.fromstring(xml_string)
        return self._parse_process(root)

    def _parse_process(self, root: ET.Element) -> BPMNProcess:
        """Parse BPMN process from XML root."""
        # Find the process element
        process_elem = root.find(".//bpmn:process", self.namespaces)
        if process_elem is None:
            raise ValueError("No BPMN process found in XML")

        process = BPMNProcess(
            id=process_elem.get("id", ""), name=process_elem.get("name")
        )

        # Parse elements
        for elem in process_elem:
            element = self._parse_element(elem)
            if element:
                process.elements.append(element)

        # Parse flows
        for flow_elem in process_elem.findall(
            ".//bpmn:sequenceFlow", self.namespaces
        ):
            flow = BPMNFlow(
                id=flow_elem.get("id", ""),
                source=flow_elem.get("sourceRef", ""),
                target=flow_elem.get("targetRef", ""),
                condition=self._parse_condition(flow_elem),
            )
            process.flows.append(flow)

        return process

    def _parse_element(self, elem: ET.Element) -> Optional[BPMNElement]:
        """Parse individual BPMN element."""
        tag = elem.tag.replace(f'{{{self.namespaces["bpmn"]}}}', "")

        if tag == "task":
            return self._parse_task(elem)
        elif tag == "exclusiveGateway":
            return self._parse_gateway(elem, "exclusive")
        elif tag == "inclusiveGateway":
            return self._parse_gateway(elem, "inclusive")
        elif tag == "parallelGateway":
            return self._parse_gateway(elem, "parallel")
        elif tag == "startEvent":
            return self._parse_event(elem, "start")
        elif tag == "endEvent":
            return self._parse_event(elem, "end")
        elif tag == "intermediateCatchEvent":
            return self._parse_event(elem, "intermediate")
        elif tag == "subProcess":
            return self._parse_subprocess(elem)

        return None

    def _parse_task(self, elem: ET.Element) -> BPMNTask:
        """Parse BPMN task element."""
        return BPMNTask(
            id=elem.get("id", ""),
            name=elem.get("name"),
            implementation=elem.get("implementation"),
            input_output=self._parse_input_output(elem),
        )

    def _parse_gateway(
        self, elem: ET.Element, gateway_type: str
    ) -> BPMNGateway:
        """Parse BPMN gateway element."""
        return BPMNGateway(
            id=elem.get("id", ""),
            name=elem.get("name"),
            gateway_type=gateway_type,
            conditions=self._parse_gateway_conditions(elem),
        )

    def _parse_event(self, elem: ET.Element, event_type: str) -> BPMNEvent:
        """Parse BPMN event element."""
        trigger_type = None
        trigger_elem = elem.find(
            ".//bpmn:timerEventDefinition", self.namespaces
        )
        if trigger_elem is not None:
            trigger_type = "timer"

        return BPMNEvent(
            id=elem.get("id", ""),
            name=elem.get("name"),
            event_type=event_type,
            trigger_type=trigger_type,
        )

    def _parse_subprocess(self, elem: ET.Element) -> BPMNSubProcess:
        """Parse BPMN subprocess element."""
        return BPMNSubProcess(
            id=elem.get("id", ""),
            name=elem.get("name"),
            workflow_ref=elem.get("processRef"),
            embedded=True,
        )

    def _parse_input_output(self, elem: ET.Element) -> Optional[dict[str, Any]]:
        """Parse input/output specifications."""
        # Simplified parsing - could be extended for full BPMN input/output
        return None

    def _parse_gateway_conditions(
        self, elem: ET.Element
    ) -> Optional[list[dict[str, Any]]]:
        """Parse gateway conditions."""
        # Simplified parsing - could be extended for full BPMN conditions
        return None

    def _parse_condition(self, elem: ET.Element) -> Optional[str]:
        """Parse flow condition."""
        condition_elem = elem.find(
            ".//bpmn:conditionExpression", self.namespaces
        )
        if condition_elem is not None:
            return condition_elem.text
        return None


class BPMNExporter:
    """Exporter for workflows to BPMN format."""

    def __init__(self):
        self.namespaces = {
            "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
            "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
            "dc": "http://www.omg.org/spec/DD/20100524/DC",
            "di": "http://www.omg.org/spec/DD/20100524/DI",
        }

    def export(self, workflow: Workflow, file_path: Union[str, Path]) -> None:
        """Export workflow to BPMN XML file."""
        process = self._workflow_to_bpmn(workflow)
        root = self._create_bpmn_root()

        # Add process to root
        process_elem = self._create_process_element(process)
        root.append(process_elem)

        # Write to file
        tree = ET.ElementTree(root)
        tree.write(file_path, encoding="utf-8", xml_declaration=True)

    def _workflow_to_bpmn(self, workflow: Workflow) -> BPMNProcess:
        """Convert workflow to BPMN process."""
        process = BPMNProcess(
            id=workflow.name or "workflow", name=workflow.name
        )

        # Convert jobs to BPMN elements
        for job_id, job in workflow.jobs.items():
            # Convert job stages to BPMN tasks
            for stage in job.stages:
                element = self._stage_to_bpmn_element(stage)
                if element:
                    process.elements.append(element)

        return process

    def _stage_to_bpmn_element(self, stage: BaseStage) -> Optional[BPMNElement]:
        """Convert stage to BPMN element."""
        if isinstance(stage, CallStage):
            return BPMNTask(
                id=stage.iden, name=stage.name, implementation=stage.uses
            )
        elif isinstance(stage, TriggerStage):
            return BPMNSubProcess(
                id=stage.iden, name=stage.name, workflow_ref=stage.trigger
            )
        elif isinstance(stage, ParallelStage):
            return BPMNGateway(
                id=stage.iden, name=stage.name, gateway_type="parallel"
            )
        elif isinstance(stage, CaseStage):
            return BPMNGateway(
                id=stage.iden, name=stage.name, gateway_type="exclusive"
            )
        else:
            return BPMNTask(
                id=stage.iden,
                name=stage.name,
                implementation=stage.__class__.__name__,
            )

    def _create_bpmn_root(self) -> ET.Element:
        """Create BPMN root element."""
        root = ET.Element(
            "bpmn:definitions",
            {
                "xmlns:bpmn": self.namespaces["bpmn"],
                "xmlns:bpmndi": self.namespaces["bpmndi"],
                "xmlns:dc": self.namespaces["dc"],
                "xmlns:di": self.namespaces["di"],
                "id": "Definitions_1",
                "targetNamespace": "http://bpmn.io/schema/bpmn",
            },
        )
        return root

    def _create_process_element(self, process: BPMNProcess) -> ET.Element:
        """Create BPMN process element."""
        process_elem = ET.Element("bpmn:process")
        process_elem.set("id", process.id)
        if process.name:
            process_elem.set("name", process.name)

        # Add elements
        for element in process.elements:
            elem = self._create_element_xml(element)
            if elem:
                process_elem.append(elem)

        # Add flows
        for flow in process.flows:
            flow_elem = ET.SubElement(process_elem, "bpmn:sequenceFlow")
            flow_elem.set("id", flow.id)
            flow_elem.set("sourceRef", flow.source)
            flow_elem.set("targetRef", flow.target)
            if flow.condition:
                condition_elem = ET.SubElement(
                    flow_elem, "bpmn:conditionExpression"
                )
                condition_elem.text = flow.condition

        return process_elem

    def _create_element_xml(self, element: BPMNElement) -> Optional[ET.Element]:
        """Create XML element for BPMN element."""
        if isinstance(element, BPMNTask):
            return ET.Element(
                "bpmn:task",
                {"id": element.id, "name": element.name or element.id},
            )
        elif isinstance(element, BPMNGateway):
            gateway_type = element.gateway_type
            if gateway_type == "exclusive":
                return ET.Element(
                    "bpmn:exclusiveGateway",
                    {"id": element.id, "name": element.name or element.id},
                )
            elif gateway_type == "parallel":
                return ET.Element(
                    "bpmn:parallelGateway",
                    {"id": element.id, "name": element.name or element.id},
                )
        elif isinstance(element, BPMNEvent):
            if element.event_type == "start":
                return ET.Element(
                    "bpmn:startEvent",
                    {"id": element.id, "name": element.name or element.id},
                )
            elif element.event_type == "end":
                return ET.Element(
                    "bpmn:endEvent",
                    {"id": element.id, "name": element.name or element.id},
                )
        elif isinstance(element, BPMNSubProcess):
            return ET.Element(
                "bpmn:subProcess",
                {
                    "id": element.id,
                    "name": element.name or element.id,
                    "processRef": element.workflow_ref or "",
                },
            )

        return None


class SubWorkflowStage:
    from .stages import BaseStage


class SubWorkflowStage(BaseStage):
    workflow_ref: str = Field(description="Reference to sub-workflow")
    params: DictData = Field(
        default_factory=dict, description="Parameters for sub-workflow"
    )

    def process(
        self,
        params: DictData,
        run_id: str,
        context: DictData,
        *,
        parent_run_id: Optional[str] = None,
        event: Optional[Event] = None,
    ) -> Result:
        from .workflow import Workflow

        sub_workflow = Workflow.from_conf(self.workflow_ref)
        result = sub_workflow.execute(
            params=self.params, run_id=parent_run_id, event=event
        )
        return result


class DMNParser:
    """Parser for DMN decision tables."""

    def parse_file(self, file_path: Union[str, Path]) -> dict[str, Any]:
        """Parse DMN XML file."""
        # Simplified DMN parsing - could be extended for full DMN support
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Find decision table
        decision_table = root.find(
            ".//{http://www.omg.org/spec/DMN/20191111/MODEL/}decisionTable"
        )
        if decision_table is None:
            raise ValueError("No decision table found in DMN file")

        return self._parse_decision_table(decision_table)

    def _parse_decision_table(self, table_elem: ET.Element) -> dict[str, Any]:
        """Parse DMN decision table."""
        # Simplified implementation
        return {"type": "decision_table", "rules": []}


# Utility functions
def bpmn_to_workflow(bpmn_file: Union[str, Path]) -> Workflow:
    """Convert BPMN file to workflow."""
    parser = BPMNParser()
    process = parser.parse_file(bpmn_file)

    # Convert BPMN process to workflow
    # This is a simplified conversion - could be extended
    workflow = Workflow(name=process.name or process.id, jobs={})

    return workflow


def workflow_to_bpmn(workflow: Workflow, output_file: Union[str, Path]) -> None:
    """Convert workflow to BPMN file."""
    exporter = BPMNExporter()
    exporter.export(workflow, output_file)
