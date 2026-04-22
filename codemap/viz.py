"""Interactive HTML dashboard — codemap.html.

Generates a polished single-file HTML dashboard with all data embedded.
Graph-first design with modules sidebar, floating controls, and AI chat.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

_PALETTE = [
    "#6366f1", "#22d3ee", "#f472b6", "#34d399", "#fb923c",
    "#a78bfa", "#facc15", "#f87171", "#2dd4bf", "#818cf8",
    "#c084fc", "#4ade80", "#fbbf24", "#f97316", "#38bdf8",
    "#e879f9", "#a3e635", "#fb7185", "#67e8f9", "#d946ef",
]


def to_html(
    G: nx.DiGraph,
    communities: dict[int, list[str]],
    output_path: str,
    labels: dict[int, str] | None = None,
    scan_results: dict[str, Any] | None = None,
) -> None:
    """Generate the full interactive HTML dashboard (standalone, no server)."""
    if G.number_of_nodes() > 5000:
        raise ValueError(f"Graph has {G.number_of_nodes()} nodes — too large for browser viz.")

    labels = labels or {}
    scan_results = scan_results or {}
    detection = scan_results.get("detection", {})
    cohesion = scan_results.get("cohesion", {})
    gods = scan_results.get("gods", [])
    entry_points = scan_results.get("entry_points", [])
    complexity = scan_results.get("complexity", [])
    surprises = scan_results.get("surprises", [])

    node_comm: dict[str, int] = {}
    for cid, members in communities.items():
        for m in members:
            node_comm[m] = cid

    # ── Graph data ──────────────────────────────────────────────────────
    graph_nodes: list[dict[str, Any]] = []
    for nid, data in G.nodes(data=True):
        cid = node_comm.get(nid, 0)
        graph_nodes.append({
            "id": nid,
            "label": data.get("label", nid),
            "type": data.get("type", "unknown"),
            "community": cid,
            "communityLabel": labels.get(cid, f"Module {cid}"),
            "color": _PALETTE[cid % len(_PALETTE)],
            "sourceFile": data.get("source_file", ""),
            "signature": data.get("signature", ""),
            "docstring": str(data.get("docstring", ""))[:200],
            "degree": G.in_degree(nid) + G.out_degree(nid),
            "inDeg": G.in_degree(nid),
            "outDeg": G.out_degree(nid),
        })

    graph_edges: list[dict[str, Any]] = []
    for u, v, data in G.edges(data=True):
        graph_edges.append({"source": u, "target": v, "relation": data.get("relation", "")})

    # ── Community data ──────────────────────────────────────────────────
    comms_data = []
    for cid, members in sorted(communities.items(), key=lambda x: len(x[1]), reverse=True):
        file_nodes = []
        sym_nodes = []
        for m in members:
            nd = G.nodes.get(m, {})
            item = {"id": m, "label": nd.get("label", m), "type": nd.get("type", ""),
                    "signature": nd.get("signature", ""), "docstring": str(nd.get("docstring", ""))[:120]}
            if nd.get("type") == "file":
                file_nodes.append(item)
            else:
                sym_nodes.append(item)
        comms_data.append({
            "id": cid,
            "label": labels.get(cid, f"Module {cid}"),
            "color": _PALETTE[cid % len(_PALETTE)],
            "size": len(members),
            "cohesion": round(cohesion.get(cid, 0), 3),
            "files": file_nodes,
            "symbols": sym_nodes[:30],
        })

    # ── Template data ───────────────────────────────────────────────────
    page = _HTML_TEMPLATE
    page = page.replace("__PROJECT_NAME__", detection.get("project_name", "Project"))
    page = page.replace("__PROJECT_TYPE__", detection.get("project_type", "unknown"))
    page = page.replace("__PROJECT_DESC__", detection.get("project_description", ""))
    page = page.replace("__TOTAL_FILES__", str(detection.get("total_files", 0)))
    page = page.replace("__TOTAL_LINES__", str(detection.get("total_lines", 0)))
    page = page.replace("__NODE_COUNT__", str(G.number_of_nodes()))
    page = page.replace("__EDGE_COUNT__", str(G.number_of_edges()))
    page = page.replace("__COMMUNITY_COUNT__", str(len(communities)))
    page = page.replace("__FRAMEWORKS_JSON__", json.dumps(detection.get("frameworks", [])))
    page = page.replace("__LANGUAGES_JSON__", json.dumps(detection.get("languages", {})))
    page = page.replace("__FRAMEWORKS_BY_LANGUAGE_JSON__", json.dumps(detection.get("frameworks_by_language", {})))
    page = page.replace("__DEPENDENCIES_BY_ECOSYSTEM_JSON__", json.dumps(detection.get("dependencies_by_ecosystem", {})))
    page = page.replace("__DOCS_SUMMARY_JSON__", json.dumps(detection.get("docs_summary", {})))
    page = page.replace("__GRAPH_NODES_JSON__", json.dumps(graph_nodes))
    page = page.replace("__GRAPH_EDGES_JSON__", json.dumps(graph_edges))
    page = page.replace("__COMMUNITIES_JSON__", json.dumps(comms_data))
    page = page.replace("__GODS_JSON__", json.dumps(gods[:20]))
    page = page.replace("__ENTRY_POINTS_JSON__", json.dumps(entry_points[:10]))
    page = page.replace("__COMPLEXITY_JSON__", json.dumps(complexity[:20]))
    page = page.replace("__SURPRISES_JSON__", json.dumps(surprises[:20]))

    Path(output_path).write_text(page, encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# Full HTML template — graph-first dashboard with modules sidebar, AI chat
# ════════════════════════════════════════════════════════════════════════════

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__PROJECT_NAME__ — codemap-zero</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');

/* ── 1. Variables & Reset ───────────────────────────────────── */
:root{
  --bg:#061118;--surface:#0b1e2b;--card:#112739;--card-hover:#173147;
  --border:#214053;--border-light:#2f5a71;
  --text:#e8f4f7;--dim:#a6c0cc;--muted:#6f93a5;
  --accent:#14b8a6;--accent-light:#2dd4bf;--accent-glow:rgba(20,184,166,.18);
  --cyan:#22d3ee;--green:#34d399;--pink:#f97316;--orange:#fb923c;--red:#f87171;--yellow:#facc15;
  --radius:12px;--radius-sm:8px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Manrope','Segoe UI',-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh;overflow:hidden;position:relative}
body::before{content:'';position:fixed;inset:0;z-index:-2;background:
  radial-gradient(900px 500px at 10% -10%, rgba(45,212,191,.16), transparent 55%),
  radial-gradient(700px 420px at 92% 10%, rgba(249,115,22,.12), transparent 55%),
  linear-gradient(140deg, #061118 0%, #081927 45%, #0b2234 100%)}
body::after{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;opacity:.24;
  background-image:radial-gradient(circle at 1px 1px, rgba(166,192,204,.18) 1px, transparent 0);
  background-size:20px 20px}
::selection{background:var(--accent);color:#fff}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
a{color:var(--accent-light);text-decoration:none}

/* ── 2. Navigation ──────────────────────────────────────────── */
nav{display:flex;align-items:center;padding:0 20px;height:56px;
  background:linear-gradient(180deg,rgba(11,30,43,.94),rgba(11,30,43,.84));border-bottom:1px solid rgba(33,64,83,.8);position:relative;z-index:100;gap:12px;flex-shrink:0;backdrop-filter:blur(12px)}
.nav-brand{display:flex;align-items:center;gap:10px;flex-shrink:0;cursor:pointer}
.nav-brand .icon{width:30px;height:30px;border-radius:8px;
  background:linear-gradient(135deg,var(--accent),var(--cyan));display:flex;align-items:center;justify-content:center;
  font-size:13px;color:#fff;box-shadow:0 2px 8px rgba(99,102,241,.3)}
.nav-brand .icon svg{width:16px;height:16px;fill:none;stroke:#fff;stroke-width:2.5}
.nav-brand h1{font-size:17px;font-weight:700;letter-spacing:-.2px;font-family:'Space Grotesk','Manrope',sans-serif;
  background:linear-gradient(135deg,var(--accent-light),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.view-tabs{display:flex;gap:2px;background:var(--bg);padding:3px;border-radius:10px;flex-shrink:0}
.view-tab{padding:6px 14px;border-radius:8px;font-size:12px;font-weight:500;cursor:pointer;
  color:var(--muted);transition:all .2s;user-select:none;white-space:nowrap;display:flex;align-items:center;gap:5px}
.view-tab:hover{color:var(--dim)}
.view-tab.active{background:linear-gradient(135deg,rgba(20,184,166,.18),rgba(34,211,238,.16));color:var(--text);border:1px solid rgba(45,212,191,.35);box-shadow:inset 0 0 0 1px rgba(45,212,191,.08)}
.view-tab svg{width:13px;height:13px;stroke:currentColor;fill:none;stroke-width:2}
.nav-search{position:relative;flex-shrink:0}
.nav-search input{width:220px;padding:7px 12px 7px 34px;border-radius:8px;border:1px solid var(--border);
  background:var(--bg);color:var(--text);font-size:13px;outline:none;transition:all .2s}
.nav-search input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow);width:280px}
.nav-search .s-icon{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none}
.nav-search .s-icon svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:2}
.nav-search .s-hint{position:absolute;right:10px;top:50%;transform:translateY(-50%);font-size:10px;
  color:var(--muted);padding:2px 6px;border-radius:4px;background:var(--surface);border:1px solid var(--border);pointer-events:none}
.filter-pills{display:flex;gap:3px;background:var(--bg);padding:3px;border-radius:10px;flex-shrink:0}
.filter-pill{padding:6px 13px;border-radius:7px;font-size:12px;font-weight:500;cursor:pointer;
  color:var(--dim);background:transparent;border:none;transition:all .2s;font-family:inherit}
.filter-pill.active{background:var(--accent);color:#fff;box-shadow:0 2px 8px rgba(99,102,241,.25)}
.filter-pill:hover:not(.active){color:var(--text)}
.nav-spacer{flex:1}
.nav-stats{display:flex;gap:6px;flex-shrink:0}
.stat-badge{padding:5px 12px;border-radius:8px;background:var(--bg);border:1px solid var(--border);
  font-size:13px;font-weight:700;color:var(--text);display:flex;align-items:center;gap:5px;white-space:nowrap}
.stat-badge small{font-weight:400;color:var(--muted);font-size:11px}

/* ── 3. Pages ───────────────────────────────────────────────── */
.page{display:none;animation:fadeIn .3s ease}
.page.active{display:flex}
.content-page{display:none;padding:0;animation:fadeIn .3s ease;overflow-y:auto;height:calc(100vh - 56px);width:100%}
.content-page.active{display:block}
.page-body{padding:28px;max-width:1400px;margin:0 auto;width:100%}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
@keyframes slideUp{from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)}}
@keyframes countUp{from{opacity:0;transform:scale(.8)}to{opacity:1;transform:scale(1)}}
@keyframes glowPulse{0%,100%{opacity:.12}50%{opacity:.22}}
@keyframes revealIn{from{opacity:0;transform:translateY(14px) scale(.99)}to{opacity:1;transform:translateY(0) scale(1)}}

.reveal-item{opacity:0;transform:translateY(14px) scale(.99)}
.reveal-item.show{opacity:1;transform:translateY(0) scale(1);transition:opacity .45s ease,transform .45s ease}

/* ── 4. Graph View ──────────────────────────────────────────── */
.graph-layout{display:flex;height:calc(100vh - 56px);overflow:hidden;width:100%}
.modules-sidebar{width:260px;background:var(--surface);border-right:1px solid var(--border);
  overflow-y:auto;flex-shrink:0;display:flex;flex-direction:column}
.sidebar-head{padding:16px 20px 10px;display:flex;align-items:center;justify-content:space-between}
.sidebar-head h4{font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);font-weight:700}
.sidebar-head .sidebar-count{font-size:10px;color:var(--muted);padding:2px 7px;border-radius:10px;background:var(--bg);border:1px solid var(--border)}
.sidebar-list{flex:1;overflow-y:auto;padding:0 0 12px}
.module-item{display:flex;align-items:center;gap:12px;padding:9px 20px;cursor:pointer;transition:all .15s;user-select:none}
.module-item:hover{background:rgba(99,102,241,.06)}
.module-item.active{background:var(--accent-glow);border-right:3px solid var(--accent)}
.module-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;box-shadow:0 0 6px rgba(0,0,0,.3)}
.module-name{font-size:13px;font-weight:500;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--dim)}
.module-item:hover .module-name,.module-item.active .module-name{color:var(--text)}
.module-count{font-size:12px;color:var(--muted);font-weight:600;flex-shrink:0;min-width:20px;text-align:right}
.graph-canvas{flex:1;position:relative;background:var(--bg)}
.graph-controls{position:absolute;bottom:24px;left:24px;display:flex;gap:4px;
  background:rgba(15,23,42,.88);backdrop-filter:blur(12px);padding:6px;border-radius:14px;
  border:1px solid var(--border);z-index:20;box-shadow:0 4px 24px rgba(0,0,0,.35)}
.ctrl-btn{width:40px;height:40px;border-radius:10px;border:none;background:transparent;
  color:var(--dim);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s;font-size:16px}
.ctrl-btn:hover{background:var(--card);color:var(--text)}
.ctrl-btn.active{background:linear-gradient(135deg,var(--yellow),var(--orange));color:#000}
.ctrl-btn svg{width:18px;height:18px;stroke:currentColor;fill:none;stroke-width:2}
.graph-legend{position:absolute;bottom:80px;left:24px;background:rgba(15,23,42,.95);backdrop-filter:blur(12px);
  padding:16px 18px;border-radius:12px;border:1px solid var(--border);z-index:20;display:none;min-width:220px;
  box-shadow:0 8px 32px rgba(0,0,0,.4)}
.graph-legend.show{display:block}
.legend-title{font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);font-weight:600;margin-bottom:10px}
.legend-item{display:flex;align-items:center;gap:10px;padding:4px 0;font-size:12px;color:var(--dim)}
.legend-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.legend-shape{font-size:15px;width:18px;text-align:center;flex-shrink:0;color:var(--dim)}
.legend-divider{height:1px;background:var(--border);margin:8px 0}

/* Node detail panel */
.node-panel{position:absolute;top:16px;right:16px;width:340px;background:rgba(17,24,39,.95);
  backdrop-filter:blur(16px);border:1px solid var(--border);border-radius:var(--radius);
  padding:0;z-index:10;display:none;animation:slideUp .25s ease;max-height:calc(100% - 32px);overflow-y:auto;
  box-shadow:0 8px 32px rgba(0,0,0,.4)}
.node-panel.show{display:block}
.node-panel-head{padding:18px 20px;border-bottom:1px solid var(--border);position:relative}
.node-panel-head h4{font-size:15px;font-weight:700;padding-right:28px;line-height:1.3}
.node-panel .close{position:absolute;top:14px;right:14px;width:26px;height:26px;border-radius:7px;border:none;
  background:var(--card);color:var(--dim);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:13px;transition:all .15s}
.node-panel .close:hover{background:var(--border);color:var(--text)}
.node-panel-body{padding:16px 20px}
.np-row{margin-bottom:14px}
.np-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:5px;font-weight:600}
.np-val{font-size:12px;color:var(--text);line-height:1.5}
.np-val code{background:var(--card);padding:2px 6px;border-radius:4px;font-size:11px;color:var(--cyan);font-family:'Consolas','Fira Code',monospace}
.np-val .sig{font-family:'Consolas','Fira Code',monospace;font-size:11px;color:var(--green);
  background:var(--card);padding:6px 10px;border-radius:6px;display:block;margin-top:4px;word-break:break-all;border:1px solid var(--border)}
.np-conn{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:6px}
.np-conn-item{text-align:center;padding:8px;border-radius:8px;background:var(--card);border:1px solid var(--border)}
.np-conn-item .conn-val{font-size:18px;font-weight:800;color:var(--accent-light)}
.np-conn-item .conn-label{font-size:9px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-top:2px}

/* ── 5. Page Hero ───────────────────────────────────────────── */
.page-hero{position:relative;padding:40px 36px 32px;overflow:hidden;
  border-bottom:1px solid var(--border);background:var(--surface)}
.page-hero::before{content:'';position:absolute;top:-40%;right:-10%;width:500px;height:500px;
  border-radius:50%;background:radial-gradient(circle,var(--accent-glow),transparent 70%);pointer-events:none;animation:glowPulse 6s ease-in-out infinite}
.page-hero::after{content:'';position:absolute;bottom:-30%;left:20%;width:400px;height:400px;
  border-radius:50%;background:radial-gradient(circle,rgba(34,211,238,.08),transparent 70%);pointer-events:none;animation:glowPulse 8s ease-in-out infinite 2s}
.hero-inner{max-width:1400px;margin:0 auto;position:relative;z-index:1}
.hero-type{display:inline-block;padding:4px 14px;border-radius:20px;font-size:11px;font-weight:700;
  text-transform:uppercase;letter-spacing:1.2px;margin-bottom:14px;
  background:linear-gradient(135deg,var(--accent-glow),rgba(34,211,238,.1));color:var(--accent-light);
  border:1px solid rgba(99,102,241,.2)}
.hero-title{font-size:30px;font-weight:800;letter-spacing:-.5px;line-height:1.2;margin-bottom:10px;
  font-family:'Space Grotesk','Manrope',sans-serif;
  background:linear-gradient(135deg,var(--text) 30%,var(--dim));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.hero-desc{font-size:14px;color:var(--dim);line-height:1.7;max-width:700px;margin-bottom:16px}
.hero-tags{display:flex;gap:8px;flex-wrap:wrap}
.hero-tag{padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;
  background:rgba(52,211,153,.08);color:var(--green);border:1px solid rgba(52,211,153,.15);transition:all .2s}
.hero-tag:hover{background:rgba(52,211,153,.15);transform:translateY(-1px)}
.hero-stats{display:flex;gap:28px;margin-top:20px}
.hero-stat{display:flex;flex-direction:column}
.hero-stat .hs-val{font-size:28px;font-weight:800;line-height:1}
.hero-stat .hs-label{font-size:11px;color:var(--muted);margin-top:4px;text-transform:uppercase;letter-spacing:.8px}

/* ── 6. Section Headers ─────────────────────────────────────── */
.section-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:24px}
.section-head h2{font-size:18px;font-weight:700;display:flex;align-items:center;gap:10px;font-family:'Space Grotesk','Manrope',sans-serif}
.section-head h2 .sec-icon{width:32px;height:32px;border-radius:10px;display:flex;align-items:center;justify-content:center}
.section-head h2 .sec-icon svg{width:16px;height:16px;stroke:#fff;fill:none;stroke-width:2}
.section-actions{display:flex;align-items:center;gap:12px}
.section-count{font-size:12px;color:var(--muted);padding:4px 12px;border-radius:20px;background:var(--card);border:1px solid var(--border)}

/* ── 7. Stat Cards (Overview) ───────────────────────────────── */
.grid{display:grid;gap:20px}
.g2{grid-template-columns:1fr 1fr}
.g3{grid-template-columns:1fr 1fr 1fr}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:1024px){.g3,.g4{grid-template-columns:1fr 1fr}}
@media(max-width:700px){.g2,.g3,.g4{grid-template-columns:1fr}}
.stat-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:24px;position:relative;overflow:hidden;transition:all .3s;cursor:default;backdrop-filter:blur(8px)}
.stat-card:hover{border-color:var(--border-light);transform:translateY(-3px);box-shadow:0 8px 30px rgba(0,0,0,.2)}
.stat-card .glow{position:absolute;top:-30px;right:-30px;width:110px;height:110px;border-radius:50%;opacity:.12;filter:blur(30px);animation:glowPulse 5s ease-in-out infinite}
.stat-card .sc-icon{width:38px;height:38px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:14px}
.stat-card .sc-icon svg{width:18px;height:18px;stroke:#fff;fill:none;stroke-width:2}
.stat-card .label{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);margin-bottom:10px;font-weight:600}
.stat-card .value{font-size:38px;font-weight:800;line-height:1;letter-spacing:-1px;animation:countUp .5s ease}
.stat-card .sub{font-size:12px;color:var(--dim);margin-top:8px;display:flex;align-items:center;gap:5px}
.stat-card .sub .trend{display:inline-flex;align-items:center;gap:2px;font-weight:600;font-size:11px}

/* ── 8. Cards ───────────────────────────────────────────────── */
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:all .2s;backdrop-filter:blur(7px)}
.card:hover{border-color:var(--border-light);box-shadow:0 4px 16px rgba(0,0,0,.1)}
.card-header{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.card-header h3{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--dim);display:flex;align-items:center;gap:8px}
.card-header h3 svg{width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:2}
.card-header .badge{font-size:11px;padding:2px 8px;border-radius:10px;background:var(--accent-glow);color:var(--accent-light);font-weight:600}
.card-body{padding:16px 20px}

/* ── 9. Lists & Bars ───────────────────────────────────────── */
.list-item{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid rgba(55,65,81,.4);transition:background .15s}
.list-item:last-child{border-bottom:none}
.list-item:hover{background:rgba(99,102,241,.03);margin:0 -20px;padding:10px 20px}
.list-rank{width:26px;height:26px;border-radius:8px;display:flex;align-items:center;
  justify-content:center;font-size:11px;font-weight:700;flex-shrink:0}
.list-rank.gold{background:linear-gradient(135deg,#f59e0b,#d97706);color:#fff}
.list-rank.silver{background:linear-gradient(135deg,#94a3b8,#64748b);color:#fff}
.list-rank.bronze{background:linear-gradient(135deg,#b45309,#92400e);color:#fff}
.list-rank.normal{background:var(--surface);color:var(--muted)}
.list-info{flex:1;min-width:0}
.list-info .name{font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.list-info .meta{font-size:11px;color:var(--muted);margin-top:2px}
.list-badge{padding:3px 8px;border-radius:6px;font-size:10px;font-weight:600;text-transform:uppercase;flex-shrink:0}
.list-badge.file{background:rgba(99,102,241,.12);color:var(--accent-light)}
.list-badge.class{background:rgba(244,114,182,.12);color:var(--pink)}
.list-badge.function{background:rgba(52,211,153,.12);color:var(--green)}
.list-badge.method{background:rgba(34,211,238,.12);color:var(--cyan)}
.list-val{font-size:14px;font-weight:700;color:var(--text);flex-shrink:0;min-width:44px;text-align:right}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:10px;animation:slideUp .4s ease both}
.bar-label{font-size:12px;color:var(--dim);width:110px;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.bar-track{flex:1;height:26px;background:var(--surface);border-radius:6px;overflow:hidden;position:relative}
.bar-fill{height:100%;border-radius:6px;transition:width .8s cubic-bezier(.4,0,.2,1);display:flex;align-items:center;padding-left:10px;
  font-size:11px;font-weight:600;color:#fff;min-width:fit-content;position:relative;overflow:hidden}
.bar-fill::after{content:'';position:absolute;top:0;left:0;right:0;bottom:0;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.06),transparent);animation:barShine 3s ease infinite}
@keyframes barShine{0%{transform:translateX(-100%)}100%{transform:translateX(200%)}}
.bar-val{font-size:12px;color:var(--muted);width:50px;text-align:right;flex-shrink:0;font-weight:600}

.chip-cloud{display:flex;flex-wrap:wrap;gap:8px}
.chip{padding:6px 12px;border-radius:999px;font-size:12px;font-weight:600;border:1px solid var(--border);
  background:rgba(20,184,166,.08);color:var(--text)}
.chip.lang{background:rgba(34,211,238,.12);border-color:rgba(34,211,238,.3);color:#bff2ff}
.chip.fw{background:rgba(52,211,153,.12);border-color:rgba(52,211,153,.3);color:#c8ffe3}
.chip.dep{background:rgba(249,115,22,.12);border-color:rgba(249,115,22,.3);color:#ffd8bf}
.tiny-muted{font-size:11px;color:var(--muted)}

/* ── 10. Module Cards ───────────────────────────────────────── */
.mod-search{width:280px;padding:8px 14px 8px 36px;border-radius:8px;border:1px solid var(--border);
  background:var(--bg);color:var(--text);font-size:13px;outline:none;transition:all .2s;font-family:inherit}
.mod-search:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.mod-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:1024px){.mod-grid{grid-template-columns:1fr}}
.mod-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:all .25s}
.mod-card:hover{border-color:var(--border-light);box-shadow:0 10px 24px rgba(0,0,0,.2);transform:translateY(-2px)}
.mod-header{padding:0;display:flex;align-items:stretch;cursor:pointer;user-select:none}
.mod-color-bar{width:5px;flex-shrink:0;transition:width .2s}
.mod-card:hover .mod-color-bar{width:6px}
.mod-header-content{flex:1;display:flex;align-items:center;gap:12px;padding:16px 18px}
.mod-dot{width:12px;height:12px;border-radius:50%;flex-shrink:0;box-shadow:0 0 8px rgba(0,0,0,.3)}
.mod-title{font-size:14px;font-weight:600;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mod-meta{display:flex;gap:10px;font-size:11px;color:var(--muted);align-items:center;flex-shrink:0}
.mod-meta span{display:flex;align-items:center;gap:3px}
.mod-meta svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2}
.mod-chevron{color:var(--muted);transition:transform .25s;font-size:12px;padding:0 14px;display:flex;align-items:center}
.mod-card.open .mod-chevron{transform:rotate(90deg)}
.mod-body{max-height:0;overflow:hidden;transition:max-height .35s ease;border-top:0 solid var(--border)}
.mod-card.open .mod-body{max-height:700px;border-top-width:1px}
.mod-inner{padding:16px 20px}
.cohesion-row{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.cohesion-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.8px;flex-shrink:0}
.cohesion-bar{flex:1;height:6px;background:var(--surface);border-radius:3px;overflow:hidden}
.cohesion-fill{height:100%;border-radius:3px;transition:width .8s cubic-bezier(.4,0,.2,1)}
.cohesion-pct{font-size:12px;font-weight:700;flex-shrink:0;min-width:36px;text-align:right}
.mod-section-label{font-size:10px;color:var(--muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:1px;font-weight:600}
.mod-files{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px}
.mod-file{padding:4px 10px;border-radius:6px;font-size:11px;font-family:'Consolas','Fira Code',monospace;
  background:var(--surface);border:1px solid var(--border);color:var(--dim);transition:all .15s;cursor:default}
.mod-file:hover{border-color:var(--accent);color:var(--text)}
.mod-symbols{margin-top:4px}
.mod-sym{font-size:11px;padding:5px 0;color:var(--dim);font-family:'Consolas','Fira Code',monospace;
  border-bottom:1px solid rgba(55,65,81,.3);display:flex;align-items:center;gap:8px}
.mod-sym:last-child{border-bottom:none}
.mod-sym .sym-type{display:inline-block;padding:1px 6px;border-radius:4px;font-size:9px;text-transform:uppercase;font-weight:600;font-family:inherit}
.mod-sym .sym-type.t-class{background:rgba(244,114,182,.12);color:var(--pink)}
.mod-sym .sym-type.t-function{background:rgba(52,211,153,.12);color:var(--green)}
.mod-sym .sym-type.t-method{background:rgba(34,211,238,.12);color:var(--cyan)}

/* ── 11. Tables ─────────────────────────────────────────────── */
table{width:100%;border-collapse:collapse}
th{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:600;
  padding:12px 14px;text-align:left;border-bottom:2px solid var(--border);background:var(--surface)}
td{padding:12px 14px;font-size:13px;border-bottom:1px solid rgba(55,65,81,.3);transition:background .15s}
tr:hover td{background:rgba(99,102,241,.04)}
td code{background:var(--surface);padding:2px 8px;border-radius:4px;font-size:12px;font-family:'Consolas','Fira Code',monospace}
td .inline-bar{display:inline-block;height:8px;border-radius:4px;vertical-align:middle;margin-left:6px;min-width:4px}
td .score-badge{display:inline-flex;align-items:center;justify-content:center;padding:2px 10px;border-radius:6px;
  font-size:11px;font-weight:700}
td .score-badge.high{background:rgba(248,113,113,.12);color:var(--red)}
td .score-badge.medium{background:rgba(251,146,60,.12);color:var(--orange)}
td .score-badge.low{background:rgba(52,211,153,.12);color:var(--green)}

/* Insight cards */
.insight-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:20px;
  position:relative;overflow:hidden;transition:all .2s;backdrop-filter:blur(8px)}
.insight-card:hover{border-color:var(--border-light);transform:translateY(-2px)}
.insight-card .ic-icon{width:36px;height:36px;border-radius:10px;display:flex;align-items:center;justify-content:center;margin-bottom:12px}
.insight-card .ic-icon svg{width:16px;height:16px;stroke:#fff;fill:none;stroke-width:2}
.insight-card .ic-val{font-size:24px;font-weight:800;line-height:1;margin-bottom:6px}
.insight-card .ic-label{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.8px}

/* Dep items */
.dep-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid rgba(55,65,81,.3);transition:background .15s}
.dep-item:last-child{border-bottom:none}
.dep-item:hover{background:rgba(99,102,241,.03);margin:0 -20px;padding:10px 20px}
.dep-source,.dep-target{font-size:12px;font-weight:500;color:var(--text);flex:1;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-family:'Consolas','Fira Code',monospace}
.dep-source{text-align:right}
.dep-arrow{flex-shrink:0;display:flex;align-items:center;justify-content:center;width:32px}
.dep-arrow svg{width:20px;height:20px;stroke:var(--accent);fill:none;stroke-width:2}
.dep-rel{font-size:10px;padding:2px 8px;border-radius:4px;background:var(--surface);color:var(--muted);flex-shrink:0}
.entry-item{display:flex;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid rgba(55,65,81,.3)}
.entry-item:last-child{border-bottom:none}
.entry-icon{width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0;
  box-shadow:0 0 6px rgba(52,211,153,.4);animation:glowPulse 3s ease-in-out infinite}
.entry-name{font-size:13px;font-family:'Consolas','Fira Code',monospace}
.entry-file{font-size:11px;color:var(--muted);margin-left:auto}

/* ── 12. AI Chat ────────────────────────────────────────────── */
.ai-layout{display:grid;grid-template-columns:300px 1fr;gap:0;height:calc(100vh - 56px);overflow:hidden;width:100%}
@media(max-width:900px){.ai-layout{grid-template-columns:1fr;height:auto}}
.ai-sidebar{background:var(--surface);display:flex;flex-direction:column;border-right:1px solid var(--border);overflow:hidden}
.ai-sidebar-header{padding:16px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}
.ai-sidebar-header .sidebar-icon{width:30px;height:30px;border-radius:9px;
  background:linear-gradient(135deg,var(--accent),var(--cyan));display:flex;align-items:center;justify-content:center}
.ai-sidebar-header .sidebar-icon svg{width:16px;height:16px;stroke:#fff;fill:none;stroke-width:2}
.ai-sidebar-header h3{font-size:14px;font-weight:700;color:var(--text)}
.ai-sidebar-scroll{flex:1;overflow-y:auto;padding:14px 18px;display:flex;flex-direction:column;gap:16px}
.ai-field-group{display:flex;flex-direction:column;gap:5px}
.ai-label{font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);font-weight:600}
.ai-select{width:100%;padding:9px 11px;border-radius:var(--radius-sm);border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:13px;outline:none;cursor:pointer;transition:border .2s;appearance:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 10px center}
.ai-select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.ai-input{width:100%;padding:9px 11px;border-radius:var(--radius-sm);border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:13px;outline:none;transition:border .2s}
.ai-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.ai-key-hint{font-size:10px;color:var(--muted);margin-top:3px;display:flex;align-items:center;gap:4px}
.ai-key-hint svg{width:10px;height:10px;flex-shrink:0;stroke:currentColor;fill:none;stroke-width:2}
.ai-connect-btn{padding:10px;border-radius:var(--radius-sm);border:none;width:100%;
  background:linear-gradient(135deg,var(--accent),var(--cyan));color:#fff;font-size:13px;font-weight:600;
  cursor:pointer;transition:all .2s;letter-spacing:.3px}
.ai-connect-btn:hover{opacity:.9;transform:translateY(-1px);box-shadow:0 4px 12px rgba(99,102,241,.3)}
.ai-connect-btn:active{transform:scale(.98)}
.ai-connect-btn:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}
.ai-status{font-size:12px;min-height:18px;display:flex;align-items:center;gap:6px}
.ai-status.ok{color:var(--green)}.ai-status.err{color:var(--red)}
.ai-status .status-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.ai-status.ok .status-dot{background:var(--green);box-shadow:0 0 6px rgba(52,211,153,.5)}
.ai-status.err .status-dot{background:var(--red)}
.ai-divider{height:1px;background:var(--border);margin:2px 0}
.ai-context-section{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;margin-top:4px}
.ai-context-section h4{font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);font-weight:600;margin-bottom:8px;
  display:flex;align-items:center;gap:5px}
.ai-context-section h4 svg{width:11px;height:11px;stroke:currentColor;fill:none;stroke-width:2}
.ai-ctx-item{display:flex;align-items:center;justify-content:space-between;padding:4px 0;font-size:11px}
.ai-ctx-item .ctx-label{color:var(--muted)}
.ai-ctx-item .ctx-val{color:var(--text);font-weight:600}
.ai-suggestions-section h4{font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);font-weight:600;margin-bottom:8px}
.ai-suggestion{padding:8px 11px;border-radius:var(--radius-sm);font-size:12px;color:var(--dim);line-height:1.4;
  cursor:pointer;transition:all .2s;border:1px solid transparent;margin-bottom:3px;display:flex;align-items:center;gap:6px}
.ai-suggestion::before{content:'\2192';color:var(--accent);font-size:11px;opacity:0;transition:opacity .2s}
.ai-suggestion:hover{background:var(--card);border-color:var(--border);color:var(--text)}
.ai-suggestion:hover::before{opacity:1}
.ai-sidebar-footer{padding:10px 18px;border-top:1px solid var(--border);font-size:10px;color:var(--muted);text-align:center}
.ai-chat-panel{display:flex;flex-direction:column;background:var(--bg);overflow:hidden}
.ai-chat-header{padding:12px 18px;border-bottom:1px solid var(--border);display:flex;align-items:center;
  justify-content:space-between;background:var(--surface);flex-shrink:0;backdrop-filter:blur(8px)}
.ai-chat-header h3{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--dim);display:flex;align-items:center;gap:8px}
.ai-chat-header .model-badge{font-size:10px;padding:3px 8px;border-radius:6px;background:var(--accent-glow);color:var(--accent-light);font-weight:600}
.ai-chat-actions{display:flex;gap:6px}
.ai-action-btn{padding:5px 10px;border-radius:6px;border:1px solid var(--border);background:var(--card);
  color:var(--dim);font-size:11px;cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:4px}
.ai-action-btn:hover{border-color:var(--accent);color:var(--text)}
.ai-action-btn svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2}
.ai-messages{flex:1;overflow-y:auto;padding:20px;display:flex;flex-direction:column;gap:18px;scroll-behavior:smooth}
.ai-welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100%;text-align:center;color:var(--text);gap:8px}
.ai-welcome-icon{width:70px;height:70px;border-radius:20px;
  background:linear-gradient(135deg,var(--accent-glow),rgba(34,211,238,.1));
  display:flex;align-items:center;justify-content:center;font-size:34px;margin-bottom:6px;
  border:1px solid rgba(99,102,241,.15)}
.ai-welcome h4{font-size:18px;font-weight:700}
.ai-welcome p{color:var(--dim);font-size:13px;max-width:420px;line-height:1.6}
.ai-welcome-features{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:14px;max-width:400px;text-align:left}
.ai-welcome-feat{display:flex;align-items:center;gap:8px;padding:8px 12px;border-radius:8px;background:var(--card);
  border:1px solid var(--border);font-size:12px;color:var(--dim);transition:all .2s}
.ai-welcome-feat:hover{border-color:var(--accent);color:var(--text)}
.ai-welcome-feat svg{width:14px;height:14px;stroke:var(--accent-light);fill:none;stroke-width:2;flex-shrink:0}
.ai-welcome-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:14px;justify-content:center;max-width:500px}
.ai-welcome-chip{padding:7px 14px;border-radius:20px;font-size:12px;color:var(--dim);
  border:1px solid var(--border);cursor:pointer;transition:all .2s}
.ai-welcome-chip:hover{border-color:var(--accent);color:var(--accent-light);background:var(--accent-glow)}
.ai-msg{max-width:78%;animation:msgIn .3s ease;position:relative}
.ai-msg.user{align-self:flex-end}.ai-msg.bot{align-self:flex-start}
@keyframes msgIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.ai-msg-row{display:flex;align-items:flex-end;gap:8px}
.ai-msg.user .ai-msg-row{flex-direction:row-reverse}
.ai-avatar{width:28px;height:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;
  font-size:11px;flex-shrink:0;font-weight:700}
.ai-msg.bot .ai-avatar{background:linear-gradient(135deg,var(--accent),var(--cyan));color:#fff}
.ai-msg.user .ai-avatar{background:var(--card);color:var(--dim);border:1px solid var(--border)}
.ai-msg-bubble{padding:12px 16px;border-radius:16px;font-size:13px;line-height:1.7;word-break:break-word}
.ai-msg.user .ai-msg-bubble{background:linear-gradient(135deg,var(--accent),#7c3aed);color:#fff;
  border-bottom-right-radius:4px;box-shadow:0 6px 16px rgba(20,184,166,.25)}
.ai-msg.bot .ai-msg-bubble{background:var(--card);border:1px solid var(--border);color:var(--text);
  border-bottom-left-radius:4px;box-shadow:0 1px 4px rgba(0,0,0,.1)}
.ai-msg-footer{display:flex;align-items:center;gap:8px;margin-top:4px;padding:0 4px}
.ai-msg-time{font-size:10px;color:var(--muted)}
.ai-msg.user .ai-msg-footer{justify-content:flex-end}
.ai-msg-actions{display:flex;gap:2px;opacity:0;transition:opacity .2s}
.ai-msg:hover .ai-msg-actions{opacity:1}
.ai-msg-action{width:22px;height:22px;border-radius:5px;border:none;background:transparent;
  color:var(--muted);cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all .15s}
.ai-msg-action:hover{background:var(--surface);color:var(--text)}
.ai-msg-action svg{width:12px;height:12px;stroke:currentColor;fill:none;stroke-width:2}
.ai-msg-bubble pre{background:var(--surface);padding:12px;border-radius:8px;overflow-x:auto;font-size:12px;margin:10px 0;
  font-family:'Consolas','Fira Code',monospace;border:1px solid var(--border);position:relative}
.ai-msg-bubble pre .copy-code{position:absolute;top:6px;right:6px;padding:3px 8px;border-radius:4px;
  border:1px solid var(--border);background:var(--card);color:var(--muted);font-size:10px;cursor:pointer;
  opacity:0;transition:opacity .2s}
.ai-msg-bubble pre:hover .copy-code{opacity:1}
.ai-msg-bubble pre .copy-code:hover{color:var(--text);border-color:var(--accent)}
.ai-msg-bubble code{font-family:'Consolas','Fira Code',monospace;font-size:12px;
  background:rgba(99,102,241,.1);padding:1px 5px;border-radius:4px;color:var(--cyan)}
.ai-msg-bubble pre code{background:none;padding:0;color:inherit}
.ai-msg-bubble p{margin:6px 0}.ai-msg-bubble p:first-child{margin-top:0}.ai-msg-bubble p:last-child{margin-bottom:0}
.ai-msg-bubble ul,.ai-msg-bubble ol{margin:8px 0;padding-left:20px}
.ai-msg-bubble li{margin:3px 0}
.ai-msg-bubble strong{color:var(--accent-light)}
.ai-msg-bubble h1,.ai-msg-bubble h2,.ai-msg-bubble h3{font-size:14px;font-weight:700;margin:10px 0 6px;color:var(--text)}
.ai-typing{display:flex;gap:5px;padding:4px 0}
.ai-typing span{width:7px;height:7px;border-radius:50%;background:var(--accent-light);animation:typing 1.4s infinite}
.ai-typing span:nth-child(2){animation-delay:.2s}
.ai-typing span:nth-child(3){animation-delay:.4s}
@keyframes typing{0%,70%,100%{opacity:.25;transform:scale(.85)}35%{opacity:1;transform:scale(1.1)}}
.ai-input-bar{display:flex;gap:8px;padding:12px 18px;border-top:1px solid var(--border);
  background:var(--surface);align-items:flex-end;flex-shrink:0}
.ai-msg-input{flex:1;padding:10px 16px;border-radius:20px;border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:13px;outline:none;transition:all .2s;
  max-height:120px;resize:none;line-height:1.5;font-family:inherit;overflow-y:auto}
.ai-msg-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.ai-msg-input:disabled{opacity:.4}
.ai-msg-input::placeholder{color:var(--muted)}
.ai-send-btn{width:38px;height:38px;border-radius:50%;border:none;
  background:linear-gradient(135deg,var(--accent),var(--cyan));
  color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;
  transition:all .2s;flex-shrink:0;box-shadow:0 2px 8px rgba(20,184,166,.25)}
.ai-send-btn:hover{transform:scale(1.05);box-shadow:0 4px 12px rgba(20,184,166,.35)}
.ai-send-btn:active{transform:scale(.92)}
.ai-send-btn:disabled{opacity:.25;cursor:not-allowed;transform:none;box-shadow:none}
.ai-char-count{font-size:10px;color:var(--muted);flex-shrink:0;align-self:center;min-width:36px;text-align:right}

/* ── 13. Footer ─────────────────────────────────────────────── */
.page-footer{text-align:center;font-size:11px;color:var(--muted);position:fixed;bottom:0;right:20px;z-index:5;
  background:rgba(11,13,23,.8);backdrop-filter:blur(8px);border-radius:8px 8px 0 0;padding:6px 14px}

/* ── 14. Responsive ─────────────────────────────────────────── */
@media(max-width:1200px){
  .nav-search input{width:160px}
  .nav-search input:focus{width:200px}
  .filter-pills{display:none}
}
@media(max-width:900px){
  .modules-sidebar{width:200px}
  .nav-stats{display:none}
  .view-tabs{gap:0}
  .view-tab{padding:6px 10px;font-size:11px}
  .mod-grid{grid-template-columns:1fr}
}
@media(max-width:700px){
  .modules-sidebar{display:none}
  .nav-search{display:none}
  .graph-controls{left:16px;bottom:16px}
  .hero-stats{flex-wrap:wrap;gap:16px}
  .page-hero{padding:28px 20px 24px}
}
</style>
</head>
<body>

<!-- ═══ NAVIGATION ═══ -->
<nav>
  <div class="nav-brand" id="nav-brand" title="codemap-zero">
    <div class="icon"><svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg></div>
    <h1>codemap</h1>
  </div>
  <div class="view-tabs">
    <div class="view-tab active" data-page="graph">
      <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><circle cx="4" cy="7" r="2"/><circle cx="20" cy="7" r="2"/><circle cx="4" cy="17" r="2"/><circle cx="20" cy="17" r="2"/><path d="M6.3 8.3l3.7 2.2M14 9.8l3.7-2M6.3 15.7l3.7-2.2M14 14.2l3.7 2"/></svg>
      Graph
    </div>
    <div class="view-tab" data-page="overview">
      <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>
      Overview
    </div>
    <div class="view-tab" data-page="modules">
      <svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
      Modules
    </div>
    <div class="view-tab" data-page="analysis">
      <svg viewBox="0 0 24 24"><path d="M21 12h-4l-3 9L9 3l-3 9H3"/></svg>
      Analysis
    </div>
    <div class="view-tab" data-page="ai">
      <svg viewBox="0 0 24 24"><path d="M12 2a4 4 0 0 1 4 4v1a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3V6a4 4 0 0 1 4-4z"/><path d="M9 18h6M10 22h4"/></svg>
      AI
    </div>
  </div>
  <div class="nav-search graph-ctx" id="nav-search">
    <span class="s-icon"><svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg></span>
    <input type="text" id="graph-search" placeholder="Search nodes...">
    <span class="s-hint">Ctrl+K</span>
  </div>
  <div class="filter-pills graph-ctx" id="filter-pills">
    <button class="filter-pill active" data-filter="all">All</button>
    <button class="filter-pill" data-filter="file">Files</button>
    <button class="filter-pill" data-filter="class">Classes</button>
    <button class="filter-pill" data-filter="function">Functions</button>
    <button class="filter-pill" data-filter="method">Methods</button>
  </div>
  <div class="nav-spacer"></div>
  <div class="nav-stats">
    <span class="stat-badge"><span style="color:var(--accent-light)">__NODE_COUNT__</span> <small>nodes</small></span>
    <span class="stat-badge"><span style="color:var(--cyan)">__EDGE_COUNT__</span> <small>edges</small></span>
    <span class="stat-badge"><span style="color:var(--pink)">__COMMUNITY_COUNT__</span> <small>modules</small></span>
  </div>
</nav>

<!-- ═══ GRAPH PAGE (default) ═══ -->
<div id="graph" class="page active">
  <div class="graph-layout">
    <aside class="modules-sidebar">
      <div class="sidebar-head">
        <h4>Modules</h4>
        <span class="sidebar-count" id="sidebar-count">__COMMUNITY_COUNT__</span>
      </div>
      <div class="sidebar-list" id="sidebar-list"></div>
    </aside>
    <div class="graph-canvas" id="graph-container">
      <!-- Node detail panel -->
      <div class="node-panel" id="node-panel">
        <div class="node-panel-head">
          <button class="close" id="panel-close">&#10005;</button>
          <h4 id="panel-title">-</h4>
        </div>
        <div class="node-panel-body" id="panel-content"></div>
      </div>
      <!-- Controls -->
      <div class="graph-controls">
        <button class="ctrl-btn" id="ctrl-zoom-in" title="Zoom in">
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <button class="ctrl-btn" id="ctrl-zoom-out" title="Zoom out">
          <svg viewBox="0 0 24 24"><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </button>
        <button class="ctrl-btn" id="ctrl-fit" title="Fit to view">
          <svg viewBox="0 0 24 24"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"/></svg>
        </button>
        <button class="ctrl-btn active" id="ctrl-physics" title="Toggle physics">
          <svg viewBox="0 0 24 24"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
        </button>
        <button class="ctrl-btn" id="ctrl-legend" title="Legend">
          <svg viewBox="0 0 24 24"><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
        </button>
      </div>
      <!-- Legend popup -->
      <div class="graph-legend" id="graph-legend">
        <div class="legend-title">Node Shapes</div>
        <div class="legend-item"><span class="legend-shape">&#9679;</span> File</div>
        <div class="legend-item"><span class="legend-shape">&#9670;</span> Class</div>
        <div class="legend-item"><span class="legend-shape">&#9650;</span> Function</div>
        <div class="legend-item"><span class="legend-shape">&#9660;</span> Method</div>
        <div class="legend-divider"></div>
        <div class="legend-title">Edge Colors</div>
        <div class="legend-item"><span class="legend-dot" style="background:#f87171"></span> Imports</div>
        <div class="legend-item"><span class="legend-dot" style="background:#22d3ee"></span> Calls</div>
        <div class="legend-item"><span class="legend-dot" style="background:#34d399"></span> Methods</div>
        <div class="legend-item"><span class="legend-dot" style="background:#4b5563"></span> Contains</div>
      </div>
    </div>
  </div>
</div>

<!-- ═══ OVERVIEW PAGE ═══ -->
<div id="overview" class="content-page">
  <!-- Hero Banner -->
  <div class="page-hero">
    <div class="hero-inner">
      <span class="hero-type">__PROJECT_TYPE__</span>
      <h2 class="hero-title">__PROJECT_NAME__</h2>
      <p class="hero-desc" id="hero-desc"></p>
      <div class="hero-tags" id="hero-tags"></div>
      <div class="hero-stats">
        <div class="hero-stat"><span class="hs-val" style="color:var(--accent-light)">__TOTAL_FILES__</span><span class="hs-label">Source Files</span></div>
        <div class="hero-stat"><span class="hs-val" style="color:var(--cyan)" id="hero-loc">__TOTAL_LINES__</span><span class="hs-label">Lines of Code</span></div>
        <div class="hero-stat"><span class="hs-val" style="color:var(--green)">__NODE_COUNT__</span><span class="hs-label">Graph Nodes</span></div>
        <div class="hero-stat"><span class="hs-val" style="color:var(--pink)">__COMMUNITY_COUNT__</span><span class="hs-label">Modules</span></div>
      </div>
    </div>
  </div>
  <div class="page-body">
    <!-- Stat Cards -->
    <div class="grid g4" style="margin-bottom:28px">
      <div class="stat-card">
        <div class="glow" style="background:var(--accent)"></div>
        <div class="sc-icon" style="background:linear-gradient(135deg,var(--accent),#7c3aed)">
          <svg viewBox="0 0 24 24"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/></svg>
        </div>
        <div class="label">Source Files</div>
        <div class="value" style="color:var(--accent-light)">__TOTAL_FILES__</div>
        <div class="sub">scanned and analyzed</div>
      </div>
      <div class="stat-card">
        <div class="glow" style="background:var(--cyan)"></div>
        <div class="sc-icon" style="background:linear-gradient(135deg,var(--cyan),#06b6d4)">
          <svg viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg>
        </div>
        <div class="label">Lines of Code</div>
        <div class="value" style="color:var(--cyan)" id="loc-stat">__TOTAL_LINES__</div>
        <div class="sub">across all source files</div>
      </div>
      <div class="stat-card">
        <div class="glow" style="background:var(--green)"></div>
        <div class="sc-icon" style="background:linear-gradient(135deg,var(--green),#059669)">
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2a10 10 0 0 1 10 10"/><path d="M12 2a10 10 0 0 0-10 10"/></svg>
        </div>
        <div class="label">Dependency Graph</div>
        <div class="value" style="color:var(--green)">__NODE_COUNT__</div>
        <div class="sub">__EDGE_COUNT__ edges connecting them</div>
      </div>
      <div class="stat-card">
        <div class="glow" style="background:var(--pink)"></div>
        <div class="sc-icon" style="background:linear-gradient(135deg,var(--pink),#db2777)">
          <svg viewBox="0 0 24 24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
        </div>
        <div class="label">Modules Detected</div>
        <div class="value" style="color:var(--pink)">__COMMUNITY_COUNT__</div>
        <div class="sub">logical communities</div>
      </div>
    </div>

    <div class="section-head">
      <h2>
        <span class="sec-icon" style="background:linear-gradient(135deg,var(--cyan),var(--accent))"><svg viewBox="0 0 24 24"><path d="M12 2v20M2 12h20"/></svg></span>
        Stack Intelligence
      </h2>
    </div>
    <div class="grid g2" style="margin-bottom:28px">
      <div class="card">
        <div class="card-header">
          <h3><svg viewBox="0 0 24 24"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg> Languages & Frameworks</h3>
        </div>
        <div class="card-body">
          <div class="tiny-muted" style="margin-bottom:8px">Languages detected</div>
          <div class="chip-cloud" id="lang-chip-cloud"></div>
          <div class="tiny-muted" style="margin:14px 0 8px">Frameworks detected</div>
          <div class="chip-cloud" id="fw-chip-cloud"></div>
        </div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3><svg viewBox="0 0 24 24"><path d="M16 18l6-6-6-6"/><path d="M8 6l-6 6 6 6"/></svg> Dependency Snapshot</h3>
        </div>
        <div class="card-body" id="deps-overview"></div>
      </div>
    </div>

    <!-- Gods & Entry Points -->
    <div class="section-head">
      <h2>
        <span class="sec-icon" style="background:linear-gradient(135deg,var(--orange),var(--red))"><svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg></span>
        Key Insights
      </h2>
    </div>
    <div class="grid g2" style="margin-bottom:28px">
      <div class="card">
        <div class="card-header">
          <h3><svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg> Most Connected Nodes</h3>
          <span class="badge">Top 10</span>
        </div>
        <div class="card-body" id="gods-list"></div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3><svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Entry Points</h3>
          <span class="badge" id="entry-count">0</span>
        </div>
        <div class="card-body" id="entry-list"></div>
      </div>
    </div>

    <!-- Distribution Charts -->
    <div class="section-head">
      <h2>
        <span class="sec-icon" style="background:linear-gradient(135deg,var(--accent),var(--cyan))"><svg viewBox="0 0 24 24"><path d="M18 20V10M12 20V4M6 20v-6"/></svg></span>
        Distribution
      </h2>
    </div>
    <div class="grid g2" style="margin-bottom:28px">
      <div class="card">
        <div class="card-header"><h3><svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg> Module Sizes</h3></div>
        <div class="card-body" id="module-bars"></div>
      </div>
      <div class="card">
        <div class="card-header"><h3><svg viewBox="0 0 24 24"><path d="M21 12h-4l-3 9L9 3l-3 9H3"/></svg> Complexity Hotspots</h3><span class="badge">Files</span></div>
        <div class="card-body" id="complexity-bars"></div>
      </div>
    </div>
  </div>
</div>

<!-- ═══ MODULES PAGE ═══ -->
<div id="modules" class="content-page">
  <div class="page-body">
    <div class="section-head">
      <h2>
        <span class="sec-icon" style="background:linear-gradient(135deg,var(--accent),var(--cyan))"><svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg></span>
        Modules
      </h2>
      <div class="section-actions">
        <div style="position:relative">
          <span style="position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--muted);pointer-events:none">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          </span>
          <input type="text" class="mod-search" id="mod-search" placeholder="Search modules...">
        </div>
        <span class="section-count">__COMMUNITY_COUNT__ modules</span>
      </div>
    </div>
    <div class="mod-grid" id="mod-container"></div>
  </div>
</div>

<!-- ═══ ANALYSIS PAGE ═══ -->
<div id="analysis" class="content-page">
  <div class="page-body">
    <div class="section-head">
      <h2>
        <span class="sec-icon" style="background:linear-gradient(135deg,var(--orange),var(--red))"><svg viewBox="0 0 24 24"><path d="M21 12h-4l-3 9L9 3l-3 9H3"/></svg></span>
        Architecture Analysis
      </h2>
    </div>
    <!-- Insight summary cards -->
    <div class="grid g4" id="insight-row" style="margin-bottom:28px"></div>
    <!-- Main content -->
    <div class="grid g2" style="margin-bottom:28px">
      <div class="card">
        <div class="card-header">
          <h3><svg viewBox="0 0 24 24"><path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="8.5" cy="7" r="4"/><path d="M20 8v6M23 11h-6"/></svg> Cross-Module Dependencies</h3>
          <span class="badge" id="dep-count">0</span>
        </div>
        <div class="card-body" id="deps-list"></div>
      </div>
      <div class="card">
        <div class="card-header">
          <h3><svg viewBox="0 0 24 24"><path d="M18 20V10M12 20V4M6 20v-6"/></svg> Complexity Table</h3>
        </div>
        <div class="card-body" style="padding:0;overflow-x:auto">
          <table>
            <thead><tr><th>File</th><th>Symbols</th><th>Connections</th><th>Lines</th><th>Score</th></tr></thead>
            <tbody id="complex-tbody"></tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</div>

<!-- ═══ AI ASSISTANT PAGE ═══ -->
<div id="ai" class="page">
  <div class="ai-layout">
    <div class="ai-sidebar">
      <div class="ai-sidebar-header">
        <div class="sidebar-icon"><svg viewBox="0 0 24 24"><path d="M12 2a4 4 0 0 1 4 4v1a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3V6a4 4 0 0 1 4-4z"/><path d="M9 18h6M10 22h4"/></svg></div>
        <h3>AI Configuration</h3>
      </div>
      <div class="ai-sidebar-scroll">
        <div class="ai-field-group">
          <label class="ai-label">Provider</label>
          <select id="ai-provider" class="ai-select"></select>
        </div>
        <div class="ai-field-group">
          <label class="ai-label">Model</label>
          <select id="ai-model" class="ai-select"></select>
        </div>
        <div class="ai-field-group">
          <label class="ai-label">API Key</label>
          <input type="password" id="ai-key" class="ai-input" placeholder="Enter your API key...">
          <div class="ai-key-hint">
            <svg viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            Key sent only to your provider. Never stored.
          </div>
        </div>
        <button class="ai-connect-btn" id="ai-connect"><span id="ai-connect-text">Connect</span></button>
        <div id="ai-status" class="ai-status"></div>
        <div class="ai-divider"></div>
        <!-- Context info -->
        <div class="ai-context-section">
          <h4><svg viewBox="0 0 24 24"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg> Context Loaded</h4>
          <div class="ai-ctx-item"><span class="ctx-label">Files</span><span class="ctx-val">__TOTAL_FILES__</span></div>
          <div class="ai-ctx-item"><span class="ctx-label">Nodes</span><span class="ctx-val">__NODE_COUNT__</span></div>
          <div class="ai-ctx-item"><span class="ctx-label">Modules</span><span class="ctx-val">__COMMUNITY_COUNT__</span></div>
          <div class="ai-ctx-item"><span class="ctx-label">Complexity</span><span class="ctx-val" id="ctx-complexity">-</span></div>
        </div>
        <div class="ai-divider"></div>
        <div class="ai-suggestions-section">
          <h4>Try Asking</h4>
          <div class="ai-suggestion" data-q="What does this project do?">What does this project do?</div>
          <div class="ai-suggestion" data-q="Explain the architecture and main modules">Explain the architecture</div>
          <div class="ai-suggestion" data-q="What are the most complex parts and why?">What are the most complex parts?</div>
          <div class="ai-suggestion" data-q="Find potential bugs, code smells, or issues">Find potential bugs or issues</div>
          <div class="ai-suggestion" data-q="Suggest refactoring opportunities to improve the codebase">Suggest refactoring opportunities</div>
          <div class="ai-suggestion" data-q="What patterns and best practices does this project follow?">Patterns and best practices</div>
        </div>
      </div>
      <div class="ai-sidebar-footer">Direct API calls &middot; Your key only</div>
    </div>
    <div class="ai-chat-panel">
      <div class="ai-chat-header">
        <h3>Chat <span class="model-badge" id="ai-model-badge" style="display:none">-</span></h3>
        <div class="ai-chat-actions">
          <button class="ai-action-btn" id="ai-export" title="Export chat">
            <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export
          </button>
          <button class="ai-action-btn" id="ai-clear" title="Clear chat">
            <svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            Clear
          </button>
        </div>
      </div>
      <div id="ai-messages" class="ai-messages">
        <div class="ai-welcome">
          <div class="ai-welcome-icon">&#129302;</div>
          <h4>AI Project Assistant</h4>
          <p>Configure your AI provider to unlock intelligent code analysis. Full project context is automatically included.</p>
          <div class="ai-welcome-features">
            <div class="ai-welcome-feat"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg> Architecture analysis</div>
            <div class="ai-welcome-feat"><svg viewBox="0 0 24 24"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg> Bug detection</div>
            <div class="ai-welcome-feat"><svg viewBox="0 0 24 24"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg> Code explanation</div>
            <div class="ai-welcome-feat"><svg viewBox="0 0 24 24"><path d="M21 12h-4l-3 9L9 3l-3 9H3"/></svg> Complexity insights</div>
          </div>
          <div class="ai-welcome-chips">
            <div class="ai-welcome-chip" data-q="What does this project do?">What does this project do?</div>
            <div class="ai-welcome-chip" data-q="What are the main features?">Main features</div>
            <div class="ai-welcome-chip" data-q="How is the code organized?">Code organization</div>
            <div class="ai-welcome-chip" data-q="What are the most complex parts?">Complex parts</div>
          </div>
        </div>
      </div>
      <div class="ai-input-bar">
        <textarea id="ai-msg" class="ai-msg-input" placeholder="Ask about your project..." disabled rows="1"></textarea>
        <span class="ai-char-count" id="ai-char-count"></span>
        <button id="ai-send" class="ai-send-btn" disabled title="Send (Enter)">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
        </button>
      </div>
    </div>
  </div>
</div>

<div class="page-footer">codemap-zero v0.1.8 &middot; <strong style="color:var(--accent-light)">Jerry4539</strong></div>

<script>
(function(){
'use strict';

/* ── Embedded Data ───────────────────────────────────────── */
var GRAPH_NODES  = __GRAPH_NODES_JSON__;
var GRAPH_EDGES  = __GRAPH_EDGES_JSON__;
var COMMUNITIES  = __COMMUNITIES_JSON__;
var GODS         = __GODS_JSON__;
var ENTRY_POINTS = __ENTRY_POINTS_JSON__;
var COMPLEXITY   = __COMPLEXITY_JSON__;
var SURPRISES    = __SURPRISES_JSON__;
var FRAMEWORKS   = __FRAMEWORKS_JSON__;
var LANGUAGES    = __LANGUAGES_JSON__;
var FRAMEWORKS_BY_LANGUAGE = __FRAMEWORKS_BY_LANGUAGE_JSON__;
var DEPENDENCIES_BY_ECOSYSTEM = __DEPENDENCIES_BY_ECOSYSTEM_JSON__;
var DOCS_SUMMARY = __DOCS_SUMMARY_JSON__;
var PROJECT_DESC = '__PROJECT_DESC__';
var TOTAL_LINES  = __TOTAL_LINES__;

/* ── AI Provider configs ─────────────────────────────────── */
var PROVIDERS = {
  vedaslab: {
    name: 'Vedaslab.in',
    baseUrl: 'https://api.vedaslab.in/public/api.php?path=chat/completions',
    modelsUrl: 'https://api.vedaslab.in/public/models.php?format=flat',
    defaultModel: 'gpt-4o',
    models: [],
    headerFn: function(key) { return {'Content-Type':'application/json','X-My-API-Key':key}; }
  },
  openai: {
    name: 'OpenAI',
    baseUrl: 'https://api.openai.com/v1/chat/completions',
    defaultModel: 'gpt-4o',
    models: ['gpt-4o','gpt-4o-mini','gpt-4.1','gpt-4.1-mini','o3-mini'],
    headerFn: function(key) { return {'Content-Type':'application/json','Authorization':'Bearer '+key}; }
  },
  gemini: {
    name: 'Google Gemini',
    baseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions',
    defaultModel: 'gemini-2.5-pro',
    models: ['gemini-2.5-pro','gemini-2.5-flash','gemini-2.0-flash'],
    headerFn: function(key) { return {'Content-Type':'application/json','Authorization':'Bearer '+key}; }
  },
  claude: {
    name: 'Anthropic Claude',
    baseUrl: 'https://api.anthropic.com/v1/messages',
    defaultModel: 'claude-sonnet-4-20250514',
    models: ['claude-sonnet-4-20250514','claude-opus-4-20250514','claude-3-5-haiku-20241022'],
    headerFn: function(key) { return {'Content-Type':'application/json','x-api-key':key,'anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true'}; }
  }
};

function buildContext() {
  var topNodes = GODS.slice(0,8).map(function(g){ return (g.label||g.id)+' ('+g.type+', degree '+g.degree+')'; }).join(', ');
  var modList = COMMUNITIES.slice(0,10).map(function(c){ return c.label+' ('+c.size+' nodes, cohesion '+(c.cohesion*100).toFixed(0)+'%)'; }).join('; ');
  var topComplex = COMPLEXITY.slice(0,5).map(function(c){ return (c.label||c.file)+' ('+c.lines+' lines, score '+c.complexity_score.toFixed(1)+')'; }).join(', ');
  return 'Project: __PROJECT_NAME__ (__PROJECT_TYPE__)\n' +
    'Stats: __TOTAL_FILES__ files, '+TOTAL_LINES+' lines, __NODE_COUNT__ nodes, __EDGE_COUNT__ edges, __COMMUNITY_COUNT__ modules\n' +
    'Top connected: '+topNodes+'\nModules: '+modList+'\nComplex files: '+topComplex+'\n' +
    'You are an AI assistant with full context of this codebase. Answer questions about the project architecture, code organization, dependencies, and complexity. Be concise and helpful.';
}
var aiChatHistory = [];

function animateVisibleSection(pageId) {
  var root = document.getElementById(pageId);
  if (!root) return;
  var items = root.querySelectorAll('.section-head,.stat-card,.card,.mod-card,.insight-card,.ai-context-section,.ai-welcome-feat,.hero-stat');
  items.forEach(function(el, idx) {
    el.classList.add('reveal-item');
    el.style.transitionDelay = Math.min(idx * 35, 280) + 'ms';
    requestAnimationFrame(function() {
      el.classList.add('show');
    });
  });
}

/* ══════════════════════════════════════════════════════════ */
/* ── TAB NAVIGATION ──────────────────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

document.querySelectorAll('.view-tab').forEach(function(tab) {
  tab.addEventListener('click', function() {
    document.querySelectorAll('.view-tab').forEach(function(t){ t.classList.remove('active'); });
    document.querySelectorAll('.page,.content-page').forEach(function(p){ p.classList.remove('active'); });
    tab.classList.add('active');
    document.getElementById(tab.dataset.page).classList.add('active');
    var isGraph = tab.dataset.page === 'graph';
    document.querySelectorAll('.graph-ctx').forEach(function(el){ el.style.display = isGraph ? '' : 'none'; });
    document.body.style.overflow = (tab.dataset.page === 'graph' || tab.dataset.page === 'ai') ? 'hidden' : 'auto';
    if (tab.dataset.page === 'graph' && !window._graphLoaded) loadGraph();
    animateVisibleSection(tab.dataset.page);
  });
});

document.getElementById('nav-brand').addEventListener('click', function() {
  document.querySelector('.view-tab[data-page="graph"]').click();
});

/* ── Keyboard shortcuts ──────────────────────────────────── */
document.addEventListener('keydown', function(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    var graphTab = document.querySelector('.view-tab[data-page="graph"]');
    if (!graphTab.classList.contains('active')) graphTab.click();
    document.getElementById('graph-search').focus();
  }
  if (e.key === 'Escape') {
    hideNodePanel();
    var s = document.getElementById('graph-search');
    if (s) { s.blur(); s.value = ''; s.dispatchEvent(new Event('input')); }
    var leg = document.getElementById('graph-legend');
    if (leg) leg.classList.remove('show');
  }
});

/* ── Format numbers ──────────────────────────────────────── */
var locEl = document.getElementById('loc-stat');
if (locEl) locEl.textContent = Number(TOTAL_LINES).toLocaleString();
var heroLoc = document.getElementById('hero-loc');
if (heroLoc) heroLoc.textContent = Number(TOTAL_LINES).toLocaleString();

/* ══════════════════════════════════════════════════════════ */
/* ── MODULES SIDEBAR (Graph page) ────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

(function(){
  var el = document.getElementById('sidebar-list');
  if (!el) return;
  el.innerHTML = COMMUNITIES.map(function(c) {
    return '<div class="module-item" data-community="'+c.id+'">' +
      '<span class="module-dot" style="background:'+c.color+'"></span>' +
      '<span class="module-name">'+escapeHtml(c.label)+'</span>' +
      '<span class="module-count">'+c.size+'</span></div>';
  }).join('');
})();

/* ══════════════════════════════════════════════════════════ */
/* ── GRAPH PAGE ──────────────────────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

var EDGE_COLORS = {imports:'#f87171',calls:'#22d3ee',contains:'#4b5563',method:'#34d399'};
var graphNetwork = null, graphNodesDS = null, graphEdgesDS = null, vNodes = [], vEdges = [];
var physicsEnabled = true;
var activeModule = -1;

function loadGraph() {
  window._graphLoaded = true;
  if (typeof vis === 'undefined') {
    document.getElementById('graph-container').innerHTML = '<div style="padding:60px;text-align:center;color:var(--red)"><h3>vis.js failed to load</h3><p>Check internet connection</p></div>';
    return;
  }
  var nodeMap = {};
  GRAPH_NODES.forEach(function(n) { nodeMap[n.id] = n; });

  vNodes = GRAPH_NODES.map(function(n) {
    var sz = Math.max(10, Math.min(50, 10 + n.degree * 3));
    var shapeMap = {file:'dot',class:'diamond',function:'triangle',method:'triangleDown',document:'square',external:'star'};
    return {
      id: n.id,
      label: n.label.length > 30 ? n.label.slice(0,27)+'...' : n.label,
      size: sz,
      shape: shapeMap[n.type] || 'dot',
      color: {background:n.color, border:n.color, highlight:{background:'#fff',border:n.color}, hover:{background:n.color+'dd',border:'#fff'}},
      font: {color:'#e5e7eb', size:Math.max(9,Math.min(14,9+n.degree)), strokeWidth:3, strokeColor:'#000'},
      borderWidth:2, borderWidthSelected:3,
      shadow:{enabled:true,color:'rgba(0,0,0,.3)',size:8,x:0,y:2},
      _raw: n,
    };
  });

  vEdges = GRAPH_EDGES.map(function(e,i) {
    var c = EDGE_COLORS[e.relation] || '#4b5563';
    return {
      id:'e'+i, from:e.source, to:e.target,
      color:{color:c,opacity:0.35,highlight:c,hover:c},
      width: (e.relation==='imports'||e.relation==='calls') ? 1.5 : 0.7,
      arrows: (e.relation==='imports'||e.relation==='calls') ? {to:{enabled:true,scaleFactor:0.5}} : {},
      smooth:{type:'continuous'},
      _rel:e.relation,
    };
  });

  graphNodesDS = new vis.DataSet(vNodes);
  graphEdgesDS = new vis.DataSet(vEdges);

  graphNetwork = new vis.Network(document.getElementById('graph-container'), {nodes:graphNodesDS, edges:graphEdgesDS}, {
    physics:{
      solver:'forceAtlas2Based',
      forceAtlas2Based:{gravitationalConstant:-45,centralGravity:0.005,springLength:150,springConstant:0.055,avoidOverlap:0.45},
      stabilization:{enabled:true,iterations:350},maxVelocity:28,minVelocity:0.3
    },
    interaction:{hover:true,tooltipDelay:200,zoomView:true,dragView:true,keyboard:{enabled:true}},
    layout:{improvedLayout:true},
  });

  graphNetwork.on('click', function(ev) {
    if (ev.nodes.length > 0) {
      var nid = ev.nodes[0];
      var raw = nodeMap[nid];
      if (!raw) return;
      showNodePanel(raw, GRAPH_EDGES, nodeMap);
      highlightNeighbors(nid);
    } else {
      hideNodePanel();
      resetHL();
    }
  });
  graphNetwork.on('doubleClick', function(ev) {
    if (ev.nodes.length > 0) graphNetwork.focus(ev.nodes[0], {scale:1.8, animation:{duration:400,easingFunction:'easeInOutQuad'}});
  });

  /* Search */
  document.getElementById('graph-search').addEventListener('input', applyGraphFilter);

  /* Filter pills */
  document.querySelectorAll('.filter-pill').forEach(function(pill) {
    pill.addEventListener('click', function() {
      document.querySelectorAll('.filter-pill').forEach(function(p){ p.classList.remove('active'); });
      pill.classList.add('active');
      applyGraphFilter();
    });
  });

  /* Module sidebar click to highlight community */
  document.querySelectorAll('.module-item').forEach(function(item) {
    item.addEventListener('click', function() {
      var cid = parseInt(item.dataset.community);
      var isActive = item.classList.contains('active');
      document.querySelectorAll('.module-item').forEach(function(i){ i.classList.remove('active'); });
      if (!isActive) {
        item.classList.add('active');
        activeModule = cid;
        highlightCommunity(cid);
      } else {
        activeModule = -1;
        resetHL();
      }
    });
  });
}

function applyGraphFilter() {
  if (!graphNetwork) return;
  var q = document.getElementById('graph-search').value.toLowerCase();
  var filterEl = document.querySelector('.filter-pill.active');
  var filter = filterEl ? filterEl.dataset.filter : 'all';
  var hidden = new Set();
  vNodes.forEach(function(n) {
    var show = true;
    if (filter !== 'all' && n._raw.type !== filter) show = false;
    if (q) {
      var hay = (n._raw.label+' '+n._raw.communityLabel+' '+n._raw.sourceFile+' '+n._raw.signature).toLowerCase();
      if (hay.indexOf(q) === -1) show = false;
    }
    if (!show) hidden.add(n.id);
    graphNodesDS.update({id:n.id, hidden:!show, borderWidth: (q && show) ? 4 : 2});
  });
  vEdges.forEach(function(e) { graphEdgesDS.update({id:e.id, hidden: hidden.has(e.from)||hidden.has(e.to)}); });
}

function highlightNeighbors(nid) {
  var conn = graphNetwork.getConnectedNodes(nid);
  var s = new Set(conn); s.add(nid);
  graphNodesDS.update(vNodes.map(function(n){ return {id:n.id, opacity: s.has(n.id)?1:0.08}; }));
  graphEdgesDS.update(vEdges.map(function(e){ return {id:e.id, color:{color:e.color.color, opacity:(e.from===nid||e.to===nid)?0.9:0.03}, width:(e.from===nid||e.to===nid)?2.5:e.width}; }));
}

function highlightCommunity(cid) {
  var members = new Set();
  GRAPH_NODES.forEach(function(n){ if (n.community === cid) members.add(n.id); });
  graphNodesDS.update(vNodes.map(function(n){ return {id:n.id, opacity: members.has(n.id)?1:0.06}; }));
  graphEdgesDS.update(vEdges.map(function(e){
    var inComm = members.has(e.from) && members.has(e.to);
    return {id:e.id, color:{color:e.color.color, opacity:inComm?0.8:0.02}, width:inComm?2:e.width};
  }));
}

function resetHL() {
  graphNodesDS.update(vNodes.map(function(n){ return {id:n.id, opacity:1}; }));
  graphEdgesDS.update(vEdges.map(function(e){ return {id:e.id, color:{color:e.color.color, opacity:0.35}, width:(e._rel==='imports'||e._rel==='calls')?1.5:0.7}; }));
}

function showNodePanel(raw, allEdges, nodeMap) {
  var panel = document.getElementById('node-panel');
  document.getElementById('panel-title').textContent = raw.label;
  var h = '';
  h += '<div class="np-row"><div class="np-label">Type</div><div class="np-val"><span class="list-badge '+raw.type+'">'+raw.type+'</span></div></div>';
  h += '<div class="np-row"><div class="np-label">Module</div><div class="np-val" style="color:'+raw.color+'">'+escapeHtml(raw.communityLabel)+'</div></div>';
  if (raw.sourceFile) h += '<div class="np-row"><div class="np-label">File</div><div class="np-val"><code>'+escapeHtml(raw.sourceFile)+'</code></div></div>';
  if (raw.signature) h += '<div class="np-row"><div class="np-label">Signature</div><div class="np-val"><span class="sig">'+escapeHtml(raw.signature)+'</span></div></div>';
  if (raw.docstring) h += '<div class="np-row"><div class="np-label">Docs</div><div class="np-val" style="font-style:italic;color:var(--dim);font-size:12px">'+escapeHtml(raw.docstring)+'</div></div>';
  h += '<div class="np-row"><div class="np-label">Connections</div><div class="np-conn"><div class="np-conn-item"><div class="conn-val">'+raw.inDeg+'</div><div class="conn-label">In</div></div><div class="np-conn-item"><div class="conn-val">'+raw.outDeg+'</div><div class="conn-label">Out</div></div><div class="np-conn-item"><div class="conn-val">'+raw.degree+'</div><div class="conn-label">Total</div></div></div></div>';
  var inc = allEdges.filter(function(e){ return e.target === raw.id; }).slice(0,8);
  var out = allEdges.filter(function(e){ return e.source === raw.id; }).slice(0,8);
  if (inc.length) {
    h += '<div class="np-row"><div class="np-label">Incoming ('+inc.length+')</div><div class="np-val">';
    inc.forEach(function(e){ h += '<div style="font-size:11px;color:var(--dim);padding:3px 0;border-bottom:1px solid rgba(55,65,81,.3)">&larr; '+(nodeMap[e.source]?escapeHtml(nodeMap[e.source].label):e.source)+' <span style="color:var(--muted);font-size:10px;float:right">'+e.relation+'</span></div>'; });
    h += '</div></div>';
  }
  if (out.length) {
    h += '<div class="np-row"><div class="np-label">Outgoing ('+out.length+')</div><div class="np-val">';
    out.forEach(function(e){ h += '<div style="font-size:11px;color:var(--dim);padding:3px 0;border-bottom:1px solid rgba(55,65,81,.3)">&rarr; '+(nodeMap[e.target]?escapeHtml(nodeMap[e.target].label):e.target)+' <span style="color:var(--muted);font-size:10px;float:right">'+e.relation+'</span></div>'; });
    h += '</div></div>';
  }
  document.getElementById('panel-content').innerHTML = h;
  panel.classList.add('show');
}
function hideNodePanel() { document.getElementById('node-panel').classList.remove('show'); }
document.getElementById('panel-close').addEventListener('click', hideNodePanel);

/* ── Graph Controls ──────────────────────────────────────── */
document.getElementById('ctrl-zoom-in').addEventListener('click', function() {
  if (graphNetwork) { var s = graphNetwork.getScale(); graphNetwork.moveTo({scale:s*1.3,animation:{duration:200}}); }
});
document.getElementById('ctrl-zoom-out').addEventListener('click', function() {
  if (graphNetwork) { var s = graphNetwork.getScale(); graphNetwork.moveTo({scale:s/1.3,animation:{duration:200}}); }
});
document.getElementById('ctrl-fit').addEventListener('click', function() {
  if (graphNetwork) graphNetwork.fit({animation:{duration:400,easingFunction:'easeInOutQuad'}});
});
document.getElementById('ctrl-physics').addEventListener('click', function() {
  physicsEnabled = !physicsEnabled;
  if (graphNetwork) graphNetwork.setOptions({physics:{enabled:physicsEnabled}});
  this.classList.toggle('active', physicsEnabled);
});
document.getElementById('ctrl-legend').addEventListener('click', function() {
  document.getElementById('graph-legend').classList.toggle('show');
});

/* Load graph immediately (default view) */
setTimeout(function(){ if (!window._graphLoaded) loadGraph(); }, 100);

/* ══════════════════════════════════════════════════════════ */
/* ── OVERVIEW PAGE ───────────────────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

/* Hero description + tags */
var heroDescEl = document.getElementById('hero-desc');
if (heroDescEl && PROJECT_DESC) heroDescEl.textContent = PROJECT_DESC;
else if (heroDescEl) heroDescEl.style.display = 'none';

var heroTagsEl = document.getElementById('hero-tags');
if (heroTagsEl && FRAMEWORKS.length > 0) {
  heroTagsEl.innerHTML = FRAMEWORKS.map(function(fw){
    return '<span class="hero-tag">'+escapeHtml(fw)+'</span>';
  }).join('');
}

/* Languages + frameworks */
(function(){
  var langEl = document.getElementById('lang-chip-cloud');
  var fwEl = document.getElementById('fw-chip-cloud');
  if (langEl) {
    var langEntries = Object.keys(LANGUAGES || {}).map(function(k){ return [k, LANGUAGES[k]]; });
    langEntries.sort(function(a,b){ return b[1]-a[1]; });
    langEl.innerHTML = langEntries.length
      ? langEntries.map(function(pair){ return '<span class="chip lang">'+escapeHtml(pair[0])+' · '+pair[1]+' files</span>'; }).join('')
      : '<span class="tiny-muted">No language metadata detected</span>';
  }
  if (fwEl) {
    var grouped = [];
    Object.keys(FRAMEWORKS_BY_LANGUAGE || {}).forEach(function(lang){
      var fws = FRAMEWORKS_BY_LANGUAGE[lang] || [];
      fws.forEach(function(fw){ grouped.push({lang:lang, fw:fw}); });
    });
    fwEl.innerHTML = grouped.length
      ? grouped.map(function(item){ return '<span class="chip fw">'+escapeHtml(item.fw)+' <span class="tiny-muted">('+escapeHtml(item.lang)+')</span></span>'; }).join('')
      : (FRAMEWORKS.length ? FRAMEWORKS.map(function(fw){ return '<span class="chip fw">'+escapeHtml(fw)+'</span>'; }).join('') : '<span class="tiny-muted">No frameworks detected</span>');
  }
})();

/* Dependency overview */
(function(){
  var depsEl = document.getElementById('deps-overview');
  if (!depsEl) return;
  var ecosystems = Object.keys(DEPENDENCIES_BY_ECOSYSTEM || {});
  if (!ecosystems.length) {
    depsEl.innerHTML = '<div class="tiny-muted">No dependency manifests detected</div>';
    return;
  }
  depsEl.innerHTML = ecosystems.map(function(eco){
    var deps = DEPENDENCIES_BY_ECOSYSTEM[eco] || [];
    var chips = deps.slice(0, 10).map(function(d){ return '<span class="chip dep">'+escapeHtml(d)+'</span>'; }).join('');
    var extra = deps.length > 10 ? '<div class="tiny-muted" style="margin-top:6px">+'+(deps.length-10)+' more</div>' : '';
    return '<div style="margin-bottom:12px"><div class="tiny-muted" style="margin-bottom:6px;text-transform:uppercase;letter-spacing:.8px">'+escapeHtml(eco)+'</div><div class="chip-cloud">'+chips+'</div>'+extra+'</div>';
  }).join('');
})();

/* Gods list with rank badges */
document.getElementById('gods-list').innerHTML = GODS.slice(0,10).map(function(g,i) {
  var rankClass = i===0?'gold':i===1?'silver':i===2?'bronze':'normal';
  return '<div class="list-item"><div class="list-rank '+rankClass+'">'+(i+1)+'</div><div class="list-info"><div class="name">'+escapeHtml(g.label||g.id)+'</div><div class="meta">'+escapeHtml(g.source_file||'')+'</div></div><span class="list-badge '+(g.type||'')+'">'+g.type+'</span><span class="list-val">'+g.degree+'</span></div>';
}).join('') || '<div style="color:var(--muted);font-size:13px;padding:10px 0">No data</div>';

/* Entry points */
(function(){
  var el = document.getElementById('entry-list');
  var countEl = document.getElementById('entry-count');
  if (countEl) countEl.textContent = ENTRY_POINTS.length;
  if (ENTRY_POINTS.length === 0) { el.innerHTML = '<div style="color:var(--muted);font-size:13px">No entry points detected</div>'; return; }
  el.innerHTML = ENTRY_POINTS.slice(0,8).map(function(ep) {
    return '<div class="entry-item"><div class="entry-icon"></div><span class="entry-name">'+escapeHtml(ep.label||ep.id||'')+'</span><span class="entry-file">'+escapeHtml(ep.source_file||'')+'</span></div>';
  }).join('');
})();

/* Module distribution bars with stagger animation */
(function(){
  var maxSize = Math.max.apply(null, COMMUNITIES.map(function(c){ return c.size; }).concat([1]));
  document.getElementById('module-bars').innerHTML = COMMUNITIES.slice(0,12).map(function(c,i) {
    var pct = (c.size / maxSize * 100).toFixed(0);
    return '<div class="bar-row" style="animation-delay:'+((i*60)+'ms')+'"><span class="bar-label">'+escapeHtml(c.label)+'</span><div class="bar-track"><div class="bar-fill" style="width:'+pct+'%;background:'+c.color+'">'+c.size+'</div></div><span class="bar-val">'+(c.cohesion*100).toFixed(0)+'%</span></div>';
  }).join('');
})();

/* Complexity bars */
(function(){
  var maxConn = Math.max.apply(null, COMPLEXITY.map(function(c){ return c.connections; }).concat([1]));
  document.getElementById('complexity-bars').innerHTML = COMPLEXITY.slice(0,10).map(function(c,i) {
    var pct = (c.connections / maxConn * 100).toFixed(0);
    return '<div class="bar-row" style="animation-delay:'+((i*60)+'ms')+'"><span class="bar-label">'+escapeHtml(c.label)+'</span><div class="bar-track"><div class="bar-fill" style="width:'+pct+'%;background:linear-gradient(90deg,var(--orange),var(--red))">'+c.symbols+' sym</div></div><span class="bar-val">'+Number(c.lines).toLocaleString()+'L</span></div>';
  }).join('');
})();

/* ══════════════════════════════════════════════════════════ */
/* ── MODULES PAGE ────────────────────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

function renderModules(filter) {
  filter = (filter || '').toLowerCase();
  var html = COMMUNITIES.filter(function(c) {
    return !filter || c.label.toLowerCase().indexOf(filter) !== -1;
  }).map(function(c) {
    var cohPct = (c.cohesion * 100).toFixed(0);
    var files = c.files.map(function(f){ return '<span class="mod-file">'+escapeHtml(f.label)+'</span>'; }).join('');
    var syms = c.symbols.slice(0,12).map(function(s){
      var tClass = 't-'+(s.type||'function');
      return '<div class="mod-sym"><span class="sym-type '+tClass+'">'+(s.type||'?')+'</span> '+escapeHtml(s.signature||s.label)+'</div>';
    }).join('');
    return '<div class="mod-card">' +
      '<div class="mod-header" onclick="this.parentElement.classList.toggle(\'open\')">' +
        '<div class="mod-color-bar" style="background:'+c.color+'"></div>' +
        '<div class="mod-header-content">' +
          '<span class="mod-dot" style="background:'+c.color+'"></span>' +
          '<span class="mod-title">'+escapeHtml(c.label)+'</span>' +
          '<div class="mod-meta">' +
            '<span><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/></svg> '+c.size+'</span>' +
            '<span><svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> '+cohPct+'%</span>' +
          '</div>' +
        '</div>' +
        '<span class="mod-chevron">&#9654;</span>' +
      '</div>' +
      '<div class="mod-body"><div class="mod-inner">' +
        '<div class="cohesion-row"><span class="cohesion-label">Cohesion</span><div class="cohesion-bar"><div class="cohesion-fill" style="width:'+cohPct+'%;background:'+c.color+'"></div></div><span class="cohesion-pct" style="color:'+c.color+'">'+cohPct+'%</span></div>' +
        (files ? '<div class="mod-section-label">Files</div><div class="mod-files">'+files+'</div>' : '') +
        (syms ? '<div class="mod-section-label">Symbols</div><div class="mod-symbols">'+syms+'</div>' : '') +
      '</div></div></div>';
  }).join('');
  document.getElementById('mod-container').innerHTML = html || '<div style="color:var(--muted);font-size:14px;text-align:center;padding:40px">No modules match your search</div>';
}
renderModules();
animateVisibleSection('modules');

/* Module search */
document.getElementById('mod-search').addEventListener('input', function() {
  renderModules(this.value);
  animateVisibleSection('modules');
});

/* ══════════════════════════════════════════════════════════ */
/* ── ANALYSIS PAGE ───────────────────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

/* Insight cards */
(function(){
  var el = document.getElementById('insight-row');
  var maxComplexity = COMPLEXITY.length > 0 ? COMPLEXITY[0] : null;
  var avgCohesion = COMMUNITIES.length > 0 ? (COMMUNITIES.reduce(function(s,c){return s+c.cohesion;},0)/COMMUNITIES.length*100).toFixed(0) : 0;
  var totalSymbols = COMPLEXITY.reduce(function(s,c){return s+c.symbols;},0);

  el.innerHTML = '<div class="insight-card">' +
    '<div class="ic-icon" style="background:linear-gradient(135deg,var(--red),var(--orange))"><svg viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></div>' +
    '<div class="ic-val" style="color:var(--red)">'+SURPRISES.length+'</div>' +
    '<div class="ic-label">Cross-Module Deps</div></div>' +
    '<div class="insight-card">' +
    '<div class="ic-icon" style="background:linear-gradient(135deg,var(--accent),var(--cyan))"><svg viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div>' +
    '<div class="ic-val" style="color:var(--green)">'+avgCohesion+'%</div>' +
    '<div class="ic-label">Avg Cohesion</div></div>' +
    '<div class="insight-card">' +
    '<div class="ic-icon" style="background:linear-gradient(135deg,var(--orange),var(--yellow))"><svg viewBox="0 0 24 24"><path d="M21 12h-4l-3 9L9 3l-3 9H3"/></svg></div>' +
    '<div class="ic-val" style="color:var(--orange)">'+(maxComplexity?maxComplexity.complexity_score.toFixed(1):'0')+'</div>' +
    '<div class="ic-label">Max Complexity</div></div>' +
    '<div class="insight-card">' +
    '<div class="ic-icon" style="background:linear-gradient(135deg,var(--pink),#db2777)"><svg viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"/><line x1="12" y1="19" x2="20" y2="19"/></svg></div>' +
    '<div class="ic-val" style="color:var(--pink)">'+totalSymbols+'</div>' +
    '<div class="ic-label">Total Symbols</div></div>';
})();
  animateVisibleSection('analysis');

/* Cross-module deps */
(function(){
  var el = document.getElementById('deps-list');
  var countEl = document.getElementById('dep-count');
  if (countEl) countEl.textContent = SURPRISES.length;
  if (SURPRISES.length === 0) { el.innerHTML = '<div style="color:var(--muted);font-size:13px">No cross-module dependencies found</div>'; return; }
  el.innerHTML = SURPRISES.slice(0,15).map(function(s) {
    return '<div class="dep-item"><span class="dep-source">'+escapeHtml(s.source)+'</span><span class="dep-arrow"><svg viewBox="0 0 24 24"><path d="M5 12h14"/><path d="M12 5l7 7-7 7"/></svg></span><span class="dep-target">'+escapeHtml(s.target)+'</span><span class="dep-rel">'+s.relation+'</span></div>';
  }).join('');
})();

/* Complexity table with inline bars and color-coded scores */
(function(){
  var maxScore = COMPLEXITY.length > 0 ? Math.max.apply(null, COMPLEXITY.map(function(c){return c.complexity_score;})) : 1;
  document.getElementById('complex-tbody').innerHTML = COMPLEXITY.slice(0,15).map(function(c) {
    var pct = (c.complexity_score / maxScore * 100).toFixed(0);
    var level = c.complexity_score > maxScore*0.7 ? 'high' : c.complexity_score > maxScore*0.3 ? 'medium' : 'low';
    return '<tr><td><code>'+escapeHtml(c.label)+'</code></td><td>'+c.symbols+'</td><td>'+c.connections+'<span class="inline-bar" style="width:'+Math.min(c.connections*3,60)+'px;background:var(--accent-light)"></span></td><td>'+Number(c.lines).toLocaleString()+'</td><td><span class="score-badge '+level+'">'+c.complexity_score.toFixed(1)+'</span></td></tr>';
  }).join('');
})();

/* AI context complexity stat */
(function(){
  var el = document.getElementById('ctx-complexity');
  if (el && COMPLEXITY.length > 0) {
    var avg = COMPLEXITY.reduce(function(s,c){return s+c.complexity_score;},0) / COMPLEXITY.length;
    el.textContent = avg.toFixed(1) + ' avg';
  }
})();

/* ══════════════════════════════════════════════════════════ */
/* ── AI ASSISTANT ────────────────────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

var aiConnected = false, aiProvider = 'vedaslab', aiModel = '', aiKey = '', aiSending = false, aiMsgCount = 0;

/* Populate provider/model selects */
(function(){
  var provSel = document.getElementById('ai-provider');
  var modSel  = document.getElementById('ai-model');
  var keys = Object.keys(PROVIDERS);
  provSel.innerHTML = keys.map(function(k){ return '<option value="'+k+'">'+PROVIDERS[k].name+'</option>'; }).join('');
  function updateModels() {
    var prov = PROVIDERS[provSel.value];
    if (!prov) return;
    if (provSel.value === 'vedaslab' && prov.models.length === 0) {
      fetch(prov.modelsUrl).then(function(r){return r.json();}).then(function(data) {
        var models = [];
        if (Array.isArray(data)) data.forEach(function(item){ if (typeof item==='string') models.push(item); else if (item&&item.model_id) models.push(item.model_id); });
        else if (data&&data.models) data.models.forEach(function(m){ if (m.model_id) models.push(m.model_id); });
        if (models.length===0) models = ['gpt-4o','gpt-4.1','gemini-2.5-pro','claude-sonnet-4'];
        prov.models = models;
        modSel.innerHTML = models.map(function(m){ return '<option value="'+m+'"'+(m===prov.defaultModel?' selected':'')+'>'+m+'</option>'; }).join('');
      }).catch(function(){
        prov.models = ['gpt-4o','gpt-4.1','gemini-2.5-pro','claude-sonnet-4'];
        modSel.innerHTML = prov.models.map(function(m){ return '<option value="'+m+'">'+m+'</option>'; }).join('');
      });
    } else {
      modSel.innerHTML = prov.models.map(function(m){ return '<option value="'+m+'"'+(m===prov.defaultModel?' selected':'')+'>'+m+'</option>'; }).join('');
    }
  }
  provSel.addEventListener('change', updateModels);
  updateModels();
})();

/* Auto-resize textarea */
var aiMsgEl = document.getElementById('ai-msg');
aiMsgEl.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  document.getElementById('ai-char-count').textContent = this.value.length > 0 ? this.value.length : '';
});

/* Connect button */
document.getElementById('ai-connect').addEventListener('click', function() {
  var key = document.getElementById('ai-key').value.trim();
  var statusEl = document.getElementById('ai-status');
  if (!key) {
    statusEl.innerHTML = '<span class="status-dot"></span> Please enter an API key';
    statusEl.className = 'ai-status err';
    return;
  }
  aiProvider = document.getElementById('ai-provider').value;
  aiModel = document.getElementById('ai-model').value;
  aiKey = key;
  aiConnected = true;
  aiChatHistory = [{role:'system', content: buildContext()}];
  statusEl.innerHTML = '<span class="status-dot"></span> Connected &mdash; ready to chat';
  statusEl.className = 'ai-status ok';
  var badge = document.getElementById('ai-model-badge');
  badge.textContent = aiModel; badge.style.display = 'inline-block';
  document.getElementById('ai-connect-text').textContent = 'Reconnect';
  document.getElementById('ai-msg').disabled = false;
  document.getElementById('ai-send').disabled = false;
  document.getElementById('ai-msg').focus();
  var welcome = document.querySelector('.ai-welcome');
  if (welcome) welcome.style.display = 'none';
});

/* Direct API call */
function callAI(provider, model, key, messages) {
  var prov = PROVIDERS[provider];
  if (!prov) return Promise.reject(new Error('Unknown provider: '+provider));
  if (provider === 'claude') {
    var sysMsg = messages.find(function(m){return m.role==='system';});
    var chatMsgs = messages.filter(function(m){return m.role!=='system';});
    var body = {model:model,max_tokens:4096,system:sysMsg?sysMsg.content:'',messages:chatMsgs.map(function(m){return {role:m.role,content:m.content};})};
    return fetch(prov.baseUrl,{method:'POST',headers:prov.headerFn(key),body:JSON.stringify(body)}).then(function(resp){
      return resp.json().then(function(data){
        if (!resp.ok) throw new Error(data.error&&data.error.message||JSON.stringify(data.error)||'API error '+resp.status);
        if (data.content&&Array.isArray(data.content)){var tb=data.content.find(function(b){return b.type==='text';});return tb?tb.text:JSON.stringify(data.content);}
        return data.content||'No response';
      });
    });
  } else {
    var body2 = {model:model,messages:messages,max_tokens:4096};
    return fetch(prov.baseUrl,{method:'POST',headers:prov.headerFn(key),body:JSON.stringify(body2)}).then(function(resp){
      return resp.json().then(function(data){
        if (!resp.ok) throw new Error(data.error&&data.error.message||JSON.stringify(data.error)||'API error '+resp.status);
        var content = data.choices&&data.choices[0]&&data.choices[0].message&&data.choices[0].message.content;
        if (!content) throw new Error('Empty response from API');
        if (Array.isArray(content)){var tb=content.find(function(b){return b.type==='text';});return tb?tb.text:content.map(function(b){return b.text||'';}).join('');}
        return content;
      });
    });
  }
}

/* Send message */
function sendAIMessage(text) {
  if (!text||!aiConnected||aiSending) return;
  aiSending = true; aiMsgCount++;
  var msgs = document.getElementById('ai-messages');
  var time = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});
  var welcome = document.querySelector('.ai-welcome');
  if (welcome) welcome.style.display = 'none';
  var userDiv = document.createElement('div');
  userDiv.className = 'ai-msg user';
  userDiv.innerHTML = '<div class="ai-msg-row"><div class="ai-avatar">You</div><div><div class="ai-msg-bubble">'+escapeHtml(text)+'</div><div class="ai-msg-footer"><span class="ai-msg-time">'+time+'</span></div></div></div>';
  msgs.appendChild(userDiv);
  var typingDiv = document.createElement('div');
  typingDiv.className = 'ai-msg bot'; typingDiv.id = 'ai-typing-indicator';
  typingDiv.innerHTML = '<div class="ai-msg-row"><div class="ai-avatar">AI</div><div class="ai-msg-bubble"><div class="ai-typing"><span></span><span></span><span></span></div></div></div>';
  msgs.appendChild(typingDiv);
  msgs.scrollTop = msgs.scrollHeight;
  document.getElementById('ai-msg').value = '';
  document.getElementById('ai-msg').style.height = 'auto';
  document.getElementById('ai-char-count').textContent = '';
  document.getElementById('ai-send').disabled = true;
  aiModel = document.getElementById('ai-model').value;
  var badge = document.getElementById('ai-model-badge');
  badge.textContent = aiModel; badge.style.display = 'inline-block';
  aiChatHistory.push({role:'user', content:text});
  var startTime = Date.now();
  callAI(aiProvider, aiModel, aiKey, aiChatHistory)
  .then(function(reply) {
    var elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    if (document.getElementById('ai-typing-indicator')) msgs.removeChild(typingDiv);
    aiChatHistory.push({role:'assistant', content:reply});
    var botDiv = document.createElement('div');
    botDiv.className = 'ai-msg bot';
    var msgId = 'msg-' + aiMsgCount;
    botDiv.innerHTML = '<div class="ai-msg-row"><div class="ai-avatar">AI</div><div style="flex:1;min-width:0"><div class="ai-msg-bubble" id="'+msgId+'">'+formatMarkdown(reply)+'</div><div class="ai-msg-footer"><span class="ai-msg-time">'+new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})+' &middot; '+elapsed+'s</span><div class="ai-msg-actions"><button class="ai-msg-action" title="Copy" onclick="window._copyMsg(\''+msgId+'\')"><svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button></div></div></div></div>';
    msgs.appendChild(botDiv);
    msgs.scrollTop = msgs.scrollHeight;
    botDiv.querySelectorAll('pre').forEach(function(pre) {
      var btn = document.createElement('button');
      btn.className = 'copy-code'; btn.textContent = 'Copy';
      btn.onclick = function(){ var code=pre.querySelector('code')?pre.querySelector('code').textContent:pre.textContent;navigator.clipboard.writeText(code).then(function(){btn.textContent='Copied!';setTimeout(function(){btn.textContent='Copy';},1500);}); };
      pre.style.position = 'relative'; pre.appendChild(btn);
    });
  })
  .catch(function(err) {
    if (document.getElementById('ai-typing-indicator')) msgs.removeChild(typingDiv);
    var errDiv = document.createElement('div');
    errDiv.className = 'ai-msg bot';
    errDiv.innerHTML = '<div class="ai-msg-row"><div class="ai-avatar">AI</div><div class="ai-msg-bubble"><span style="color:var(--red)">Error: '+escapeHtml(err.message)+'</span></div></div>';
    msgs.appendChild(errDiv);
    msgs.scrollTop = msgs.scrollHeight;
    aiChatHistory.pop();
  })
  .finally(function() {
    aiSending = false;
    document.getElementById('ai-send').disabled = false;
    document.getElementById('ai-msg').focus();
  });
}

window._copyMsg = function(id) {
  var el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(function(){
    var btn = el.closest('.ai-msg').querySelector('.ai-msg-action');
    if (btn) { btn.style.color = 'var(--green)'; setTimeout(function(){ btn.style.color = ''; }, 1500); }
  });
};

document.getElementById('ai-send').addEventListener('click', function(){ sendAIMessage(document.getElementById('ai-msg').value.trim()); });
document.getElementById('ai-msg').addEventListener('keydown', function(e){ if (e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendAIMessage(e.target.value.trim());} });

document.querySelectorAll('.ai-suggestion, .ai-welcome-chip').forEach(function(el) {
  el.addEventListener('click', function() {
    if (!aiConnected) { var s=document.getElementById('ai-status'); s.innerHTML='<span class="status-dot"></span> Connect to a provider first'; s.className='ai-status err'; return; }
    sendAIMessage(el.dataset.q);
  });
});

/* Clear chat */
document.getElementById('ai-clear').addEventListener('click', function() {
  var msgs = document.getElementById('ai-messages');
  msgs.innerHTML = '<div class="ai-welcome"><div class="ai-welcome-icon">&#129302;</div><h4>AI Project Assistant</h4><p>Ask anything about your project.</p><div class="ai-welcome-chips"><div class="ai-welcome-chip" data-q="What does this project do?">What does this project do?</div><div class="ai-welcome-chip" data-q="What are the main features?">Main features</div><div class="ai-welcome-chip" data-q="How is the code organized?">Code organization</div><div class="ai-welcome-chip" data-q="What are the most complex parts?">Complex parts</div></div></div>';
  msgs.querySelectorAll('.ai-welcome-chip').forEach(function(el) {
    el.addEventListener('click', function(){ if (!aiConnected){var s=document.getElementById('ai-status');s.innerHTML='<span class="status-dot"></span> Connect first';s.className='ai-status err';return;} sendAIMessage(el.dataset.q); });
  });
  if (aiConnected) { var w=msgs.querySelector('.ai-welcome'); if (w) w.style.display='none'; }
  aiChatHistory = [{role:'system', content: buildContext()}]; aiMsgCount = 0;
});

/* Export chat */
document.getElementById('ai-export').addEventListener('click', function() {
  var msgs = document.getElementById('ai-messages');
  var bubbles = msgs.querySelectorAll('.ai-msg');
  if (bubbles.length === 0) return;
  var txt = '# AI Chat Export\n# ' + new Date().toLocaleString() + '\n# Model: ' + aiModel + '\n\n';
  bubbles.forEach(function(msg) {
    var isUser = msg.classList.contains('user');
    var bubble = msg.querySelector('.ai-msg-bubble');
    if (bubble) txt += (isUser ? '>> You:\n' : '>> AI:\n') + bubble.textContent.trim() + '\n\n';
  });
  var blob = new Blob([txt], {type:'text/plain'});
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'chat-export-' + new Date().toISOString().slice(0,10) + '.txt';
  a.click(); URL.revokeObjectURL(a.href);
});

/* ── Utility functions ───────────────────────────────────── */
function escapeHtml(t) { var d=document.createElement('div');d.textContent=t;return d.innerHTML; }
function formatMarkdown(text) {
  var h = escapeHtml(text);
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, function(m,lang,code){ return '<pre><code class="lang-'+lang+'">'+code+'</code></pre>'; });
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  h = h.replace(/^[-\u2022] (.+)$/gm, '<li>$1</li>');
  h = h.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  h = h.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>');
  h = h.replace(/\n\n/g, '</p><p>');
  h = h.replace(/\n/g, '<br>');
  return '<p>' + h + '</p>';
}
animateVisibleSection('overview');

})();
</script>
</body>
</html>"""
