"""Graph clustering with Leiden (or Louvain fallback).

Community detection is topology-based — no embeddings, no LLM.
Auto-labels communities using file stems, symbol names, and TF-IDF-like
distinguishing terms.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import networkx as nx


def cluster(G: nx.Graph) -> dict[int, list[str]]:
    """Run community detection on the graph.

    Tries Leiden (graspologic) first, falls back to Louvain (networkx).
    Uses undirected view for community detection algorithms.
    """
    if G.number_of_nodes() == 0:
        return {}

    if G.number_of_nodes() == 1:
        node_id = list(G.nodes())[0]
        return {0: [node_id]}

    # Community detection needs undirected graph
    if isinstance(G, nx.DiGraph):
        UG = G.to_undirected()
    else:
        UG = G

    # Try Leiden first
    try:
        from graspologic.partition import leiden
        partitions = leiden(UG)
        communities: dict[int, list[str]] = {}
        for node_id, comm_id in partitions.items():
            communities.setdefault(comm_id, []).append(node_id)
        return communities
    except (ImportError, Exception):
        pass

    # Fallback to Louvain
    try:
        louvain_comms = nx.community.louvain_communities(UG, seed=42)
        communities = {}
        for i, comm in enumerate(louvain_comms):
            communities[i] = list(comm)
        return communities
    except Exception:
        pass

    return {0: list(G.nodes())}


def _split_large_communities(
    communities: dict[int, list[str]],
    G: nx.Graph,
    max_fraction: float = 0.25,
) -> dict[int, list[str]]:
    """Split communities that are too large (>25% of graph)."""
    total = G.number_of_nodes()
    if total == 0:
        return communities

    if isinstance(G, nx.DiGraph):
        UG = G.to_undirected()
    else:
        UG = G

    max_size = int(total * max_fraction)
    result: dict[int, list[str]] = {}
    next_id = max(communities.keys()) + 1 if communities else 0

    for cid, members in communities.items():
        if len(members) <= max_size or len(members) <= 5:
            result[cid] = members
        else:
            subgraph = UG.subgraph(members)
            try:
                sub_comms = nx.community.louvain_communities(subgraph, seed=42)
                for sub in sub_comms:
                    result[next_id] = list(sub)
                    next_id += 1
            except Exception:
                result[cid] = members

    return result


def score_communities(
    G: nx.Graph,
    communities: dict[int, list[str]],
) -> dict[int, float]:
    """Calculate cohesion score for each community."""
    if isinstance(G, nx.DiGraph):
        UG = G.to_undirected()
    else:
        UG = G

    scores: dict[int, float] = {}
    for cid, members in communities.items():
        if len(members) < 2:
            scores[cid] = 1.0
            continue
        subgraph = UG.subgraph(members)
        internal_edges = subgraph.number_of_edges()
        possible_edges = len(members) * (len(members) - 1) / 2
        scores[cid] = round(internal_edges / possible_edges, 3) if possible_edges > 0 else 0.0
    return scores


def auto_label_communities(
    G: nx.Graph,
    communities: dict[int, list[str]],
) -> dict[int, str]:
    """Generate meaningful labels for communities using distinguishing terms.

    Uses a TF-IDF-like approach: finds terms that appear frequently in THIS
    community but rarely in others, creating genuinely descriptive labels.
    """
    labels: dict[int, str] = {}

    # Step 1: Collect all terms per community
    community_terms: dict[int, list[str]] = {}
    for cid, members in communities.items():
        terms: list[str] = []
        for node_id in members:
            data = G.nodes.get(node_id, {})
            source = data.get("source_file", "")
            label = data.get("label", "")
            ntype = data.get("type", "")
            docstring = data.get("docstring", "") or ""

            # File stems (most distinctive)
            if source:
                stem = Path(source).stem
                if stem not in ("__init__", "__main__", "index", "main", "app", "mod"):
                    terms.append(stem)

            # Symbol names for functions/classes
            if ntype in ("function", "class", "method") and label:
                # Clean label — remove private prefix
                clean = label.lstrip("_").split(".")[-1]
                if len(clean) > 2:
                    terms.append(clean)

            # First meaningful word of docstring
            if docstring and len(docstring) > 10:
                words = docstring.split()[:3]
                for w in words:
                    w = w.strip(".:,;!?").lower()
                    if len(w) > 3 and w not in ("this", "that", "the", "and", "for", "from", "with"):
                        terms.append(w)
                        break

        community_terms[cid] = terms

    # Step 2: Count term frequency across ALL communities (for IDF)
    all_term_counts: Counter = Counter()
    for terms in community_terms.values():
        unique_terms = set(terms)
        for t in unique_terms:
            all_term_counts[t] += 1

    total_communities = len(communities)

    # Step 3: For each community, find the most distinguishing term
    used_labels: set[str] = set()
    for cid, terms in community_terms.items():
        if not terms:
            labels[cid] = f"Group {cid}"
            continue

        # Score each term: TF in this community × IDF across communities
        term_freq = Counter(terms)
        scored: list[tuple[str, float]] = []
        for term, tf in term_freq.items():
            idf = total_communities / max(all_term_counts[term], 1)
            score = tf * idf
            scored.append((term, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Pick the best label — try to be unique
        label_text = ""
        for term, _ in scored[:5]:
            candidate = term.replace("_", " ").replace("-", " ").title()
            if candidate not in used_labels:
                label_text = candidate
                break

        if not label_text:
            # Combine top 2 terms
            if len(scored) >= 2:
                t1 = scored[0][0].replace("_", " ").title()
                t2 = scored[1][0].replace("_", " ").title()
                label_text = f"{t1} + {t2}"
            elif scored:
                label_text = scored[0][0].replace("_", " ").title()
            else:
                label_text = f"Group {cid}"

        if label_text in used_labels:
            label_text = f"{label_text} ({cid})"

        used_labels.add(label_text)
        labels[cid] = label_text

    return labels


def cluster_and_label(G: nx.Graph) -> tuple[dict[int, list[str]], dict[int, str], dict[int, float]]:
    """Full clustering pipeline: detect → split → label → score."""
    communities = cluster(G)
    communities = _split_large_communities(communities, G)
    labels = auto_label_communities(G, communities)
    scores = score_communities(G, communities)
    return communities, labels, scores
