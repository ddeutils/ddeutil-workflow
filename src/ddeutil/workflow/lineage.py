# ------------------------------------------------------------------------------
# Copyright (c) 2022 Korawich Anuttra. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root for
# license information.
# ------------------------------------------------------------------------------
"""Data Lineage and Asset Tracking System.

This module provides comprehensive data lineage tracking and asset management
for workflows, inspired by Dagster and Prefect. It tracks data dependencies,
materializations, and provides lineage visualization.

Features:
- Asset definition and tracking
- Data dependency tracking
- Materialization history
- Lineage visualization
- Asset partitioning
- Data freshness monitoring
- Dependency resolution

Classes:
    Asset: Data asset definition
    AssetKey: Unique asset identifier
    AssetMaterialization: Asset materialization record
    AssetDependency: Asset dependency relationship
    LineageTracker: Main lineage tracking system
    AssetPartition: Asset partitioning support

Example:
    ```python
    from ddeutil.workflow.lineage import Asset, LineageTracker

    # Define assets
    raw_data = Asset("raw_data", description="Raw input data")
    processed_data = Asset("processed_data", description="Processed data")

    # Track dependencies
    tracker = LineageTracker()
    tracker.add_asset(raw_data)
    tracker.add_asset(processed_data)
    tracker.add_dependency(processed_data, raw_data)

    # Record materialization
    tracker.record_materialization("processed_data", {"rows": 1000})
    ```
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional, Union

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AssetType(Enum):
    """Asset type enumeration."""

    DATASET = "dataset"
    MODEL = "model"
    FILE = "file"
    DATABASE = "database"
    API = "api"
    CUSTOM = "custom"


class MaterializationStatus(Enum):
    """Materialization status enumeration."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"


@dataclass
class AssetKey:
    """Unique asset identifier."""

    name: str
    namespace: Optional[str] = None

    def __str__(self) -> str:
        if self.namespace:
            return f"{self.namespace}/{self.name}"
        return self.name

    def __hash__(self) -> int:
        return hash(str(self))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, AssetKey):
            return False
        return str(self) == str(other)


class Asset(BaseModel):
    """Data asset definition."""

    key: AssetKey
    description: Optional[str] = None
    asset_type: AssetType = AssetType.DATASET
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    partitions: Optional[list[str]] = None
    freshness_policy: Optional[dict[str, Any]] = None

    class Config:
        arbitrary_types_allowed = True


class AssetMaterialization(BaseModel):
    """Asset materialization record."""

    asset_key: AssetKey
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: MaterializationStatus = MaterializationStatus.SUCCESS
    partition: Optional[str] = None
    run_id: Optional[str] = None
    workflow_name: Optional[str] = None

    class Config:
        arbitrary_types_allowed = True


class AssetDependency(BaseModel):
    """Asset dependency relationship."""

    upstream_asset: AssetKey
    downstream_asset: AssetKey
    dependency_type: str = "data"  # data, metadata, etc.
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        arbitrary_types_allowed = True


@dataclass
class AssetPartition:
    """Asset partitioning information."""

    partition_key: str
    partition_value: str
    metadata: dict[str, Any] = field(default_factory=dict)
    last_materialization: Optional[datetime] = None


class LineageTracker:
    """Main lineage tracking system."""

    def __init__(self, storage_path: Optional[Union[str, Path]] = None):
        self.assets: dict[AssetKey, Asset] = {}
        self.dependencies: list[AssetDependency] = []
        self.materializations: list[AssetMaterialization] = []
        self.storage_path = (
            Path(storage_path) if storage_path else Path("./lineage_data")
        )
        self.storage_path.mkdir(exist_ok=True)

    def add_asset(self, asset: Asset) -> None:
        """Add an asset to the tracker."""
        self.assets[asset.key] = asset
        logger.info(f"Added asset: {asset.key}")

    def get_asset(self, asset_key: Union[str, AssetKey]) -> Optional[Asset]:
        """Get an asset by key."""
        if isinstance(asset_key, str):
            asset_key = AssetKey(asset_key)
        return self.assets.get(asset_key)

    def add_dependency(
        self,
        downstream_asset: Union[str, AssetKey, Asset],
        upstream_asset: Union[str, AssetKey, Asset],
        dependency_type: str = "data",
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Add a dependency between assets."""
        # Convert to AssetKey
        if isinstance(downstream_asset, Asset):
            downstream_key = downstream_asset.key
        elif isinstance(downstream_asset, str):
            downstream_key = AssetKey(downstream_asset)
        else:
            downstream_key = downstream_asset

        if isinstance(upstream_asset, Asset):
            upstream_key = upstream_asset.key
        elif isinstance(upstream_asset, str):
            upstream_key = AssetKey(upstream_asset)
        else:
            upstream_key = upstream_asset

        # Check if assets exist
        if downstream_key not in self.assets:
            raise ValueError(f"Downstream asset {downstream_key} not found")
        if upstream_key not in self.assets:
            raise ValueError(f"Upstream asset {upstream_key} not found")

        dependency = AssetDependency(
            upstream_asset=upstream_key,
            downstream_asset=downstream_key,
            dependency_type=dependency_type,
            metadata=metadata or {},
        )

        self.dependencies.append(dependency)
        logger.info(f"Added dependency: {upstream_key} -> {downstream_key}")

    def record_materialization(
        self,
        asset_key: Union[str, AssetKey],
        metadata: Optional[dict[str, Any]] = None,
        status: MaterializationStatus = MaterializationStatus.SUCCESS,
        partition: Optional[str] = None,
        run_id: Optional[str] = None,
        workflow_name: Optional[str] = None,
    ) -> AssetMaterialization:
        """Record an asset materialization."""
        if isinstance(asset_key, str):
            asset_key = AssetKey(asset_key)

        if asset_key not in self.assets:
            raise ValueError(f"Asset {asset_key} not found")

        materialization = AssetMaterialization(
            asset_key=asset_key,
            metadata=metadata or {},
            status=status,
            partition=partition,
            run_id=run_id,
            workflow_name=workflow_name,
        )

        self.materializations.append(materialization)
        logger.info(f"Recorded materialization: {asset_key} ({status.value})")

        return materialization

    def get_materializations(
        self, asset_key: Union[str, AssetKey], limit: Optional[int] = None
    ) -> list[AssetMaterialization]:
        """Get materializations for an asset."""
        if isinstance(asset_key, str):
            asset_key = AssetKey(asset_key)

        materializations = [
            m for m in self.materializations if m.asset_key == asset_key
        ]

        # Sort by timestamp (newest first)
        materializations.sort(key=lambda x: x.timestamp, reverse=True)

        if limit:
            materializations = materializations[:limit]

        return materializations

    def get_latest_materialization(
        self, asset_key: Union[str, AssetKey]
    ) -> Optional[AssetMaterialization]:
        """Get the latest materialization for an asset."""
        materializations = self.get_materializations(asset_key, limit=1)
        return materializations[0] if materializations else None

    def get_upstream_assets(
        self, asset_key: Union[str, AssetKey], max_depth: Optional[int] = None
    ) -> set[AssetKey]:
        """Get all upstream assets for a given asset."""
        if isinstance(asset_key, str):
            asset_key = AssetKey(asset_key)

        upstream = set()
        visited = set()

        def _traverse_upstream(current: AssetKey, depth: int = 0):
            if current in visited:
                return
            if max_depth is not None and depth > max_depth:
                return

            visited.add(current)

            for dep in self.dependencies:
                if dep.downstream_asset == current:
                    upstream.add(dep.upstream_asset)
                    _traverse_upstream(dep.upstream_asset, depth + 1)

        _traverse_upstream(asset_key)
        return upstream

    def get_downstream_assets(
        self, asset_key: Union[str, AssetKey], max_depth: Optional[int] = None
    ) -> set[AssetKey]:
        """Get all downstream assets for a given asset."""
        if isinstance(asset_key, str):
            asset_key = AssetKey(asset_key)

        downstream = set()
        visited = set()

        def _traverse_downstream(current: AssetKey, depth: int = 0):
            if current in visited:
                return
            if max_depth is not None and depth > max_depth:
                return

            visited.add(current)

            for dep in self.dependencies:
                if dep.upstream_asset == current:
                    downstream.add(dep.downstream_asset)
                    _traverse_downstream(dep.downstream_asset, depth + 1)

        _traverse_downstream(asset_key)
        return downstream

    def get_lineage_graph(
        self, asset_key: Union[str, AssetKey], max_depth: int = 3
    ) -> dict[str, Any]:
        """Get lineage graph for an asset."""
        if isinstance(asset_key, str):
            asset_key = AssetKey(asset_key)

        nodes = []
        edges = []

        # Get all related assets
        upstream = self.get_upstream_assets(asset_key, max_depth)
        downstream = self.get_downstream_assets(asset_key, max_depth)
        all_assets = {asset_key} | upstream | downstream

        # Create nodes
        for asset in all_assets:
            asset_info = self.assets.get(asset)
            latest_materialization = self.get_latest_materialization(asset)

            node = {
                "id": str(asset),
                "name": asset.name,
                "namespace": asset.namespace,
                "type": (
                    asset_info.asset_type.value if asset_info else "unknown"
                ),
                "description": asset_info.description if asset_info else None,
                "last_materialization": (
                    latest_materialization.timestamp.isoformat()
                    if latest_materialization
                    else None
                ),
                "status": (
                    latest_materialization.status.value
                    if latest_materialization
                    else None
                ),
            }
            nodes.append(node)

        # Create edges
        for dep in self.dependencies:
            if (
                dep.upstream_asset in all_assets
                and dep.downstream_asset in all_assets
            ):
                edge = {
                    "source": str(dep.upstream_asset),
                    "target": str(dep.downstream_asset),
                    "type": dep.dependency_type,
                    "metadata": dep.metadata,
                }
                edges.append(edge)

        return {"nodes": nodes, "edges": edges, "center_asset": str(asset_key)}

    def check_freshness(
        self, asset_key: Union[str, AssetKey]
    ) -> dict[str, Any]:
        """Check asset freshness based on its freshness policy."""
        if isinstance(asset_key, str):
            asset_key = AssetKey(asset_key)

        asset = self.assets.get(asset_key)
        if not asset or not asset.freshness_policy:
            return {"fresh": True, "reason": "No freshness policy defined"}

        latest_materialization = self.get_latest_materialization(asset_key)
        if not latest_materialization:
            return {"fresh": False, "reason": "No materializations found"}

        # Simplified freshness check - could be extended
        max_age_hours = asset.freshness_policy.get("max_age_hours", 24)
        age_hours = (
            datetime.now(timezone.utc) - latest_materialization.timestamp
        ).total_seconds() / 3600

        fresh = age_hours <= max_age_hours
        return {
            "fresh": fresh,
            "age_hours": age_hours,
            "max_age_hours": max_age_hours,
            "last_materialization": latest_materialization.timestamp.isoformat(),
        }

    def save_lineage_data(self) -> None:
        """Save lineage data to storage."""
        data = {
            "assets": {str(k): v.dict() for k, v in self.assets.items()},
            "dependencies": [dep.dict() for dep in self.dependencies],
            "materializations": [mat.dict() for mat in self.materializations],
        }

        with open(self.storage_path / "lineage_data.json", "w") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Saved lineage data to {self.storage_path}")

    def load_lineage_data(self) -> None:
        """Load lineage data from storage."""
        data_file = self.storage_path / "lineage_data.json"
        if not data_file.exists():
            return

        with open(data_file) as f:
            data = json.load(f)

        # Load assets
        for key_str, asset_data in data.get("assets", {}).items():
            key_parts = key_str.split("/", 1)
            if len(key_parts) == 2:
                asset_key = AssetKey(key_parts[1], key_parts[0])
            else:
                asset_key = AssetKey(key_str)

            asset_data["key"] = asset_key
            self.assets[asset_key] = Asset(**asset_data)

        # Load dependencies
        for dep_data in data.get("dependencies", []):
            # Convert string keys back to AssetKey objects
            if isinstance(dep_data.get("upstream_asset"), str):
                upstream_parts = dep_data["upstream_asset"].split("/", 1)
                if len(upstream_parts) == 2:
                    dep_data["upstream_asset"] = AssetKey(
                        upstream_parts[1], upstream_parts[0]
                    )
                else:
                    dep_data["upstream_asset"] = AssetKey(
                        dep_data["upstream_asset"]
                    )

            if isinstance(dep_data.get("downstream_asset"), str):
                downstream_parts = dep_data["downstream_asset"].split("/", 1)
                if len(downstream_parts) == 2:
                    dep_data["downstream_asset"] = AssetKey(
                        downstream_parts[1], downstream_parts[0]
                    )
                else:
                    dep_data["downstream_asset"] = AssetKey(
                        dep_data["downstream_asset"]
                    )

            dependency = AssetDependency(**dep_data)
            self.dependencies.append(dependency)

        # Load materializations
        for mat_data in data.get("materializations", []):
            # Convert string key back to AssetKey object
            if isinstance(mat_data.get("asset_key"), str):
                asset_key_parts = mat_data["asset_key"].split("/", 1)
                if len(asset_key_parts) == 2:
                    mat_data["asset_key"] = AssetKey(
                        asset_key_parts[1], asset_key_parts[0]
                    )
                else:
                    mat_data["asset_key"] = AssetKey(mat_data["asset_key"])

            materialization = AssetMaterialization(**mat_data)
            self.materializations.append(materialization)

        logger.info(f"Loaded lineage data from {data_file}")


# Global lineage tracker instance
lineage_tracker = LineageTracker()


# Utility functions
def track_asset_materialization(
    asset_name: str, metadata: Optional[dict[str, Any]] = None, **kwargs
) -> AssetMaterialization:
    """Convenience function to track asset materialization."""
    return lineage_tracker.record_materialization(
        asset_name, metadata, **kwargs
    )


def get_asset_lineage(asset_name: str, max_depth: int = 3) -> dict[str, Any]:
    """Convenience function to get asset lineage."""
    return lineage_tracker.get_lineage_graph(asset_name, max_depth)
