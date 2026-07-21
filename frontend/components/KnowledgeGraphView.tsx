"use client";
import { useRef, useEffect, useState, useCallback } from "react";
import { ExternalLink, Network, X } from "lucide-react";

/* ── Types ──────────────────────────────────────────────── */
type GraphNode = {
  id: string;
  label: string;
  type: string;
  year?: number;
  citation_count?: number;
  title?: string;
  name?: string;
  source?: string;
  abstract?: string;
  authors?: string[];
  url?: string;
  relevance_score?: number;
  topics?: string[];
};
type GraphLink = { source: string; target: string; type: string; weight?: number; reason?: string };
type GraphData = {
  nodes: GraphNode[];
  links: GraphLink[];
  stats: {
    total_nodes: number;
    total_edges: number;
    node_types: Record<string, number>;
    edge_types: Record<string, number>;
    top_connected: { id: string; label: string; degree: number }[];
  };
};

interface KnowledgeGraphViewProps {
  data: GraphData | null;
}

/* ── Constants ──────────────────────────────────────────── */
const NODE_COLORS: Record<string, string> = {
  paper: "#6366f1",
  author: "#10b981",
  topic: "#a855f7",
  cluster: "#22d3ee",
};
const NODE_SIZES: Record<string, number> = {
  paper: 8,
  author: 6,
  topic: 7,
  cluster: 10,
};
const CANVAS_HEIGHT = 400;

/* ── Simulation node (mutable internal state) ───────────── */
interface SimNode {
  id: string;
  label: string;
  type: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  r: number;
  color: string;
  data: GraphNode;
}
interface SimLink {
  source: SimNode;
  target: SimNode;
  type: string;
}

export default function KnowledgeGraphView({ data }: KnowledgeGraphViewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const animFrameRef = useRef<number>(0);
  const nodesRef = useRef<SimNode[]>([]);
  const linksRef = useRef<SimLink[]>([]);
  const panRef = useRef({ x: 0, y: 0 });
  const dragRef = useRef({ dragging: false, moved: false, lastX: 0, lastY: 0 });
  const hoverRef = useRef<SimNode | null>(null);
  const [tooltip, setTooltip] = useState<{ label: string; x: number; y: number } | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);

  const isEmpty = !data || data.nodes.length === 0;

  /* ── Initialise simulation data ─────────────────────────── */
  const initSim = useCallback((d: GraphData, w: number, h: number) => {
    const nodeMap = new Map<string, SimNode>();
    d.nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / d.nodes.length;
      const radius = Math.min(w, h) * 0.3;
      const sn: SimNode = {
        id: n.id,
        label: n.label,
        type: n.type,
        x: w / 2 + Math.cos(angle) * radius + (Math.random() - 0.5) * 40,
        y: h / 2 + Math.sin(angle) * radius + (Math.random() - 0.5) * 40,
        vx: 0,
        vy: 0,
        r: NODE_SIZES[n.type] ?? 6,
        color: NODE_COLORS[n.type] ?? "#6b7280",
        data: n,
      };
      nodeMap.set(n.id, sn);
    });
    const simLinks: SimLink[] = [];
    d.links.forEach((l) => {
      const s = nodeMap.get(l.source);
      const t = nodeMap.get(l.target);
      if (s && t) simLinks.push({ source: s, target: t, type: l.type });
    });
    nodesRef.current = Array.from(nodeMap.values());
    linksRef.current = simLinks;
    panRef.current = { x: 0, y: 0 };
  }, []);

  /* ── Force tick ─────────────────────────────────────────── */
  const tick = useCallback((w: number, h: number) => {
    const nodes = nodesRef.current;
    const links = linksRef.current;
    const alpha = 0.3;
    const repulsion = 800;
    const springLen = 80;
    const springK = 0.005;
    const damping = 0.85;
    const cx = w / 2;
    const cy = h / 2;

    // Charge repulsion (Barnes-Hut would be better for perf but simple O(n²) is fine for small graphs)
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        let dx = nodes[j].x - nodes[i].x;
        let dy = nodes[j].y - nodes[i].y;
        let dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (repulsion / (dist * dist)) * alpha;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        nodes[i].vx -= fx;
        nodes[i].vy -= fy;
        nodes[j].vx += fx;
        nodes[j].vy += fy;
      }
    }

    // Spring attraction along links
    for (const link of links) {
      let dx = link.target.x - link.source.x;
      let dy = link.target.y - link.source.y;
      let dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const displacement = dist - springLen;
      const force = displacement * springK * alpha;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      link.source.vx += fx;
      link.source.vy += fy;
      link.target.vx -= fx;
      link.target.vy -= fy;
    }

    // Centering force
    for (const n of nodes) {
      n.vx += (cx - n.x) * 0.0005;
      n.vy += (cy - n.y) * 0.0005;
    }

    // Integrate + damp
    for (const n of nodes) {
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
    }
  }, []);

  /* ── Draw ───────────────────────────────────────────────── */
  const draw = useCallback((ctx: CanvasRenderingContext2D, w: number, h: number) => {
    const { x: px, y: py } = panRef.current;
    ctx.clearRect(0, 0, w, h);
    ctx.save();
    ctx.translate(px, py);

    // Links
    for (const link of linksRef.current) {
      ctx.beginPath();
      ctx.lineWidth = link.type === "cites" ? 1.8 : link.type === "similar_to" ? 1.2 : 1;
      ctx.strokeStyle =
        link.type === "cites"
          ? "rgba(34, 211, 238, 0.45)"
          : link.type === "similar_to"
          ? "rgba(168, 85, 247, 0.28)"
          : link.type === "in_cluster"
          ? "rgba(34, 211, 238, 0.22)"
          : "rgba(99, 102, 241, 0.12)";
      ctx.moveTo(link.source.x, link.source.y);
      ctx.lineTo(link.target.x, link.target.y);
      ctx.stroke();
    }

    // Nodes
    const hover = hoverRef.current;
    for (const n of nodesRef.current) {
      ctx.beginPath();
      const isHover = hover?.id === n.id;
      ctx.arc(n.x, n.y, isHover ? n.r + 2 : n.r, 0, Math.PI * 2);
      ctx.fillStyle = n.color;
      ctx.globalAlpha = isHover ? 1 : 0.85;
      ctx.fill();
      if (isHover) {
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      if (selectedNode?.id === n.id) {
        ctx.strokeStyle = "#22d3ee";
        ctx.lineWidth = 2;
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    ctx.restore();
  }, [selectedNode]);

  /* ── Animation loop ─────────────────────────────────────── */
  const loop = useCallback(
    (ctx: CanvasRenderingContext2D, w: number, h: number) => {
      tick(w, h);
      draw(ctx, w, h);
      animFrameRef.current = requestAnimationFrame(() => loop(ctx, w, h));
    },
    [tick, draw]
  );

  /* ── Setup ──────────────────────────────────────────────── */
  useEffect(() => {
    if (isEmpty) return;
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    const dpr = window.devicePixelRatio || 1;
    const w = container.clientWidth;
    const h = CANVAS_HEIGHT;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    const ctx = canvas.getContext("2d")!;
    ctx.scale(dpr, dpr);

    initSim(data!, w, h);
    animFrameRef.current = requestAnimationFrame(() => loop(ctx, w, h));

    return () => cancelAnimationFrame(animFrameRef.current);
  }, [data, isEmpty, initSim, loop]);

  /* ── Mouse events ───────────────────────────────────────── */
  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left - panRef.current.x;
    const my = e.clientY - rect.top - panRef.current.y;

    // Drag
    if (dragRef.current.dragging) {
      const dx = e.clientX - dragRef.current.lastX;
      const dy = e.clientY - dragRef.current.lastY;
      if (Math.abs(dx) + Math.abs(dy) > 2) dragRef.current.moved = true;
      panRef.current.x += dx;
      panRef.current.y += dy;
      dragRef.current.lastX = e.clientX;
      dragRef.current.lastY = e.clientY;
      return;
    }

    // Hover detection
    let found: SimNode | null = null;
    for (const n of nodesRef.current) {
      const dx = n.x - mx;
      const dy = n.y - my;
      if (dx * dx + dy * dy < (n.r + 4) * (n.r + 4)) {
        found = n;
        break;
      }
    }
    hoverRef.current = found;
    if (found) {
      setTooltip({ label: found.label, x: e.clientX - rect.left + 12, y: e.clientY - rect.top - 8 });
    } else {
      setTooltip(null);
    }
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent<HTMLCanvasElement>) => {
    dragRef.current = { dragging: true, moved: false, lastX: e.clientX, lastY: e.clientY };
  }, []);

  const handleMouseUp = useCallback(() => {
    if (!dragRef.current.moved && hoverRef.current) {
      setSelectedNode(hoverRef.current.data);
    }
    dragRef.current.dragging = false;
  }, []);

  const handleMouseLeave = useCallback(() => {
    dragRef.current.dragging = false;
    hoverRef.current = null;
    setTooltip(null);
  }, []);

  const selectedLinks = selectedNode && data
    ? data.links.filter((l) => l.source === selectedNode.id || l.target === selectedNode.id)
    : [];

  /* ── Render ─────────────────────────────────────────────── */
  if (isEmpty) {
    return (
      <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Network size={14} className="text-indigo-400" />
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Knowledge Graph</span>
        </div>
        <div className="flex flex-col items-center justify-center py-14 text-center">
          <Network size={32} className="text-gray-700 mb-3" />
          <p className="text-sm text-gray-600">No knowledge graph data available.</p>
          <p className="text-xs text-gray-700 mt-1">Run a research query to generate the graph.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-5 py-4 border-b border-gray-800">
        <Network size={14} className="text-indigo-400" />
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Knowledge Graph</span>
        <span className="ml-auto text-[11px] text-gray-600">Click any node to inspect it</span>
      </div>

      {/* Canvas area */}
      <div ref={containerRef} className="relative w-full" style={{ height: CANVAS_HEIGHT }}>
        <canvas
          ref={canvasRef}
          className="w-full cursor-grab active:cursor-grabbing"
          style={{ height: CANVAS_HEIGHT }}
          onMouseMove={handleMouseMove}
          onMouseDown={handleMouseDown}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseLeave}
        />

        {/* Tooltip */}
        {tooltip && (
          <div
            className="absolute z-10 px-2.5 py-1.5 rounded-lg bg-gray-800 border border-gray-700 text-xs text-white shadow-xl pointer-events-none whitespace-nowrap"
            style={{ left: tooltip.x, top: tooltip.y }}
          >
            {tooltip.label}
          </div>
        )}

        {/* Stats overlay */}
        {data?.stats && (
          <div className="absolute top-3 left-3 bg-gray-950/80 backdrop-blur-sm border border-gray-800 rounded-xl px-3 py-2.5 space-y-1.5">
            <p className="text-xs font-semibold text-gray-400">
              {data.stats.total_nodes} nodes · {data.stats.total_edges} edges
            </p>
            <div className="flex flex-wrap gap-2">
              {Object.entries(data.stats.node_types).map(([type, count]) => (
                <span
                  key={type}
                  className="flex items-center gap-1.5 text-xs text-gray-500"
                >
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: NODE_COLORS[type] ?? "#6b7280" }}
                  />
                  {type}: {count}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="absolute bottom-3 right-3 flex items-center gap-3">
          {Object.entries(NODE_COLORS).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1.5 text-xs text-gray-500">
              <span className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
              {type}
            </span>
          ))}
        </div>
      </div>

      {data?.stats?.edge_types && (
        <div className="px-5 py-3 border-t border-gray-800 flex flex-wrap gap-2">
          {Object.entries(data.stats.edge_types).map(([type, count]) => (
            <span
              key={type}
              className="text-[10px] px-2 py-1 rounded-full bg-gray-950 border border-gray-800 text-gray-500"
            >
              {type.replace("_", " ")}: {count}
            </span>
          ))}
        </div>
      )}

      {selectedNode && (
        <div className="border-t border-gray-800 bg-gray-950/60 p-5">
          <div className="flex items-start gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="w-2.5 h-2.5 rounded-full"
                  style={{ backgroundColor: NODE_COLORS[selectedNode.type] ?? "#6b7280" }}
                />
                <span className="text-[10px] uppercase tracking-wider text-gray-500">
                  {selectedNode.type}
                </span>
              </div>
              <h3 className="text-sm font-semibold text-gray-100 leading-snug">
                {selectedNode.title || selectedNode.name || selectedNode.label}
              </h3>
              {selectedNode.authors && selectedNode.authors.length > 0 && (
                <p className="text-[11px] text-gray-500 mt-1">
                  {selectedNode.authors.join(", ")}
                  {selectedNode.year ? ` · ${selectedNode.year}` : ""}
                </p>
              )}
              {selectedNode.source && (
                <p className="text-[11px] text-indigo-400/70 mt-1">
                  {selectedNode.source.replace("_", " ")}
                  {selectedNode.citation_count ? ` · ${selectedNode.citation_count.toLocaleString()} citations` : ""}
                </p>
              )}
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="p-1.5 rounded-lg text-gray-600 hover:text-gray-300 hover:bg-gray-800 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {selectedNode.abstract && (
            <p className="text-xs text-gray-400 leading-relaxed mt-3 line-clamp-4">
              {selectedNode.abstract}
            </p>
          )}

          {selectedNode.topics && selectedNode.topics.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3">
              {selectedNode.topics.map((topic) => (
                <span
                  key={topic}
                  className="text-[10px] px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-300 border border-purple-500/20"
                >
                  {topic}
                </span>
              ))}
            </div>
          )}

          {selectedLinks.length > 0 && (
            <div className="mt-4">
              <p className="text-[10px] uppercase tracking-wider text-gray-600 mb-2">
                Connected edges
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {selectedLinks.slice(0, 8).map((link, i) => {
                  const otherId = link.source === selectedNode.id ? link.target : link.source;
                  const other = data.nodes.find((n) => n.id === otherId);
                  return (
                    <div key={`${link.source}-${link.target}-${i}`} className="rounded-lg bg-gray-900 border border-gray-800 p-2">
                      <p className="text-[11px] text-gray-400 truncate">
                        {link.type.replace("_", " ")} · {other?.label || otherId}
                      </p>
                      {link.reason && (
                        <p className="text-[10px] text-gray-600 mt-0.5 truncate">{link.reason}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {selectedNode.url && (
            <a
              href={selectedNode.url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 mt-4 text-xs text-indigo-400 hover:text-indigo-300"
            >
              <ExternalLink className="w-3.5 h-3.5" />
              Open source
            </a>
          )}
        </div>
      )}
    </div>
  );
}
