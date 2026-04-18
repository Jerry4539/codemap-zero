"""Interactive HTML graph visualization — codemap.html.

Generates a polished single-file HTML with embedded data.
Uses vis-network with advanced config + custom dark UI.
"""

from __future__ import annotations

import html as _html
import json
from pathlib import Path
from typing import Any

import networkx as nx

# Softer professional palette — 20 distinguishable hues
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
) -> None:
    """Generate an interactive HTML visualization."""
    if G.number_of_nodes() > 5000:
        raise ValueError(f"Graph has {G.number_of_nodes()} nodes — too large for browser viz.")

    labels = labels or {}

    node_comm: dict[str, int] = {}
    for cid, members in communities.items():
        for m in members:
            node_comm[m] = cid

    # ── Build vis nodes ─────────────────────────────────────────────────
    vis_nodes: list[dict[str, Any]] = []
    for node_id, data in G.nodes(data=True):
        cid = node_comm.get(node_id, 0)
        color = _PALETTE[cid % len(_PALETTE)]
        ntype = data.get("type", "unknown")
        label_text = data.get("label", node_id)
        in_d = G.in_degree(node_id)
        out_d = G.out_degree(node_id)
        degree = in_d + out_d

        vis_nodes.append({
            "id": node_id,
            "label": str(label_text)[:32] + ("..." if len(str(label_text)) > 32 else ""),
            "fullLabel": str(label_text),
            "ntype": ntype,
            "community": cid,
            "communityLabel": labels.get(cid, f"Module {cid}"),
            "color": color,
            "degree": degree,
            "inDeg": in_d,
            "outDeg": out_d,
            "sourceFile": data.get("source_file", ""),
            "signature": data.get("signature", ""),
            "docstring": str(data.get("docstring", ""))[:300],
            "location": data.get("source_location", ""),
        })

    # ── Build vis edges ─────────────────────────────────────────────────
    vis_edges: list[dict[str, Any]] = []
    for u, v, data in G.edges(data=True):
        rel = data.get("relation", "")
        vis_edges.append({"from": u, "to": v, "relation": rel})

    # ── Community legend data ───────────────────────────────────────────
    comm_legend = []
    for cid in sorted(communities.keys()):
        comm_legend.append({
            "id": cid,
            "label": labels.get(cid, f"Module {cid}"),
            "color": _PALETTE[cid % len(_PALETTE)],
            "count": len(communities[cid]),
        })

    stats = {
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "communities": len(communities),
    }

    page = _HTML_TEMPLATE.replace("__NODES_JSON__", json.dumps(vis_nodes))
    page = page.replace("__EDGES_JSON__", json.dumps(vis_edges))
    page = page.replace("__LEGEND_JSON__", json.dumps(comm_legend))
    page = page.replace("__STATS_JSON__", json.dumps(stats))

    Path(output_path).write_text(page, encoding="utf-8")


# ════════════════════════════════════════════════════════════════════════════
# Full HTML template — professional dark theme with sidebar + graph
# ════════════════════════════════════════════════════════════════════════════

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>codemap — Project Graph</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
/* ── Reset & Vars ───────────────────────────────────────────── */
:root {
  --bg:      #0b0d17;
  --surface: #111827;
  --card:    #1f2937;
  --border:  #374151;
  --text:    #f3f4f6;
  --dim:     #9ca3af;
  --muted:   #6b7280;
  --accent:  #6366f1;
  --accent2: #22d3ee;
  --red:     #f87171;
  --green:   #34d399;
  --orange:  #fb923c;
  --pink:    #f472b6;
  --radius:  10px;
  --shadow:  0 4px 24px rgba(0,0,0,.4);
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter','Segoe UI',-apple-system,sans-serif;background:var(--bg);color:var(--text);overflow:hidden;height:100vh}
::selection{background:var(--accent);color:#fff}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

/* ── Layout ─────────────────────────────────────────────────── */
#app{display:grid;grid-template-columns:1fr;grid-template-rows:56px 1fr;height:100vh}
#app.sidebar-open{grid-template-columns:1fr 340px}

/* ── Top Bar ────────────────────────────────────────────────── */
#topbar{grid-column:1/-1;display:flex;align-items:center;gap:16px;padding:0 20px;
  background:var(--surface);border-bottom:1px solid var(--border);z-index:20}
#topbar .brand{display:flex;align-items:center;gap:10px}
#topbar .brand svg{width:22px;height:22px}
#topbar .brand span{font-size:16px;font-weight:700;
  background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
#topbar .sep{width:1px;height:28px;background:var(--border)}

/* Search */
.search-box{position:relative;flex:0 1 260px}
.search-box input{width:100%;padding:7px 12px 7px 34px;border-radius:8px;border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:13px;outline:none;transition:border .2s}
.search-box input:focus{border-color:var(--accent)}
.search-box svg{position:absolute;left:10px;top:50%;transform:translateY(-50%);width:14px;height:14px;color:var(--muted)}

/* Filter chips */
.chips{display:flex;gap:4px;flex-wrap:nowrap}
.chip{padding:5px 12px;border-radius:20px;font-size:12px;font-weight:500;cursor:pointer;
  background:var(--card);border:1px solid var(--border);color:var(--dim);transition:all .2s;white-space:nowrap;user-select:none}
.chip:hover{border-color:var(--accent);color:var(--text)}
.chip.active{background:var(--accent);border-color:var(--accent);color:#fff}

/* Stats badges */
.stat-badges{display:flex;gap:8px;margin-left:auto}
.stat-badge{display:flex;align-items:center;gap:5px;padding:4px 10px;border-radius:6px;
  background:var(--card);font-size:11px;color:var(--dim);border:1px solid var(--border)}
.stat-badge .num{font-weight:700;color:var(--text);font-size:12px}

/* ── Graph ──────────────────────────────────────────────────── */
#graph-wrap{position:relative;overflow:hidden;background:var(--bg)}
#graph-canvas{width:100%;height:100%}

/* Controls floating */
.graph-controls{position:absolute;bottom:20px;left:20px;display:flex;gap:6px;z-index:10}
.ctrl-btn{width:36px;height:36px;border-radius:8px;border:1px solid var(--border);background:var(--surface);
  color:var(--text);display:flex;align-items:center;justify-content:center;cursor:pointer;
  font-size:16px;transition:all .15s;backdrop-filter:blur(8px)}
.ctrl-btn:hover{background:var(--accent);border-color:var(--accent);color:#fff}
.ctrl-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}

/* Legend floating */
.legend-panel{position:absolute;top:16px;left:16px;background:rgba(17,24,39,.92);
  backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:var(--radius);
  padding:14px;max-height:calc(100vh - 140px);overflow-y:auto;z-index:10;min-width:180px;
  transition:opacity .2s,transform .2s}
.legend-panel.hidden{opacity:0;pointer-events:none;transform:translateX(-10px)}
.legend-panel h4{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:10px}
.legend-item{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:12px;cursor:pointer;
  color:var(--dim);transition:color .15s}
.legend-item:hover{color:var(--text)}
.legend-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0}
.legend-count{margin-left:auto;font-size:10px;color:var(--muted)}

/* ── Sidebar ────────────────────────────────────────────────── */
#sidebar{background:var(--surface);border-left:1px solid var(--border);overflow-y:auto;
  padding:0;display:none;animation:slideIn .2s ease}
#app.sidebar-open #sidebar{display:block}
@keyframes slideIn{from{opacity:0;transform:translateX(20px)}to{opacity:1;transform:translateX(0)}}

.sidebar-header{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;
  border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--surface);z-index:5}
.sidebar-header h3{font-size:14px;font-weight:600}
.sidebar-close{width:28px;height:28px;border-radius:6px;border:none;background:var(--card);
  color:var(--dim);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:14px}
.sidebar-close:hover{background:var(--border);color:var(--text)}

.sidebar-section{padding:14px 18px;border-bottom:1px solid var(--border)}
.sidebar-section:last-child{border-bottom:none}
.sidebar-label{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);margin-bottom:6px}
.sidebar-value{font-size:13px;color:var(--text);line-height:1.5}
.sidebar-value code{background:var(--card);padding:2px 6px;border-radius:4px;font-size:12px;color:var(--accent2)}
.sidebar-value .sig{font-family:'Fira Code','Consolas',monospace;font-size:11px;color:var(--green);
  background:var(--card);padding:8px 10px;border-radius:6px;display:block;margin-top:6px;word-break:break-all;line-height:1.6}
.sidebar-value .doc{font-style:italic;color:var(--dim);font-size:12px;line-height:1.5;margin-top:4px}

.type-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;
  font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.5px}
.type-badge.file{background:rgba(99,102,241,.15);color:#818cf8}
.type-badge.class{background:rgba(244,114,182,.15);color:#f472b6}
.type-badge.function{background:rgba(52,211,153,.15);color:#34d399}
.type-badge.method{background:rgba(251,191,36,.15);color:#fbbf24}
.type-badge.document{background:rgba(56,189,248,.15);color:#38bdf8}

.conn-list{list-style:none;margin-top:8px}
.conn-list li{font-size:12px;padding:4px 0;color:var(--dim);display:flex;align-items:center;gap:6px}
.conn-list li .arrow{color:var(--muted);font-size:10px}
.conn-list li .rel{font-size:10px;color:var(--muted);padding:1px 5px;border-radius:3px;background:var(--card)}

/* Loading overlay */
.loading{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  background:var(--bg);z-index:30;transition:opacity .4s}
.loading.done{opacity:0;pointer-events:none}
.spinner{width:36px;height:36px;border:3px solid var(--border);border-top-color:var(--accent);
  border-radius:50%;animation:spin .8s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}

/* Noscript */
.noscript{text-align:center;padding:80px;color:var(--red)}
</style>
</head>
<body>
<div id="app">
  <!-- Top bar -->
  <header id="topbar">
    <div class="brand">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:var(--accent)">
        <circle cx="12" cy="12" r="3"/><path d="M12 2v4m0 12v4M2 12h4m12 0h4M4.93 4.93l2.83 2.83m8.48 8.48l2.83 2.83M4.93 19.07l2.83-2.83m8.48-8.48l2.83-2.83"/>
      </svg>
      <span>codemap</span>
    </div>
    <div class="sep"></div>
    <div class="search-box">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
      <input type="text" id="search" placeholder="Search nodes... (Ctrl+K)">
    </div>
    <div class="chips" id="chips">
      <div class="chip active" data-type="all">All</div>
      <div class="chip" data-type="file">Files</div>
      <div class="chip" data-type="class">Classes</div>
      <div class="chip" data-type="function">Functions</div>
      <div class="chip" data-type="method">Methods</div>
    </div>
    <div class="stat-badges">
      <div class="stat-badge"><span class="num" id="sb-nodes">0</span> nodes</div>
      <div class="stat-badge"><span class="num" id="sb-edges">0</span> edges</div>
      <div class="stat-badge"><span class="num" id="sb-comms">0</span> modules</div>
    </div>
  </header>

  <!-- Graph area -->
  <div id="graph-wrap">
    <div class="loading" id="loader"><div class="spinner"></div></div>
    <div id="graph-canvas"></div>

    <!-- Legend -->
    <div class="legend-panel" id="legend">
      <h4>Modules</h4>
      <div id="legend-items"></div>
    </div>

    <!-- Controls -->
    <div class="graph-controls">
      <button class="ctrl-btn" id="btn-zoomin" title="Zoom in">+</button>
      <button class="ctrl-btn" id="btn-zoomout" title="Zoom out">−</button>
      <button class="ctrl-btn" id="btn-fit" title="Fit all (F)">⊡</button>
      <button class="ctrl-btn" id="btn-physics" title="Toggle physics (P)">⚡</button>
      <button class="ctrl-btn" id="btn-legend" title="Toggle legend (L)">☰</button>
    </div>
  </div>

  <!-- Sidebar (node details) -->
  <div id="sidebar">
    <div class="sidebar-header">
      <h3 id="sb-title">Node Details</h3>
      <button class="sidebar-close" id="sb-close">✕</button>
    </div>
    <div id="sb-content"></div>
  </div>
</div>

<noscript><div class="noscript"><h2>JavaScript required</h2></div></noscript>

<script>
(function(){
'use strict';

const RAW_NODES = __NODES_JSON__;
const RAW_EDGES = __EDGES_JSON__;
const LEGEND    = __LEGEND_JSON__;
const STATS     = __STATS_JSON__;

/* ── Populate stats badges ───────────────────────────────── */
document.getElementById('sb-nodes').textContent = STATS.nodes;
document.getElementById('sb-edges').textContent = STATS.edges;
document.getElementById('sb-comms').textContent  = STATS.communities;

/* ── Populate legend ─────────────────────────────────────── */
const legendEl = document.getElementById('legend-items');
legendEl.innerHTML = LEGEND.map(c =>
  `<div class="legend-item" data-comm="${c.id}">
    <span class="legend-dot" style="background:${c.color}"></span>
    <span>${c.label}</span>
    <span class="legend-count">${c.count}</span>
  </div>`
).join('');

/* ── Edge colors ─────────────────────────────────────────── */
const EDGE_COLORS = {imports:'#f87171',calls:'#22d3ee',contains:'#4b5563',method:'#34d399'};

/* ── Build vis datasets ──────────────────────────────────── */
const nodeMap = {};
const visNodes = RAW_NODES.map(n => {
  const size = Math.max(10, Math.min(45, 10 + n.degree * 3));
  const shapeMap = {file:'dot',class:'diamond',function:'triangle',method:'triangleDown',
    document:'square',config:'star',section:'hexagon'};
  const obj = {
    id: n.id,
    label: n.label,
    size: size,
    shape: shapeMap[n.ntype] || 'dot',
    color: {
      background: n.color,
      border: n.color,
      highlight: {background:'#fff',border:n.color},
      hover: {background:n.color+'dd',border:'#fff'},
    },
    font: {color:'#e5e7eb', size: Math.max(9, Math.min(14, 9 + n.degree)), strokeWidth:3, strokeColor:'#000'},
    borderWidth: 2,
    borderWidthSelected: 3,
    shadow: {enabled:true, color:'rgba(0,0,0,.3)', size:8, x:0, y:2},
    _raw: n,
  };
  nodeMap[n.id] = n;
  return obj;
});

const visEdges = RAW_EDGES.map((e,i) => {
  const c = EDGE_COLORS[e.relation] || '#4b5563';
  return {
    id: 'e'+i,
    from: e.from,
    to: e.to,
    color: {color:c, opacity:0.45, highlight:c, hover:c},
    width: e.relation==='imports'||e.relation==='calls' ? 1.5 : 0.8,
    arrows: (e.relation==='imports'||e.relation==='calls') ? {to:{enabled:true,scaleFactor:0.5}} : {},
    smooth: {type:'continuous'},
    _rel: e.relation,
  };
});

const nodes = new vis.DataSet(visNodes);
const edges = new vis.DataSet(visEdges);

/* ── Create network ──────────────────────────────────────── */
const container = document.getElementById('graph-canvas');
const network = new vis.Network(container, {nodes,edges}, {
  physics: {
    solver: 'forceAtlas2Based',
    forceAtlas2Based: {gravitationalConstant:-40, centralGravity:0.005, springLength:140, springConstant:0.06, avoidOverlap:0.4},
    stabilization: {enabled:true, iterations:300, updateInterval:25},
    maxVelocity:30,
    minVelocity:0.3,
  },
  interaction: {hover:true, tooltipDelay:200, zoomView:true, dragView:true,
    navigationButtons:false, keyboard:{enabled:true}},
  nodes: {chosen:true},
  edges: {chosen:true},
  layout: {improvedLayout:true},
});

/* Hide loader after stabilisation */
network.once('stabilizationIterationsDone', () => {
  document.getElementById('loader').classList.add('done');
});

/* ── State ───────────────────────────────────────────────── */
let physicsOn = true;
let selectedNodeId = null;
let activeType = 'all';
let activeComm = null;
let searchQuery = '';

/* ── Filtering ───────────────────────────────────────────── */
function applyFilters() {
  const q = searchQuery.toLowerCase();
  const updates = [];
  const edgeUpdates = [];
  const hiddenSet = new Set();

  visNodes.forEach(n => {
    const raw = n._raw;
    let show = true;
    if (activeType !== 'all' && raw.ntype !== activeType) show = false;
    if (activeComm !== null && raw.community !== activeComm) show = false;
    if (q) {
      const haystack = (raw.fullLabel + ' ' + raw.communityLabel + ' ' + raw.sourceFile + ' ' + raw.signature + ' ' + raw.docstring).toLowerCase();
      if (!haystack.includes(q)) show = false;
    }
    if (!show) hiddenSet.add(n.id);

    // Highlight matches
    let borderW = 2;
    let fontColor = '#e5e7eb';
    if (q && show) { borderW = 4; fontColor = '#fff'; }
    updates.push({id:n.id, hidden:!show, borderWidth:borderW, font:{color:fontColor, size:n.font.size, strokeWidth:3, strokeColor:'#000'}});
  });

  visEdges.forEach(e => {
    const hide = hiddenSet.has(e.from) || hiddenSet.has(e.to);
    edgeUpdates.push({id:e.id, hidden:hide});
  });

  nodes.update(updates);
  edges.update(edgeUpdates);
}

/* ── Search ──────────────────────────────────────────────── */
const searchInput = document.getElementById('search');
searchInput.addEventListener('input', e => { searchQuery = e.target.value; applyFilters(); });

/* ── Chip filters ────────────────────────────────────────── */
document.querySelectorAll('.chip').forEach(chip => {
  chip.addEventListener('click', () => {
    document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
    chip.classList.add('active');
    activeType = chip.dataset.type;
    applyFilters();
  });
});

/* ── Legend click → filter community ─────────────────────── */
document.querySelectorAll('.legend-item').forEach(item => {
  item.addEventListener('click', () => {
    const cid = parseInt(item.dataset.comm);
    if (activeComm === cid) {
      activeComm = null;
      document.querySelectorAll('.legend-item').forEach(i => i.style.opacity = '1');
    } else {
      activeComm = cid;
      document.querySelectorAll('.legend-item').forEach(i => { i.style.opacity = parseInt(i.dataset.comm)===cid ? '1' : '0.35'; });
    }
    applyFilters();
  });
});

/* ── Node click → sidebar ────────────────────────────────── */
network.on('click', function(e) {
  if (e.nodes.length > 0) {
    selectedNodeId = e.nodes[0];
    showSidebar(selectedNodeId);
    highlightNeighbors(selectedNodeId);
  } else {
    closeSidebar();
    resetHighlight();
  }
});

network.on('doubleClick', function(e) {
  if (e.nodes.length > 0) {
    network.focus(e.nodes[0], {scale:1.5, animation:{duration:400,easingFunction:'easeInOutQuad'}});
  }
});

function highlightNeighbors(nodeId) {
  const connected = network.getConnectedNodes(nodeId);
  const connSet = new Set(connected);
  connSet.add(nodeId);

  const nUpdates = visNodes.map(n => ({
    id: n.id,
    opacity: connSet.has(n.id) ? 1.0 : 0.12,
  }));
  const eUpdates = visEdges.map(e => ({
    id: e.id,
    color: {
      ...e.color,
      opacity: (e.from === nodeId || e.to === nodeId) ? 0.9 : 0.05,
    },
    width: (e.from === nodeId || e.to === nodeId) ? 2.5 : e.width,
  }));
  nodes.update(nUpdates);
  edges.update(eUpdates);
}

function resetHighlight() {
  const nUpdates = visNodes.map(n => ({id:n.id, opacity:1.0}));
  const eUpdates = visEdges.map(e => ({
    id:e.id,
    color:{...e.color, opacity:0.45},
    width: e._rel==='imports'||e._rel==='calls' ? 1.5 : 0.8,
  }));
  nodes.update(nUpdates);
  edges.update(eUpdates);
}

/* ── Sidebar rendering ───────────────────────────────────── */
function showSidebar(nodeId) {
  const raw = nodeMap[nodeId];
  if (!raw) return;
  document.getElementById('app').classList.add('sidebar-open');

  document.getElementById('sb-title').textContent = raw.fullLabel;

  const incoming = [];
  const outgoing = [];
  RAW_EDGES.forEach(e => {
    if (e.to === nodeId)   incoming.push({node: nodeMap[e.from]?.fullLabel || e.from, rel: e.relation});
    if (e.from === nodeId) outgoing.push({node: nodeMap[e.to]?.fullLabel || e.to,     rel: e.relation});
  });

  let html = '';
  html += `<div class="sidebar-section">
    <div class="sidebar-label">Type</div>
    <div class="sidebar-value"><span class="type-badge ${raw.ntype}">${raw.ntype}</span></div>
  </div>`;

  html += `<div class="sidebar-section">
    <div class="sidebar-label">Module</div>
    <div class="sidebar-value"><span class="legend-dot" style="background:${raw.color};display:inline-block;width:8px;height:8px;border-radius:50%;vertical-align:middle;margin-right:4px"></span> ${raw.communityLabel}</div>
  </div>`;

  if (raw.sourceFile) {
    html += `<div class="sidebar-section">
      <div class="sidebar-label">File</div>
      <div class="sidebar-value"><code>${raw.sourceFile}</code>${raw.location ? ' : '+raw.location : ''}</div>
    </div>`;
  }

  if (raw.signature) {
    html += `<div class="sidebar-section">
      <div class="sidebar-label">Signature</div>
      <div class="sidebar-value"><span class="sig">${raw.signature}</span></div>
    </div>`;
  }

  if (raw.docstring) {
    html += `<div class="sidebar-section">
      <div class="sidebar-label">Documentation</div>
      <div class="sidebar-value"><span class="doc">${raw.docstring}</span></div>
    </div>`;
  }

  html += `<div class="sidebar-section">
    <div class="sidebar-label">Connections</div>
    <div class="sidebar-value" style="font-size:12px;color:var(--dim)">
      ${raw.inDeg} incoming · ${raw.outDeg} outgoing · ${raw.degree} total
    </div>`;

  if (incoming.length > 0) {
    html += `<div style="margin-top:8px;font-size:11px;color:var(--muted)">INCOMING</div><ul class="conn-list">`;
    incoming.slice(0,15).forEach(c => {
      html += `<li><span class="arrow">←</span> ${c.node} <span class="rel">${c.rel}</span></li>`;
    });
    if (incoming.length > 15) html += `<li style="color:var(--muted)">+${incoming.length-15} more</li>`;
    html += '</ul>';
  }
  if (outgoing.length > 0) {
    html += `<div style="margin-top:8px;font-size:11px;color:var(--muted)">OUTGOING</div><ul class="conn-list">`;
    outgoing.slice(0,15).forEach(c => {
      html += `<li><span class="arrow">→</span> ${c.node} <span class="rel">${c.rel}</span></li>`;
    });
    if (outgoing.length > 15) html += `<li style="color:var(--muted)">+${outgoing.length-15} more</li>`;
    html += '</ul>';
  }
  html += '</div>';

  document.getElementById('sb-content').innerHTML = html;
}

function closeSidebar() {
  document.getElementById('app').classList.remove('sidebar-open');
  selectedNodeId = null;
}
document.getElementById('sb-close').addEventListener('click', () => { closeSidebar(); resetHighlight(); });

/* ── Control buttons ─────────────────────────────────────── */
document.getElementById('btn-zoomin').addEventListener('click', () => {
  const s = network.getScale(); network.moveTo({scale:s*1.3, animation:{duration:200}});
});
document.getElementById('btn-zoomout').addEventListener('click', () => {
  const s = network.getScale(); network.moveTo({scale:s/1.3, animation:{duration:200}});
});
document.getElementById('btn-fit').addEventListener('click', () => {
  network.fit({animation:{duration:400,easingFunction:'easeInOutQuad'}});
});
document.getElementById('btn-physics').addEventListener('click', function() {
  physicsOn = !physicsOn;
  network.setOptions({physics:{enabled:physicsOn}});
  this.classList.toggle('active', physicsOn);
});
document.getElementById('btn-legend').addEventListener('click', () => {
  document.getElementById('legend').classList.toggle('hidden');
});

/* ── Keyboard shortcuts ──────────────────────────────────── */
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'f' || e.key === 'F') { network.fit({animation:{duration:400}}); }
  if (e.key === 'p' || e.key === 'P') { document.getElementById('btn-physics').click(); }
  if (e.key === 'l' || e.key === 'L') { document.getElementById('btn-legend').click(); }
  if (e.key === 'Escape') { closeSidebar(); resetHighlight(); activeComm=null; document.querySelectorAll('.legend-item').forEach(i=>i.style.opacity='1'); applyFilters(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); searchInput.focus(); }
});

/* ── Init physics button state ───────────────────────────── */
document.getElementById('btn-physics').classList.add('active');
})();
</script>
</body>
</html>"""
