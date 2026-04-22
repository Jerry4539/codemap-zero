"""Export graph to JSON and other formats."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import networkx as nx
from networkx.readwrite import json_graph


def to_json(
    G: nx.DiGraph,
    communities: dict[int, list[str]],
    labels: dict[int, str],
    output_path: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Export graph as JSON (NetworkX node_link format).

    Works on a copy so the original graph is not mutated.
    """
    G_copy = copy.deepcopy(G)

    node_to_comm: dict[str, int] = {}
    for cid, members in communities.items():
        for m in members:
            node_to_comm[m] = cid

    for node_id in G_copy.nodes():
        cid = node_to_comm.get(node_id)
        if cid is not None:
            G_copy.nodes[node_id]["community"] = cid
            G_copy.nodes[node_id]["community_label"] = labels.get(cid, f"Module {cid}")

    data = json_graph.node_link_data(G_copy, edges="links")
    if metadata:
        data["meta"] = metadata
    Path(output_path).write_text(
        json.dumps(data, indent=2, default=str),
        encoding="utf-8",
    )
