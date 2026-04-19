"""codemap-zero web server — professional dashboard UI.

Uses Flask to serve a polished single-page dashboard with:
  - Overview with animated stat cards
  - Module explorer with cohesion bars & expandable details
  - Full interactive graph (vis-network)
  - Analysis tables + dependency flow
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

try:
    from flask import Flask, render_template_string, jsonify, request
except ImportError:
    Flask = None  # type: ignore


_PALETTE = [
    "#6366f1", "#22d3ee", "#f472b6", "#34d399", "#fb923c",
    "#a78bfa", "#facc15", "#f87171", "#2dd4bf", "#818cf8",
    "#c084fc", "#4ade80", "#fbbf24", "#f97316", "#38bdf8",
    "#e879f9", "#a3e635", "#fb7185", "#67e8f9", "#d946ef",
]


def create_app(scan_results: dict[str, Any], output_dir: str) -> "Flask":
    """Create and configure the Flask app."""
    if Flask is None:
        raise ImportError("Flask is required. Install with: pip install codemap-zero[web]")

    app = Flask(__name__)

    G: nx.DiGraph = scan_results["G"]
    detection = scan_results["detection"]
    communities = scan_results["communities"]
    labels = scan_results["labels"]
    cohesion = scan_results["cohesion"]
    gods = scan_results["gods"]
    entry_points = scan_results["entry_points"]
    complexity = scan_results["complexity"]
    surprises = scan_results["surprises"]

    @app.route("/")
    def index():
        return render_template_string(
            _DASHBOARD_HTML,
            project_name=detection.get("project_name", "Project"),
            project_type=detection.get("project_type", "unknown"),
            project_desc=detection.get("project_description", ""),
            total_files=detection.get("total_files", 0),
            total_lines=detection.get("total_lines", 0),
            node_count=G.number_of_nodes(),
            edge_count=G.number_of_edges(),
            community_count=len(communities),
            frameworks=detection.get("frameworks", []),
        )

    @app.route("/api/graph")
    def api_graph():
        node_comm: dict[str, int] = {}
        for cid, members in communities.items():
            for m in members:
                node_comm[m] = cid
        nodes_out = []
        for nid, data in G.nodes(data=True):
            cid = node_comm.get(nid, 0)
            nodes_out.append({
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
        edges_out = []
        for u, v, data in G.edges(data=True):
            edges_out.append({"source": u, "target": v, "relation": data.get("relation", "")})
        return jsonify({"nodes": nodes_out, "edges": edges_out})

    @app.route("/api/stats")
    def api_stats():
        return jsonify({
            "project_name": detection.get("project_name", "?"),
            "project_type": detection.get("project_type", "?"),
            "total_files": detection.get("total_files", 0),
            "total_lines": detection.get("total_lines", 0),
            "node_count": G.number_of_nodes(),
            "edge_count": G.number_of_edges(),
            "community_count": len(communities),
            "frameworks": detection.get("frameworks", []),
        })

    @app.route("/api/communities")
    def api_communities():
        result = []
        for cid, members in sorted(communities.items(), key=lambda x: len(x[1]), reverse=True):
            file_nodes = []
            sym_nodes = []
            for m in members:
                data = G.nodes.get(m, {})
                item = {"id": m, "label": data.get("label", m), "type": data.get("type", ""),
                        "signature": data.get("signature", ""), "docstring": str(data.get("docstring", ""))[:120]}
                if data.get("type") == "file":
                    file_nodes.append(item)
                else:
                    sym_nodes.append(item)
            result.append({
                "id": cid,
                "label": labels.get(cid, f"Module {cid}"),
                "color": _PALETTE[cid % len(_PALETTE)],
                "size": len(members),
                "cohesion": round(cohesion.get(cid, 0), 3),
                "files": file_nodes,
                "symbols": sym_nodes[:30],
            })
        return jsonify(result)

    @app.route("/api/gods")
    def api_gods():
        return jsonify(gods[:20])

    @app.route("/api/complexity")
    def api_complexity():
        return jsonify(complexity[:20])

    @app.route("/api/surprises")
    def api_surprises():
        return jsonify(surprises[:20])

    @app.route("/api/entry_points")
    def api_entry_points():
        return jsonify(entry_points[:10])

    # ── AI Chat endpoints ───────────────────────────────────────────────
    _ai_sessions: dict[str, Any] = {}  # provider_key → AIAssistant

    @app.route("/api/providers")
    def api_providers():
        from codemap.assistant import PROVIDERS, fetch_vedaslab_models
        out = []
        for key, p in PROVIDERS.items():
            models = p["models"]
            if key == "vedaslab":
                # Fetch live model list from VedasLab
                live = fetch_vedaslab_models()
                if live:
                    models = live
            out.append({"key": key, "name": p["name"], "models": models, "default_model": p["default_model"]})
        return jsonify(out)

    @app.route("/api/chat", methods=["POST"])
    def api_chat():
        data = request.get_json(silent=True)
        if not data or "message" not in data:
            return jsonify({"error": "message is required"}), 400

        provider = data.get("provider", "vedaslab")
        model = data.get("model")
        api_key = data.get("api_key", "")
        message = data["message"].strip()

        if not api_key:
            return jsonify({"error": "API key is required"}), 400
        if not message:
            return jsonify({"error": "Message cannot be empty"}), 400

        # Re-use or create session per provider+key combo
        session_key = f"{provider}:{api_key[:8]}"
        if session_key not in _ai_sessions:
            try:
                from codemap.assistant import AIAssistant
                _ai_sessions[session_key] = AIAssistant(
                    api_key=api_key,
                    provider=provider,
                    model=model,
                    scan_results=scan_results,
                )
            except (ImportError, ValueError) as e:
                return jsonify({"error": str(e)}), 400

        assistant = _ai_sessions[session_key]
        # Update model if changed
        if model and model != assistant.model:
            assistant.model = model

        answer = assistant.ask(message)
        return jsonify({"reply": answer})

    @app.route("/api/chat/reset", methods=["POST"])
    def api_chat_reset():
        _ai_sessions.clear()
        return jsonify({"status": "ok"})

    return app


# ════════════════════════════════════════════════════════════════════════════
# Dashboard HTML
# ════════════════════════════════════════════════════════════════════════════

_DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{ project_name }} — codemap-zero</title>
<script src="https://unpkg.com/vis-network@9.1.9/standalone/umd/vis-network.min.js"></script>
<style>
/* ── Reset & Vars ───────────────────────────────────────────── */
:root{
  --bg:#0b0d17;--surface:#111827;--card:#1f2937;--card-hover:#263347;
  --border:#374151;--border-light:#4b5563;
  --text:#f3f4f6;--dim:#9ca3af;--muted:#6b7280;
  --accent:#6366f1;--accent-light:#818cf8;--accent-glow:rgba(99,102,241,.2);
  --cyan:#22d3ee;--green:#34d399;--pink:#f472b6;--orange:#fb923c;--red:#f87171;--yellow:#facc15;
  --radius:12px;--radius-sm:8px;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Inter','Segoe UI',-apple-system,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
::selection{background:var(--accent);color:#fff}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:transparent}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
a{color:var(--accent-light);text-decoration:none}

/* ── Nav ────────────────────────────────────────────────────── */
nav{display:flex;align-items:center;padding:0 28px;height:60px;
  background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:50}
.nav-brand{display:flex;align-items:center;gap:10px}
.nav-brand .icon{width:28px;height:28px;border-radius:8px;
  background:linear-gradient(135deg,var(--accent),var(--cyan));display:flex;align-items:center;justify-content:center;font-weight:900;font-size:14px;color:#fff}
.nav-brand h1{font-size:17px;font-weight:700;
  background:linear-gradient(135deg,var(--accent-light),var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.nav-meta{margin-left:16px;font-size:12px;color:var(--muted);display:flex;align-items:center;gap:8px}
.nav-meta .dot{width:4px;height:4px;border-radius:50%;background:var(--border-light)}
.nav-tabs{display:flex;gap:2px;margin-left:auto;background:var(--card);padding:3px;border-radius:10px}
.nav-tab{padding:7px 18px;border-radius:8px;font-size:13px;font-weight:500;cursor:pointer;
  color:var(--dim);transition:all .2s;user-select:none}
.nav-tab:hover{color:var(--text)}
.nav-tab.active{background:var(--accent);color:#fff;box-shadow:0 2px 8px rgba(99,102,241,.3)}

/* ── Pages ──────────────────────────────────────────────────── */
.page{display:none;padding:28px;max-width:1400px;margin:0 auto;animation:fadeIn .3s ease}
.page.active{display:block}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ── Grid ───────────────────────────────────────────────────── */
.grid{display:grid;gap:20px}
.g2{grid-template-columns:1fr 1fr}
.g3{grid-template-columns:1fr 1fr 1fr}
.g4{grid-template-columns:repeat(4,1fr)}
@media(max-width:1024px){.g3,.g4{grid-template-columns:1fr 1fr}}
@media(max-width:700px){.g2,.g3,.g4{grid-template-columns:1fr}}

/* ── Stat Cards ─────────────────────────────────────────────── */
.stat-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);
  padding:22px;position:relative;overflow:hidden;transition:border-color .2s,transform .2s}
.stat-card:hover{border-color:var(--border-light);transform:translateY(-2px)}
.stat-card .glow{position:absolute;top:-30px;right:-30px;width:100px;height:100px;border-radius:50%;opacity:.12;filter:blur(30px)}
.stat-card .label{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);margin-bottom:10px;font-weight:600}
.stat-card .value{font-size:38px;font-weight:800;line-height:1;letter-spacing:-1px}
.stat-card .sub{font-size:12px;color:var(--dim);margin-top:6px}

/* ── Cards ──────────────────────────────────────────────────── */
.card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;transition:border-color .2s}
.card:hover{border-color:var(--border-light)}
.card-header{padding:16px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between}
.card-header h3{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--dim)}
.card-header .badge{font-size:11px;padding:2px 8px;border-radius:10px;background:var(--accent-glow);color:var(--accent-light);font-weight:600}
.card-body{padding:16px 20px}

/* ── List Items ─────────────────────────────────────────────── */
.list-item{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid rgba(55,65,81,.5)}
.list-item:last-child{border-bottom:none}
.list-rank{width:22px;height:22px;border-radius:6px;background:var(--surface);display:flex;align-items:center;
  justify-content:center;font-size:10px;font-weight:700;color:var(--muted);flex-shrink:0}
.list-info{flex:1;min-width:0}
.list-info .name{font-size:13px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.list-info .meta{font-size:11px;color:var(--muted);margin-top:2px}
.list-badge{padding:3px 8px;border-radius:6px;font-size:10px;font-weight:600;text-transform:uppercase;flex-shrink:0}
.list-badge.file{background:rgba(99,102,241,.12);color:var(--accent-light)}
.list-badge.class{background:rgba(244,114,182,.12);color:var(--pink)}
.list-badge.function{background:rgba(52,211,153,.12);color:var(--green)}
.list-val{font-size:13px;font-weight:700;color:var(--text);flex-shrink:0;min-width:40px;text-align:right}

/* ── Bar Chart ──────────────────────────────────────────────── */
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px}
.bar-label{font-size:12px;color:var(--dim);width:100px;text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0}
.bar-track{flex:1;height:22px;background:var(--surface);border-radius:4px;overflow:hidden;position:relative}
.bar-fill{height:100%;border-radius:4px;transition:width .6s ease;display:flex;align-items:center;padding-left:8px;font-size:10px;font-weight:600;color:#fff;min-width:fit-content}
.bar-val{font-size:11px;color:var(--muted);width:50px;text-align:right;flex-shrink:0}

/* ── Module Cards ───────────────────────────────────────────── */
.mod-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;
  transition:border-color .2s}
.mod-card:hover{border-color:var(--border-light)}
.mod-header{padding:16px 20px;display:flex;align-items:center;gap:14px;cursor:pointer;user-select:none}
.mod-dot{width:14px;height:14px;border-radius:50%;flex-shrink:0;box-shadow:0 0 8px rgba(0,0,0,.3)}
.mod-title{font-size:15px;font-weight:600;flex:1}
.mod-stats{display:flex;gap:12px;font-size:12px;color:var(--muted)}
.mod-stats span{display:flex;align-items:center;gap:4px}
.mod-chevron{color:var(--muted);transition:transform .2s;font-size:12px}
.mod-card.open .mod-chevron{transform:rotate(90deg)}
.mod-body{max-height:0;overflow:hidden;transition:max-height .3s ease;border-top:0 solid var(--border)}
.mod-card.open .mod-body{max-height:600px;border-top-width:1px}
.mod-inner{padding:16px 20px}
.cohesion-bar{height:6px;background:var(--surface);border-radius:3px;overflow:hidden;margin-bottom:14px}
.cohesion-fill{height:100%;border-radius:3px;transition:width .6s ease}
.mod-files{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}
.mod-file{padding:4px 10px;border-radius:6px;font-size:11px;font-family:'Consolas','Fira Code',monospace;
  background:var(--surface);border:1px solid var(--border);color:var(--dim);transition:all .15s}
.mod-file:hover{border-color:var(--accent);color:var(--text)}
.mod-symbols{margin-top:10px}
.mod-sym{font-size:11px;padding:4px 0;color:var(--dim);font-family:'Consolas','Fira Code',monospace}
.mod-sym .sym-type{display:inline-block;width:50px;font-size:9px;text-transform:uppercase;color:var(--muted)}

/* ── Graph Page ─────────────────────────────────────────────── */
#graph-container{width:100%;height:calc(100vh - 130px);border:1px solid var(--border);border-radius:var(--radius);
  overflow:hidden;background:var(--surface);position:relative}
.graph-toolbar{display:flex;gap:8px;margin-bottom:16px;align-items:center;flex-wrap:wrap}
.graph-toolbar input{padding:7px 14px;border-radius:var(--radius-sm);border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:13px;width:240px;outline:none;transition:border .2s}
.graph-toolbar input:focus{border-color:var(--accent)}
.graph-toolbar select{padding:7px 10px;border-radius:var(--radius-sm);border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:12px;outline:none;cursor:pointer}
.graph-toolbar .spacer{flex:1}
.graph-toolbar .info{font-size:12px;color:var(--muted)}
.graph-btn{padding:7px 14px;border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--card);
  color:var(--dim);font-size:12px;cursor:pointer;transition:all .15s;font-weight:500}
.graph-btn:hover{border-color:var(--accent);color:var(--text)}
.graph-btn.active{background:var(--accent);border-color:var(--accent);color:#fff}

/* Node detail panel (inside graph) */
.node-panel{position:absolute;top:16px;right:16px;width:300px;background:rgba(17,24,39,.95);
  backdrop-filter:blur(12px);border:1px solid var(--border);border-radius:var(--radius);
  padding:18px;z-index:10;display:none;animation:fadeIn .2s ease;max-height:calc(100% - 32px);overflow-y:auto}
.node-panel.show{display:block}
.node-panel h4{font-size:14px;font-weight:600;margin-bottom:12px;padding-right:24px}
.node-panel .close{position:absolute;top:12px;right:12px;width:24px;height:24px;border-radius:6px;border:none;
  background:var(--card);color:var(--dim);cursor:pointer;display:flex;align-items:center;justify-content:center;font-size:12px}
.node-panel .close:hover{background:var(--border);color:var(--text)}
.np-row{margin-bottom:10px}
.np-label{font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin-bottom:3px}
.np-val{font-size:12px;color:var(--text);line-height:1.5}
.np-val code{background:var(--card);padding:1px 5px;border-radius:4px;font-size:11px;color:var(--cyan)}
.np-val .sig{font-family:'Consolas','Fira Code',monospace;font-size:11px;color:var(--green);
  background:var(--card);padding:6px 8px;border-radius:6px;display:block;margin-top:4px;word-break:break-all}

/* ── Table ──────────────────────────────────────────────────── */
table{width:100%;border-collapse:collapse}
th{font-size:10px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);font-weight:600;
  padding:10px 14px;text-align:left;border-bottom:1px solid var(--border);cursor:pointer;user-select:none}
th:hover{color:var(--text)}
td{padding:10px 14px;font-size:13px;border-bottom:1px solid rgba(55,65,81,.4)}
tr:hover td{background:rgba(99,102,241,.04)}
td code{background:var(--surface);padding:1px 6px;border-radius:4px;font-size:12px}

/* ── Dep Flow ───────────────────────────────────────────────── */
.dep-item{display:flex;align-items:center;gap:10px;padding:10px 0;border-bottom:1px solid rgba(55,65,81,.4)}
.dep-item:last-child{border-bottom:none}
.dep-source{font-size:12px;font-weight:500;color:var(--text);text-align:right;flex:1;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dep-arrow{color:var(--accent);font-size:16px;flex-shrink:0;font-weight:300}
.dep-target{font-size:12px;font-weight:500;color:var(--text);flex:1;min-width:0;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.dep-rel{font-size:10px;padding:2px 6px;border-radius:4px;background:var(--surface);color:var(--muted);flex-shrink:0}

/* ── Entry Points ───────────────────────────────────────────── */
.entry-item{display:flex;align-items:center;gap:10px;padding:8px 0}
.entry-icon{width:8px;height:8px;border-radius:50%;background:var(--green);flex-shrink:0;box-shadow:0 0 6px rgba(52,211,153,.4)}
.entry-name{font-size:13px;font-family:'Consolas','Fira Code',monospace}

/* ── Footer ─────────────────────────────────────────────────── */
.page-footer{text-align:center;padding:24px;font-size:11px;color:var(--muted)}

/* ── AI Chat ────────────────────────────────────────────────── */
.ai-page-wrap{display:grid;grid-template-columns:320px 1fr;gap:0;height:calc(100vh - 130px);border-radius:var(--radius);overflow:hidden;border:1px solid var(--border)}
@media(max-width:900px){.ai-page-wrap{grid-template-columns:1fr;height:auto}}

/* ── Sidebar ────────────────────────────────────────────────── */
.ai-sidebar{background:var(--surface);display:flex;flex-direction:column;border-right:1px solid var(--border);overflow:hidden}
.ai-sidebar-header{padding:18px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px}
.ai-sidebar-header .sidebar-icon{width:32px;height:32px;border-radius:10px;
  background:linear-gradient(135deg,var(--accent),var(--cyan));display:flex;align-items:center;justify-content:center}
.ai-sidebar-header .sidebar-icon svg{width:18px;height:18px;color:#fff}
.ai-sidebar-header h3{font-size:14px;font-weight:700;color:var(--text)}
.ai-sidebar-scroll{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:18px}
.ai-field-group{display:flex;flex-direction:column;gap:5px}
.ai-label{display:block;font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);font-weight:600}
.ai-select{width:100%;padding:10px 12px;border-radius:var(--radius-sm);border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:13px;outline:none;cursor:pointer;transition:border .2s;appearance:none;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat:no-repeat;background-position:right 12px center}
.ai-select:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.ai-input{width:100%;padding:10px 12px;border-radius:var(--radius-sm);border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:13px;outline:none;transition:border .2s}
.ai-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.ai-key-hint{font-size:10px;color:var(--muted);margin-top:3px;display:flex;align-items:center;gap:4px}
.ai-key-hint svg{width:10px;height:10px;flex-shrink:0}
.ai-connect-btn{padding:11px;border-radius:var(--radius-sm);border:none;width:100%;
  background:linear-gradient(135deg,var(--accent),var(--cyan));color:#fff;font-size:13px;font-weight:600;
  cursor:pointer;transition:all .2s;letter-spacing:.3px}
.ai-connect-btn:hover{opacity:.9;transform:translateY(-1px);box-shadow:0 4px 12px rgba(99,102,241,.3)}
.ai-connect-btn:active{transform:scale(.98)}
.ai-connect-btn:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}
.ai-status{font-size:12px;min-height:18px;display:flex;align-items:center;gap:6px}
.ai-status.ok{color:var(--green)}
.ai-status.err{color:var(--red)}
.ai-status .status-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0}
.ai-status.ok .status-dot{background:var(--green);box-shadow:0 0 6px rgba(52,211,153,.5)}
.ai-status.err .status-dot{background:var(--red)}

.ai-divider{height:1px;background:var(--border);margin:2px 0}

.ai-suggestions-section h4{font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:var(--muted);font-weight:600;margin-bottom:8px}
.ai-suggestion{padding:9px 12px;border-radius:var(--radius-sm);font-size:12px;color:var(--dim);line-height:1.4;
  cursor:pointer;transition:all .2s;border:1px solid transparent;margin-bottom:4px;display:flex;align-items:center;gap:8px}
.ai-suggestion::before{content:'→';color:var(--accent);font-size:11px;opacity:0;transition:opacity .2s}
.ai-suggestion:hover{background:var(--card);border-color:var(--border);color:var(--text)}
.ai-suggestion:hover::before{opacity:1}

.ai-sidebar-footer{padding:12px 20px;border-top:1px solid var(--border);font-size:10px;color:var(--muted);text-align:center}

/* ── Chat Panel ─────────────────────────────────────────────── */
.ai-chat-panel{display:flex;flex-direction:column;background:var(--bg);overflow:hidden}
.ai-chat-header{padding:14px 20px;border-bottom:1px solid var(--border);display:flex;align-items:center;
  justify-content:space-between;background:var(--surface);flex-shrink:0}
.ai-chat-header h3{font-size:13px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;color:var(--dim);display:flex;align-items:center;gap:8px}
.ai-chat-header .model-badge{font-size:10px;padding:3px 8px;border-radius:6px;background:var(--accent-glow);color:var(--accent-light);font-weight:600}
.ai-chat-actions{display:flex;gap:6px}
.ai-action-btn{padding:5px 10px;border-radius:6px;border:1px solid var(--border);background:var(--card);
  color:var(--dim);font-size:11px;cursor:pointer;transition:all .15s;display:flex;align-items:center;gap:4px}
.ai-action-btn:hover{border-color:var(--accent);color:var(--text)}
.ai-action-btn svg{width:12px;height:12px}

.ai-messages{flex:1;overflow-y:auto;padding:24px;display:flex;flex-direction:column;gap:20px;
  scroll-behavior:smooth;overscroll-behavior:contain}
.ai-messages::-webkit-scrollbar{width:5px}
.ai-messages::-webkit-scrollbar-track{background:transparent}
.ai-messages::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}

.ai-welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;
  height:100%;text-align:center;color:var(--text);gap:8px}
.ai-welcome-icon{width:64px;height:64px;border-radius:20px;
  background:linear-gradient(135deg,var(--accent-glow),rgba(34,211,238,.1));
  display:flex;align-items:center;justify-content:center;font-size:32px;margin-bottom:4px}
.ai-welcome h4{font-size:18px;font-weight:700}
.ai-welcome p{color:var(--dim);font-size:13px;max-width:420px;line-height:1.6}
.ai-welcome-chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px;justify-content:center;max-width:480px}
.ai-welcome-chip{padding:8px 14px;border-radius:20px;font-size:12px;color:var(--dim);
  border:1px solid var(--border);cursor:pointer;transition:all .2s}
.ai-welcome-chip:hover{border-color:var(--accent);color:var(--accent-light);background:var(--accent-glow)}

/* ── Chat Bubbles (enhanced) ────────────────────────────────── */
.ai-msg{max-width:78%;animation:msgIn .3s ease;position:relative}
.ai-msg.user{align-self:flex-end}
.ai-msg.bot{align-self:flex-start}
@keyframes msgIn{from{opacity:0;transform:translateY(12px)}to{opacity:1;transform:translateY(0)}}

.ai-msg-row{display:flex;align-items:flex-end;gap:8px}
.ai-msg.user .ai-msg-row{flex-direction:row-reverse}
.ai-avatar{width:28px;height:28px;border-radius:8px;display:flex;align-items:center;justify-content:center;
  font-size:13px;flex-shrink:0;font-weight:700}
.ai-msg.bot .ai-avatar{background:linear-gradient(135deg,var(--accent),var(--cyan));color:#fff}
.ai-msg.user .ai-avatar{background:var(--card);color:var(--dim);border:1px solid var(--border)}

.ai-msg-bubble{padding:12px 16px;border-radius:16px;font-size:13px;line-height:1.7;word-break:break-word;position:relative}
.ai-msg.user .ai-msg-bubble{background:linear-gradient(135deg,var(--accent),#7c3aed);color:#fff;
  border-bottom-right-radius:4px;box-shadow:0 2px 8px rgba(99,102,241,.2)}
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
.ai-msg-action svg{width:12px;height:12px}

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
.ai-msg-bubble p{margin:6px 0}
.ai-msg-bubble p:first-child{margin-top:0}
.ai-msg-bubble p:last-child{margin-bottom:0}
.ai-msg-bubble ul,.ai-msg-bubble ol{margin:8px 0;padding-left:20px}
.ai-msg-bubble li{margin:3px 0}
.ai-msg-bubble strong{color:var(--accent-light)}
.ai-msg-bubble h1,.ai-msg-bubble h2,.ai-msg-bubble h3{font-size:14px;font-weight:700;margin:10px 0 6px;color:var(--text)}

/* ── Typing ─────────────────────────────────────────────────── */
.ai-typing{display:flex;gap:5px;padding:4px 0}
.ai-typing span{width:7px;height:7px;border-radius:50%;background:var(--accent-light);animation:typing 1.4s infinite}
.ai-typing span:nth-child(2){animation-delay:.2s}
.ai-typing span:nth-child(3){animation-delay:.4s}
@keyframes typing{0%,70%,100%{opacity:.25;transform:scale(.85)}35%{opacity:1;transform:scale(1.1)}}

/* ── Input Bar ──────────────────────────────────────────────── */
.ai-input-bar{display:flex;gap:8px;padding:14px 20px;border-top:1px solid var(--border);
  background:var(--surface);align-items:flex-end;flex-shrink:0}
.ai-msg-input{flex:1;padding:10px 16px;border-radius:20px;border:1px solid var(--border);
  background:var(--card);color:var(--text);font-size:13px;outline:none;transition:all .2s;
  max-height:120px;resize:none;line-height:1.5;font-family:inherit;overflow-y:auto}
.ai-msg-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-glow)}
.ai-msg-input:disabled{opacity:.4}
.ai-msg-input::placeholder{color:var(--muted)}
.ai-send-btn{width:40px;height:40px;border-radius:50%;border:none;
  background:linear-gradient(135deg,var(--accent),#7c3aed);
  color:#fff;cursor:pointer;display:flex;align-items:center;justify-content:center;
  transition:all .2s;flex-shrink:0;box-shadow:0 2px 8px rgba(99,102,241,.25)}
.ai-send-btn:hover{transform:scale(1.05);box-shadow:0 4px 12px rgba(99,102,241,.35)}
.ai-send-btn:active{transform:scale(.92)}
.ai-send-btn:disabled{opacity:.25;cursor:not-allowed;transform:none;box-shadow:none}
.ai-char-count{font-size:10px;color:var(--muted);flex-shrink:0;align-self:center;min-width:40px;text-align:right}
</style>
</head>
<body>

<!-- Nav -->
<nav>
  <div class="nav-brand">
    <div class="icon">C</div>
    <h1>codemap-zero</h1>
  </div>
  <div class="nav-meta">
    <span class="dot"></span>
    <span>{{ project_name }}</span>
    <span class="dot"></span>
    <span>{{ project_type }}</span>
    <span class="dot"></span>
    <span>{{ total_files }} files</span>
  </div>
  <div class="nav-tabs">
    <div class="nav-tab active" data-page="overview">Overview</div>
    <div class="nav-tab" data-page="modules">Modules</div>
    <div class="nav-tab" data-page="graph">Graph</div>
    <div class="nav-tab" data-page="analysis">Analysis</div>
    <div class="nav-tab" data-page="ai">AI Assistant</div>
  </div>
</nav>

<!-- ═══ OVERVIEW ═══ -->
<div id="overview" class="page active">
  <div class="grid g4" style="margin-bottom:24px">
    <div class="stat-card">
      <div class="glow" style="background:var(--accent)"></div>
      <div class="label">Source Files</div>
      <div class="value" style="color:var(--accent-light)">{{ total_files }}</div>
      <div class="sub">scanned and analyzed</div>
    </div>
    <div class="stat-card">
      <div class="glow" style="background:var(--cyan)"></div>
      <div class="label">Lines of Code</div>
      <div class="value" style="color:var(--cyan)" id="loc-stat">{{ total_lines }}</div>
      <div class="sub">across all source files</div>
    </div>
    <div class="stat-card">
      <div class="glow" style="background:var(--green)"></div>
      <div class="label">Dependency Graph</div>
      <div class="value" style="color:var(--green)">{{ node_count }}</div>
      <div class="sub">{{ edge_count }} edges connecting them</div>
    </div>
    <div class="stat-card">
      <div class="glow" style="background:var(--pink)"></div>
      <div class="label">Modules Detected</div>
      <div class="value" style="color:var(--pink)">{{ community_count }}</div>
      <div class="sub">logical communities</div>
    </div>
  </div>

  {% if project_desc %}
  <div class="card" style="margin-bottom:24px">
    <div class="card-body" style="font-size:14px;color:var(--dim);line-height:1.6">{{ project_desc }}</div>
  </div>
  {% endif %}

  {% if frameworks %}
  <div class="card" style="margin-bottom:24px">
    <div class="card-body" style="display:flex;gap:8px;flex-wrap:wrap">
      {% for fw in frameworks %}
      <span style="padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600;background:var(--accent-glow);color:var(--accent-light);border:1px solid rgba(99,102,241,.2)">{{ fw }}</span>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  <div class="grid g2" style="margin-bottom:24px">
    <!-- Most Connected -->
    <div class="card">
      <div class="card-header"><h3>Most Connected Nodes</h3><span class="badge">Top 10</span></div>
      <div class="card-body" id="gods-list"></div>
    </div>
    <!-- Entry Points -->
    <div class="card">
      <div class="card-header"><h3>Entry Points</h3></div>
      <div class="card-body" id="entry-list"></div>
    </div>
  </div>

  <div class="card" style="margin-bottom:24px">
    <div class="card-header"><h3>Module Distribution</h3></div>
    <div class="card-body" id="module-bars"></div>
  </div>

  <div class="card">
    <div class="card-header"><h3>Complexity Hotspots</h3><span class="badge">Files</span></div>
    <div class="card-body" id="complexity-bars"></div>
  </div>
</div>

<!-- ═══ MODULES ═══ -->
<div id="modules" class="page">
  <div id="mod-container"></div>
</div>

<!-- ═══ GRAPH ═══ -->
<div id="graph" class="page">
  <div class="graph-toolbar">
    <input type="text" id="graph-search" placeholder="Search nodes...">
    <select id="graph-filter">
      <option value="all">All types</option>
      <option value="file">Files</option>
      <option value="class">Classes</option>
      <option value="function">Functions</option>
      <option value="method">Methods</option>
    </select>
    <button class="graph-btn active" id="graph-physics">Physics</button>
    <button class="graph-btn" id="graph-fit">Fit All</button>
    <span class="spacer"></span>
    <span class="info">Click a node for details · Double-click to focus · Scroll to zoom</span>
  </div>
  <div id="graph-container">
    <div class="node-panel" id="node-panel">
      <button class="close" id="panel-close">✕</button>
      <h4 id="panel-title">-</h4>
      <div id="panel-content"></div>
    </div>
  </div>
</div>

<!-- ═══ ANALYSIS ═══ -->
<div id="analysis" class="page">
  <div class="grid g2" style="margin-bottom:24px">
    <div class="card">
      <div class="card-header"><h3>Cross-Module Dependencies</h3></div>
      <div class="card-body" id="deps-list"></div>
    </div>
    <div class="card">
      <div class="card-header"><h3>Complexity Table</h3></div>
      <div class="card-body" style="padding:0">
        <table>
          <thead><tr><th>File</th><th>Symbols</th><th>Connections</th><th>Lines</th><th>Score</th></tr></thead>
          <tbody id="complex-tbody"></tbody>
        </table>
      </div>
    </div>
  </div>
</div>

<!-- ═══ AI ASSISTANT ═══ -->
<div id="ai" class="page">
  <div class="ai-page-wrap">
    <!-- Sidebar -->
    <div class="ai-sidebar">
      <div class="ai-sidebar-header">
        <div class="sidebar-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2a4 4 0 0 1 4 4v1a3 3 0 0 1 3 3v1a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-1a3 3 0 0 1 3-3V6a4 4 0 0 1 4-4z"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
        </div>
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
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
            Key is sent only to your chosen provider. Never stored.
          </div>
        </div>
        <button class="ai-connect-btn" id="ai-connect">
          <span id="ai-connect-text">Connect</span>
        </button>
        <div id="ai-status" class="ai-status"></div>

        <div class="ai-divider"></div>

        <div class="ai-suggestions-section">
          <h4>Try Asking</h4>
          <div class="ai-suggestion" data-q="What does this project do?">What does this project do?</div>
          <div class="ai-suggestion" data-q="What are the main features?">What are the main features?</div>
          <div class="ai-suggestion" data-q="Explain the project workflow">Explain the project workflow</div>
          <div class="ai-suggestion" data-q="How can I make this project better?">How can I make this project better?</div>
          <div class="ai-suggestion" data-q="What are the most complex parts?">What are the most complex parts?</div>
          <div class="ai-suggestion" data-q="Find potential bugs or issues">Find potential bugs or issues</div>
          <div class="ai-suggestion" data-q="Suggest refactoring opportunities">Suggest refactoring opportunities</div>
          <div class="ai-suggestion" data-q="Explain the architecture">Explain the architecture</div>
        </div>
      </div>
      <div class="ai-sidebar-footer">Powered by your API key · Context-aware</div>
    </div>

    <!-- Chat Panel -->
    <div class="ai-chat-panel">
      <div class="ai-chat-header">
        <h3>
          Chat
          <span class="model-badge" id="ai-model-badge" style="display:none">-</span>
        </h3>
        <div class="ai-chat-actions">
          <button class="ai-action-btn" id="ai-export" title="Export chat">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            Export
          </button>
          <button class="ai-action-btn" id="ai-clear" title="Clear chat">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            Clear
          </button>
        </div>
      </div>
      <div id="ai-messages" class="ai-messages">
        <div class="ai-welcome">
          <div class="ai-welcome-icon">&#129302;</div>
          <h4>AI Project Assistant</h4>
          <p>Configure your AI provider, then ask anything about your project.
            I have full context of your codebase — modules, dependencies, complexity, and architecture.</p>
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
        <button id="ai-send" class="ai-send-btn" disabled title="Send message (Enter)">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13"/><path d="M22 2L15 22L11 13L2 9L22 2Z"/></svg>
        </button>
      </div>
    </div>
  </div>
</div>

<div class="page-footer">codemap-zero v0.1.3 · Developed by <strong style="color:var(--accent-light)">Jerry4539</strong> · zero LLM tokens used</div>

<script>
(function(){
'use strict';

/* ── Tab Navigation ──────────────────────────────────────── */
document.querySelectorAll('.nav-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById(tab.dataset.page).classList.add('active');
    if (tab.dataset.page === 'graph' && !window._graphLoaded) loadGraph();
  });
});

/* ── Format numbers ──────────────────────────────────────── */
document.getElementById('loc-stat').textContent = Number({{ total_lines }}).toLocaleString();

/* ── API helpers ─────────────────────────────────────────── */
const api = url => fetch(url).then(r => r.json());

/* ── Gods list ───────────────────────────────────────────── */
api('/api/gods').then(gods => {
  const el = document.getElementById('gods-list');
  el.innerHTML = gods.slice(0,10).map((g,i) => `
    <div class="list-item">
      <div class="list-rank">${i+1}</div>
      <div class="list-info">
        <div class="name">${g.label || g.id}</div>
        <div class="meta">${g.source_file || ''}</div>
      </div>
      <span class="list-badge ${g.type}">${g.type}</span>
      <span class="list-val">${g.degree}</span>
    </div>`).join('');
});

/* ── Entry points ────────────────────────────────────────── */
api('/api/entry_points').then(eps => {
  const el = document.getElementById('entry-list');
  if (eps.length === 0) { el.innerHTML = '<div style="color:var(--muted);font-size:13px">No entry points detected</div>'; return; }
  el.innerHTML = eps.slice(0,8).map(ep => `
    <div class="entry-item">
      <div class="entry-icon"></div>
      <span class="entry-name">${ep.label || ep.id || ''}</span>
    </div>`).join('');
});

/* ── Module distribution bars ────────────────────────────── */
api('/api/communities').then(comms => {
  const maxSize = Math.max(...comms.map(c => c.size), 1);
  const barsEl = document.getElementById('module-bars');
  barsEl.innerHTML = comms.slice(0,12).map(c => {
    const pct = (c.size / maxSize * 100).toFixed(0);
    return `<div class="bar-row">
      <span class="bar-label">${c.label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:${c.color}">${c.size}</div></div>
      <span class="bar-val">${(c.cohesion*100).toFixed(0)}%</span>
    </div>`;
  }).join('');

  /* ── Module cards (modules page) ───────────────────────── */
  const modEl = document.getElementById('mod-container');
  modEl.innerHTML = comms.map(c => {
    const cohPct = (c.cohesion * 100).toFixed(0);
    const files = c.files.map(f => `<span class="mod-file">${f.label}</span>`).join('');
    const syms = c.symbols.slice(0,12).map(s =>
      `<div class="mod-sym"><span class="sym-type">${s.type}</span> ${s.signature || s.label}</div>`
    ).join('');
    return `<div class="mod-card" style="margin-bottom:12px">
      <div class="mod-header" onclick="this.parentElement.classList.toggle('open')">
        <span class="mod-dot" style="background:${c.color}"></span>
        <span class="mod-title">${c.label}</span>
        <div class="mod-stats">
          <span>${c.size} nodes</span>
          <span>cohesion ${cohPct}%</span>
        </div>
        <span class="mod-chevron">▶</span>
      </div>
      <div class="mod-body"><div class="mod-inner">
        <div class="cohesion-bar"><div class="cohesion-fill" style="width:${cohPct}%;background:${c.color}"></div></div>
        <div style="font-size:11px;color:var(--muted);margin-bottom:8px;text-transform:uppercase;letter-spacing:1px">Files</div>
        <div class="mod-files">${files}</div>
        ${syms ? `<div style="font-size:11px;color:var(--muted);margin-bottom:6px;margin-top:12px;text-transform:uppercase;letter-spacing:1px">Symbols</div><div class="mod-symbols">${syms}</div>` : ''}
      </div></div>
    </div>`;
  }).join('');
});

/* ── Complexity bars ─────────────────────────────────────── */
api('/api/complexity').then(data => {
  const maxConn = Math.max(...data.map(c => c.connections), 1);
  document.getElementById('complexity-bars').innerHTML = data.slice(0,10).map(c => {
    const pct = (c.connections / maxConn * 100).toFixed(0);
    return `<div class="bar-row">
      <span class="bar-label">${c.label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%;background:linear-gradient(90deg,var(--orange),var(--red))">${c.symbols} sym</div></div>
      <span class="bar-val">${c.lines}L</span>
    </div>`;
  }).join('');

  /* Analysis table */
  document.getElementById('complex-tbody').innerHTML = data.slice(0,15).map(c =>
    `<tr><td><code>${c.label}</code></td><td>${c.symbols}</td><td>${c.connections}</td><td>${Number(c.lines).toLocaleString()}</td><td style="font-weight:700;color:var(--orange)">${c.complexity_score.toFixed(1)}</td></tr>`
  ).join('');
});

/* ── Surprises / cross-module deps ───────────────────────── */
api('/api/surprises').then(data => {
  const el = document.getElementById('deps-list');
  if (data.length === 0) { el.innerHTML = '<div style="color:var(--muted);font-size:13px">No cross-module dependencies found</div>'; return; }
  el.innerHTML = data.slice(0,15).map(s => `
    <div class="dep-item">
      <span class="dep-source">${s.source}</span>
      <span class="dep-arrow">→</span>
      <span class="dep-target">${s.target}</span>
      <span class="dep-rel">${s.relation}</span>
    </div>`).join('');
});

/* ══════════════════════════════════════════════════════════ */
/* ── GRAPH PAGE ──────────────────────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

const EDGE_COLORS = {imports:'#f87171',calls:'#22d3ee',contains:'#4b5563',method:'#34d399'};
let graphNetwork = null;
let graphNodes = null;
let graphEdges = null;
let physicsEnabled = true;

function loadGraph() {
  window._graphLoaded = true;
  if (typeof vis === 'undefined') {
    document.getElementById('graph-container').innerHTML = '<div style="padding:60px;text-align:center;color:var(--red)"><h3>vis.js failed to load</h3><p>Check internet connection</p></div>';
    return;
  }
  api('/api/graph').then(data => {
    const rawNodes = data.nodes;
    const rawEdges = data.edges;
    const nodeMap = {};
    rawNodes.forEach(n => { nodeMap[n.id] = n; });

    const vNodes = rawNodes.map(n => {
      const sz = Math.max(10, Math.min(45, 10 + n.degree * 3));
      const shapeMap = {file:'dot',class:'diamond',function:'triangle',method:'triangleDown',document:'square'};
      return {
        id: n.id, label: n.label.length > 28 ? n.label.slice(0,25)+'...' : n.label,
        size: sz,
        shape: shapeMap[n.type] || 'dot',
        color: {background:n.color, border:n.color, highlight:{background:'#fff',border:n.color}, hover:{background:n.color+'dd',border:'#fff'}},
        font: {color:'#e5e7eb', size:Math.max(9,Math.min(14,9+n.degree)), strokeWidth:3, strokeColor:'#000'},
        borderWidth:2, borderWidthSelected:3,
        shadow:{enabled:true,color:'rgba(0,0,0,.25)',size:6,x:0,y:2},
        _raw: n,
      };
    });

    const vEdges = rawEdges.map((e,i) => {
      const c = EDGE_COLORS[e.relation] || '#4b5563';
      return {
        id:'e'+i, from:e.source, to:e.target,
        color:{color:c,opacity:0.4,highlight:c,hover:c},
        width: (e.relation==='imports'||e.relation==='calls') ? 1.5 : 0.8,
        arrows: (e.relation==='imports'||e.relation==='calls') ? {to:{enabled:true,scaleFactor:0.5}} : {},
        smooth:{type:'continuous'},
        _rel:e.relation,
      };
    });

    graphNodes = new vis.DataSet(vNodes);
    graphEdges = new vis.DataSet(vEdges);

    graphNetwork = new vis.Network(document.getElementById('graph-container'), {nodes:graphNodes, edges:graphEdges}, {
      physics:{solver:'forceAtlas2Based',forceAtlas2Based:{gravitationalConstant:-40,centralGravity:0.005,springLength:140,springConstant:0.06,avoidOverlap:0.4},
        stabilization:{enabled:true,iterations:300},maxVelocity:30,minVelocity:0.3},
      interaction:{hover:true,tooltipDelay:200,zoomView:true,dragView:true,keyboard:{enabled:true}},
      layout:{improvedLayout:true},
    });

    /* Click → detail panel */
    graphNetwork.on('click', function(ev) {
      if (ev.nodes.length > 0) {
        const nid = ev.nodes[0];
        const raw = nodeMap[nid];
        if (!raw) return;
        showNodePanel(raw, rawEdges, nodeMap);
        highlightNeighbors(nid, vNodes, vEdges);
      } else {
        hideNodePanel();
        resetHL(vNodes, vEdges);
      }
    });
    graphNetwork.on('doubleClick', function(ev) {
      if (ev.nodes.length > 0) graphNetwork.focus(ev.nodes[0], {scale:1.5, animation:{duration:400,easingFunction:'easeInOutQuad'}});
    });

    /* Search */
    document.getElementById('graph-search').addEventListener('input', function() {
      const q = this.value.toLowerCase();
      const filter = document.getElementById('graph-filter').value;
      const hidden = new Set();
      vNodes.forEach(n => {
        let show = true;
        if (filter !== 'all' && n._raw.type !== filter) show = false;
        if (q) {
          const hay = (n._raw.label+' '+n._raw.communityLabel+' '+n._raw.sourceFile+' '+n._raw.signature).toLowerCase();
          if (!hay.includes(q)) show = false;
        }
        if (!show) hidden.add(n.id);
        graphNodes.update({id:n.id, hidden:!show, borderWidth: (q && show) ? 4 : 2});
      });
      vEdges.forEach(e => { graphEdges.update({id:e.id, hidden: hidden.has(e.from)||hidden.has(e.to)}); });
    });
    document.getElementById('graph-filter').addEventListener('change', () => {
      document.getElementById('graph-search').dispatchEvent(new Event('input'));
    });
  });
}

function highlightNeighbors(nid, vNodes, vEdges) {
  const conn = graphNetwork.getConnectedNodes(nid);
  const s = new Set(conn); s.add(nid);
  graphNodes.update(vNodes.map(n => ({id:n.id, opacity: s.has(n.id)?1:0.1})));
  graphEdges.update(vEdges.map(e => ({id:e.id, color:{...e.color, opacity:(e.from===nid||e.to===nid)?0.9:0.04}, width:(e.from===nid||e.to===nid)?2.5:e.width})));
}
function resetHL(vNodes, vEdges) {
  graphNodes.update(vNodes.map(n => ({id:n.id, opacity:1})));
  graphEdges.update(vEdges.map(e => ({id:e.id, color:{...e.color, opacity:0.4}, width:(e._rel==='imports'||e._rel==='calls')?1.5:0.8})));
}

function showNodePanel(raw, allEdges, nodeMap) {
  const panel = document.getElementById('node-panel');
  document.getElementById('panel-title').textContent = raw.label;
  let h = '';
  h += `<div class="np-row"><div class="np-label">Type</div><div class="np-val"><span class="list-badge ${raw.type}">${raw.type}</span></div></div>`;
  h += `<div class="np-row"><div class="np-label">Module</div><div class="np-val">${raw.communityLabel}</div></div>`;
  if (raw.sourceFile) h += `<div class="np-row"><div class="np-label">File</div><div class="np-val"><code>${raw.sourceFile}</code></div></div>`;
  if (raw.signature) h += `<div class="np-row"><div class="np-label">Signature</div><div class="np-val"><span class="sig">${raw.signature}</span></div></div>`;
  if (raw.docstring) h += `<div class="np-row"><div class="np-label">Docs</div><div class="np-val" style="font-style:italic;color:var(--dim);font-size:12px">${raw.docstring}</div></div>`;
  h += `<div class="np-row"><div class="np-label">Connections</div><div class="np-val">${raw.inDeg} in · ${raw.outDeg} out · ${raw.degree} total</div></div>`;

  const inc = allEdges.filter(e => e.target === raw.id).slice(0,8);
  const out = allEdges.filter(e => e.source === raw.id).slice(0,8);
  if (inc.length) {
    h += '<div class="np-row"><div class="np-label">Incoming</div><div class="np-val">';
    inc.forEach(e => { h += `<div style="font-size:11px;color:var(--dim);padding:2px 0">← ${nodeMap[e.source]?.label||e.source} <span style="color:var(--muted);font-size:10px">${e.relation}</span></div>`; });
    h += '</div></div>';
  }
  if (out.length) {
    h += '<div class="np-row"><div class="np-label">Outgoing</div><div class="np-val">';
    out.forEach(e => { h += `<div style="font-size:11px;color:var(--dim);padding:2px 0">→ ${nodeMap[e.target]?.label||e.target} <span style="color:var(--muted);font-size:10px">${e.relation}</span></div>`; });
    h += '</div></div>';
  }
  document.getElementById('panel-content').innerHTML = h;
  panel.classList.add('show');
}
function hideNodePanel() { document.getElementById('node-panel').classList.remove('show'); }
document.getElementById('panel-close').addEventListener('click', hideNodePanel);

/* Graph toolbar */
document.getElementById('graph-physics').addEventListener('click', function() {
  physicsEnabled = !physicsEnabled;
  if (graphNetwork) graphNetwork.setOptions({physics:{enabled:physicsEnabled}});
  this.classList.toggle('active', physicsEnabled);
});
document.getElementById('graph-fit').addEventListener('click', () => {
  if (graphNetwork) graphNetwork.fit({animation:{duration:400,easingFunction:'easeInOutQuad'}});
});

/* ══════════════════════════════════════════════════════════ */
/* ── AI ASSISTANT PAGE ───────────────────────────────────── */
/* ══════════════════════════════════════════════════════════ */

let aiConnected = false;
let aiProvider = 'vedaslab';
let aiModel = '';
let aiKey = '';
let aiSending = false;
let aiMsgCount = 0;

/* Load providers */
api('/api/providers').then(providers => {
  const provSel = document.getElementById('ai-provider');
  const modSel  = document.getElementById('ai-model');
  provSel.innerHTML = providers.map(p => `<option value="${p.key}">${p.name}</option>`).join('');

  function updateModels() {
    const prov = providers.find(p => p.key === provSel.value);
    if (!prov) return;
    modSel.innerHTML = prov.models.map(m => `<option value="${m}" ${m===prov.default_model?'selected':''}>${m}</option>`).join('');
  }
  provSel.addEventListener('change', updateModels);
  updateModels();
});

/* Auto-resize textarea */
const aiMsgEl = document.getElementById('ai-msg');
aiMsgEl.addEventListener('input', function() {
  this.style.height = 'auto';
  this.style.height = Math.min(this.scrollHeight, 120) + 'px';
  /* Char count */
  const cnt = document.getElementById('ai-char-count');
  cnt.textContent = this.value.length > 0 ? this.value.length : '';
});

/* Connect button */
document.getElementById('ai-connect').addEventListener('click', function() {
  const key = document.getElementById('ai-key').value.trim();
  const statusEl = document.getElementById('ai-status');
  if (!key) {
    statusEl.innerHTML = '<span class="status-dot"></span> Please enter an API key';
    statusEl.className = 'ai-status err';
    return;
  }
  aiProvider = document.getElementById('ai-provider').value;
  aiModel = document.getElementById('ai-model').value;
  aiKey = key;
  aiConnected = true;

  statusEl.innerHTML = '<span class="status-dot"></span> Connected — ready to chat';
  statusEl.className = 'ai-status ok';

  /* Show model badge */
  const badge = document.getElementById('ai-model-badge');
  badge.textContent = aiModel;
  badge.style.display = 'inline-block';

  /* Update connect button */
  document.getElementById('ai-connect-text').textContent = 'Reconnect';

  document.getElementById('ai-msg').disabled = false;
  document.getElementById('ai-send').disabled = false;
  document.getElementById('ai-msg').focus();

  /* Remove welcome screen */
  const welcome = document.querySelector('.ai-welcome');
  if (welcome) welcome.style.display = 'none';
});

/* Send message */
function sendAIMessage(text) {
  if (!text || !aiConnected || aiSending) return;
  aiSending = true;
  aiMsgCount++;

  const msgs = document.getElementById('ai-messages');
  const time = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});

  /* Hide welcome */
  const welcome = document.querySelector('.ai-welcome');
  if (welcome) welcome.style.display = 'none';

  /* User bubble */
  const userDiv = document.createElement('div');
  userDiv.className = 'ai-msg user';
  userDiv.innerHTML = `
    <div class="ai-msg-row">
      <div class="ai-avatar">You</div>
      <div>
        <div class="ai-msg-bubble">${escapeHtml(text)}</div>
        <div class="ai-msg-footer">
          <span class="ai-msg-time">${time}</span>
        </div>
      </div>
    </div>`;
  msgs.appendChild(userDiv);

  /* Typing indicator */
  const typingDiv = document.createElement('div');
  typingDiv.className = 'ai-msg bot';
  typingDiv.id = 'ai-typing-indicator';
  typingDiv.innerHTML = `
    <div class="ai-msg-row">
      <div class="ai-avatar">AI</div>
      <div class="ai-msg-bubble"><div class="ai-typing"><span></span><span></span><span></span></div></div>
    </div>`;
  msgs.appendChild(typingDiv);
  msgs.scrollTop = msgs.scrollHeight;

  document.getElementById('ai-msg').value = '';
  document.getElementById('ai-msg').style.height = 'auto';
  document.getElementById('ai-char-count').textContent = '';
  document.getElementById('ai-send').disabled = true;

  /* Update model in case user changed it */
  aiModel = document.getElementById('ai-model').value;
  const badge = document.getElementById('ai-model-badge');
  badge.textContent = aiModel;
  badge.style.display = 'inline-block';

  const startTime = Date.now();

  fetch('/api/chat', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({provider:aiProvider, model:aiModel, api_key:aiKey, message:text}),
  })
  .then(r => r.json())
  .then(data => {
    const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
    msgs.removeChild(typingDiv);
    const botDiv = document.createElement('div');
    botDiv.className = 'ai-msg bot';
    const replyHtml = data.error
      ? `<span style="color:var(--red)">${escapeHtml(data.error)}</span>`
      : formatMarkdown(data.reply);
    const msgId = 'msg-' + aiMsgCount;
    botDiv.innerHTML = `
      <div class="ai-msg-row">
        <div class="ai-avatar">AI</div>
        <div style="flex:1;min-width:0">
          <div class="ai-msg-bubble" id="${msgId}">${replyHtml}</div>
          <div class="ai-msg-footer">
            <span class="ai-msg-time">${new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})} · ${elapsed}s</span>
            <div class="ai-msg-actions">
              <button class="ai-msg-action" title="Copy" onclick="copyMsg('${msgId}')">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
              </button>
            </div>
          </div>
        </div>
      </div>`;
    msgs.appendChild(botDiv);
    msgs.scrollTop = msgs.scrollHeight;

    /* Add copy buttons to code blocks */
    botDiv.querySelectorAll('pre').forEach(pre => {
      const btn = document.createElement('button');
      btn.className = 'copy-code';
      btn.textContent = 'Copy';
      btn.onclick = () => {
        const code = pre.querySelector('code') ? pre.querySelector('code').textContent : pre.textContent;
        navigator.clipboard.writeText(code).then(() => { btn.textContent = 'Copied!'; setTimeout(() => btn.textContent = 'Copy', 1500); });
      };
      pre.style.position = 'relative';
      pre.appendChild(btn);
    });
  })
  .catch(err => {
    if (document.getElementById('ai-typing-indicator')) msgs.removeChild(typingDiv);
    const errDiv = document.createElement('div');
    errDiv.className = 'ai-msg bot';
    errDiv.innerHTML = `
      <div class="ai-msg-row">
        <div class="ai-avatar">AI</div>
        <div class="ai-msg-bubble"><span style="color:var(--red)">Network error: ${escapeHtml(err.message)}</span></div>
      </div>`;
    msgs.appendChild(errDiv);
    msgs.scrollTop = msgs.scrollHeight;
  })
  .finally(() => {
    aiSending = false;
    document.getElementById('ai-send').disabled = false;
    document.getElementById('ai-msg').focus();
  });
}

/* Copy message text */
window.copyMsg = function(id) {
  const el = document.getElementById(id);
  if (!el) return;
  navigator.clipboard.writeText(el.textContent).then(() => {
    /* Brief visual feedback */
    const btn = el.closest('.ai-msg').querySelector('.ai-msg-action');
    if (btn) { btn.style.color = 'var(--green)'; setTimeout(() => btn.style.color = '', 1500); }
  });
};

document.getElementById('ai-send').addEventListener('click', () => {
  sendAIMessage(document.getElementById('ai-msg').value.trim());
});
document.getElementById('ai-msg').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendAIMessage(e.target.value.trim()); }
});

/* Suggestion chips (sidebar + welcome) */
document.querySelectorAll('.ai-suggestion, .ai-welcome-chip').forEach(el => {
  el.addEventListener('click', () => {
    if (!aiConnected) {
      const s = document.getElementById('ai-status');
      s.innerHTML = '<span class="status-dot"></span> Connect to a provider first';
      s.className = 'ai-status err';
      return;
    }
    sendAIMessage(el.dataset.q);
  });
});

/* Clear chat */
document.getElementById('ai-clear').addEventListener('click', () => {
  const msgs = document.getElementById('ai-messages');
  msgs.innerHTML = '';
  /* Restore welcome */
  msgs.innerHTML = `
    <div class="ai-welcome">
      <div class="ai-welcome-icon">&#129302;</div>
      <h4>AI Project Assistant</h4>
      <p>Ask anything about your project.</p>
      <div class="ai-welcome-chips">
        <div class="ai-welcome-chip" data-q="What does this project do?">What does this project do?</div>
        <div class="ai-welcome-chip" data-q="What are the main features?">Main features</div>
        <div class="ai-welcome-chip" data-q="How is the code organized?">Code organization</div>
        <div class="ai-welcome-chip" data-q="What are the most complex parts?">Complex parts</div>
      </div>
    </div>`;
  /* Re-attach welcome chip listeners */
  msgs.querySelectorAll('.ai-welcome-chip').forEach(el => {
    el.addEventListener('click', () => {
      if (!aiConnected) { const s=document.getElementById('ai-status'); s.innerHTML='<span class="status-dot"></span> Connect first'; s.className='ai-status err'; return; }
      sendAIMessage(el.dataset.q);
    });
  });
  if (aiConnected) {
    const w = msgs.querySelector('.ai-welcome'); if (w) w.style.display = 'none';
  }
  fetch('/api/chat/reset', {method:'POST'});
  aiMsgCount = 0;
});

/* Export chat as text */
document.getElementById('ai-export').addEventListener('click', () => {
  const msgs = document.getElementById('ai-messages');
  const bubbles = msgs.querySelectorAll('.ai-msg');
  if (bubbles.length === 0) return;
  let txt = '# AI Chat Export\n# ' + new Date().toLocaleString() + '\n# Model: ' + aiModel + '\n\n';
  bubbles.forEach(msg => {
    const isUser = msg.classList.contains('user');
    const bubble = msg.querySelector('.ai-msg-bubble');
    if (bubble) {
      txt += (isUser ? '>> You:\n' : '>> AI:\n') + bubble.textContent.trim() + '\n\n';
    }
  });
  const blob = new Blob([txt], {type:'text/plain'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'chat-export-' + new Date().toISOString().slice(0,10) + '.txt';
  a.click();
  URL.revokeObjectURL(a.href);
});

/* Utils */
function escapeHtml(t) {
  const d = document.createElement('div');
  d.textContent = t;
  return d.innerHTML;
}
function formatMarkdown(text) {
  /* Robust markdown formatting */
  let h = escapeHtml(text);
  /* Code blocks with language hint */
  h = h.replace(/```(\w*)\n([\s\S]*?)```/g, function(m, lang, code) {
    return '<pre><code class="lang-'+lang+'">' + code + '</code></pre>';
  });
  /* Inline code */
  h = h.replace(/`([^`]+)`/g, '<code>$1</code>');
  /* Headings */
  h = h.replace(/^### (.+)$/gm, '<h3>$1</h3>');
  h = h.replace(/^## (.+)$/gm, '<h2>$1</h2>');
  h = h.replace(/^# (.+)$/gm, '<h1>$1</h1>');
  /* Bold/italic */
  h = h.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  h = h.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  /* Unordered lists */
  h = h.replace(/^[-•] (.+)$/gm, '<li>$1</li>');
  /* Numbered lists */
  h = h.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  /* Wrap consecutive <li> in <ul> */
  h = h.replace(/((?:<li>.*?<\/li>\s*)+)/g, '<ul>$1</ul>');
  /* Paragraphs */
  h = h.replace(/\n\n/g, '</p><p>');
  h = h.replace(/\n/g, '<br>');
  return '<p>' + h + '</p>';
}

})();
</script>
</body>
</html>"""
