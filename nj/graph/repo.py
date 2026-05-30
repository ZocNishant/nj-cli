from __future__ import annotations

import re
from datetime import datetime, UTC

from sqlalchemy import func

from nj.db.engine import get_session
from nj.db.models import GraphEdgeORM, GraphNodeORM
from nj.utils.logger import get_logger

logger = get_logger(__name__)


class GraphRepo:
    def __init__(self, db_path: str = "data/nj.db") -> None:
        self.db_path = db_path

    def normalize(self, label: str) -> str:
        return re.sub(r"\s+", " ", label.lower().strip())

    def get_or_create_node(
        self,
        node_type: str,
        label: str,
        properties: dict | None = None,
        source: str = "manual",
    ) -> int:
        normalized = self.normalize(label)
        with get_session(self.db_path) as session:
            existing = (
                session.query(GraphNodeORM)
                .filter(
                    GraphNodeORM.node_type == node_type,
                    GraphNodeORM.label_normalized == normalized,
                )
                .first()
            )
            if existing:
                if properties:
                    existing.properties = {**existing.properties, **properties}
                    existing.updated_at = datetime.now(UTC)
                return existing.id
            node = GraphNodeORM(
                node_type=node_type,
                label=label,
                label_normalized=normalized,
                properties=properties or {},
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
                source=source,
            )
            session.add(node)
            session.flush()
            return node.id

    def get_or_create_edge(
        self,
        from_id: int,
        to_id: int,
        edge_type: str,
        weight: float = 1.0,
        properties: dict | None = None,
        source: str = "manual",
    ) -> int:
        with get_session(self.db_path) as session:
            existing = (
                session.query(GraphEdgeORM)
                .filter(
                    GraphEdgeORM.from_node_id == from_id,
                    GraphEdgeORM.to_node_id == to_id,
                    GraphEdgeORM.edge_type == edge_type,
                )
                .first()
            )
            if existing:
                existing.weight = max(existing.weight, weight)
                if properties:
                    existing.properties = {**existing.properties, **properties}
                return existing.id
            edge = GraphEdgeORM(
                from_node_id=from_id,
                to_node_id=to_id,
                edge_type=edge_type,
                weight=weight,
                properties=properties or {},
                created_at=datetime.now(UTC),
                source=source,
            )
            session.add(edge)
            session.flush()
            return edge.id

    def get_node_by_id(self, node_id: int) -> GraphNodeORM | None:
        with get_session(self.db_path) as session:
            return session.get(GraphNodeORM, node_id)

    def get_nodes_by_type(self, node_type: str) -> list[GraphNodeORM]:
        with get_session(self.db_path) as session:
            rows = (
                session.query(GraphNodeORM)
                .filter(GraphNodeORM.node_type == node_type)
                .all()
            )
            # Detach from session by converting to plain objects
            session.expunge_all()
            return rows

    def get_neighbors(
        self,
        node_id: int,
        edge_type: str | None = None,
    ) -> list[dict]:
        with get_session(self.db_path) as session:
            q = session.query(GraphEdgeORM).filter(
                GraphEdgeORM.from_node_id == node_id
            )
            if edge_type:
                q = q.filter(GraphEdgeORM.edge_type == edge_type)
            edges = q.all()
            result = []
            for edge in edges:
                neighbor = session.get(GraphNodeORM, edge.to_node_id)
                if neighbor:
                    result.append(
                        {
                            "node_id": neighbor.id,
                            "node_type": neighbor.node_type,
                            "label": neighbor.label,
                            "edge_type": edge.edge_type,
                            "weight": edge.weight,
                            "properties": dict(edge.properties or {}),
                        }
                    )
            return result

    def get_graph_stats(self) -> dict:
        with get_session(self.db_path) as session:
            try:
                total_nodes = session.query(GraphNodeORM).count()
                total_edges = session.query(GraphEdgeORM).count()
                node_types: dict[str, int] = {}
                for node_type in [
                    "skill",
                    "company",
                    "role",
                    "project",
                    "technology",
                    "institution",
                    "outcome",
                ]:
                    count = (
                        session.query(GraphNodeORM)
                        .filter(GraphNodeORM.node_type == node_type)
                        .count()
                    )
                    if count > 0:
                        node_types[node_type] = count
                edge_types: dict[str, int] = {}
                rows = (
                    session.query(
                        GraphEdgeORM.edge_type,
                        func.count(GraphEdgeORM.id),
                    )
                    .group_by(GraphEdgeORM.edge_type)
                    .all()
                )
                for et, count in rows:
                    edge_types[et] = count
                return {
                    "total_nodes": total_nodes,
                    "total_edges": total_edges,
                    "node_types": node_types,
                    "edge_types": edge_types,
                }
            except Exception:
                return {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "node_types": {},
                    "edge_types": {},
                }

    def find_path(
        self,
        from_label: str,
        to_label: str,
        max_depth: int = 4,
    ) -> list[dict]:
        with get_session(self.db_path) as session:
            start_nodes = (
                session.query(GraphNodeORM)
                .filter(
                    GraphNodeORM.label_normalized.contains(
                        self.normalize(from_label)
                    )
                )
                .limit(3)
                .all()
            )
            end_nodes = (
                session.query(GraphNodeORM)
                .filter(
                    GraphNodeORM.label_normalized.contains(
                        self.normalize(to_label)
                    )
                )
                .limit(3)
                .all()
            )
            if not start_nodes or not end_nodes:
                return []
            start_id = start_nodes[0].id
            end_ids = {n.id for n in end_nodes}
            visited = {start_id}
            queue: list[list[int]] = [[start_id]]
            while queue:
                path = queue.pop(0)
                current = path[-1]
                if current in end_ids:
                    return self._path_to_dicts(path, session)
                if len(path) >= max_depth:
                    continue
                edges = (
                    session.query(GraphEdgeORM)
                    .filter(GraphEdgeORM.from_node_id == current)
                    .all()
                )
                for edge in edges:
                    if edge.to_node_id not in visited:
                        visited.add(edge.to_node_id)
                        queue.append(path + [edge.to_node_id])
            return []

    def _path_to_dicts(
        self, node_ids: list[int], session
    ) -> list[dict]:
        result = []
        for nid in node_ids:
            node = session.get(GraphNodeORM, nid)
            if node:
                result.append(
                    {
                        "id": node.id,
                        "type": node.node_type,
                        "label": node.label,
                    }
                )
        return result
