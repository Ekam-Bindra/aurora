"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

import {
  getGraphImpact,
  getGraphNeighbors,
  type GraphNode,
} from "@/lib/api";

type ViewMode = "neighborhood" | "impact";

type GraphExplorerProps = {
  rootNode: GraphNode;
  mode: ViewMode;
  depth?: number;
  onNodeSelect?: (node: GraphNode) => void;
};

type ApiNode = GraphNode & Record<string, unknown>;
type ApiEdge = { id: string; source: string; target: string; type: string; properties?: Record<string, unknown> };

const LABEL_COLORS: Record<string, string> = {
  Vendor: "#F59E0B",
  Product: "#3B82F6",
  Customer: "#22D3EE",
  Department: "#8B5CF6",
  Project: "#22C55E",
  Employee: "#8A93A6",
  Company: "#E6EAF2",
  Contract: "#6366F1",
};

function nodeColor(node: ApiNode): string {
  if (node.label === "Vendor" && node.criticality === "critical") return "#EF4444";
  return LABEL_COLORS[node.label] ?? "#26304A";
}

function layoutNodes(
  rootId: string,
  nodes: ApiNode[],
  edges: ApiEdge[],
): Map<string, { x: number; y: number }> {
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const adj = new Map<string, Set<string>>();
  for (const e of edges) {
    if (!byId.has(e.source) || !byId.has(e.target)) continue;
    if (!adj.has(e.source)) adj.set(e.source, new Set());
    if (!adj.has(e.target)) adj.set(e.target, new Set());
    adj.get(e.source)!.add(e.target);
    adj.get(e.target)!.add(e.source);
  }

  const layers: string[][] = [];
  const visited = new Set<string>();
  let frontier = [rootId];
  visited.add(rootId);

  while (frontier.length > 0) {
    layers.push([...frontier]);
    const next: string[] = [];
    for (const id of frontier) {
      for (const nb of adj.get(id) ?? []) {
        if (!visited.has(nb)) {
          visited.add(nb);
          next.push(nb);
        }
      }
    }
    frontier = next;
  }

  for (const n of nodes) {
    if (!visited.has(n.id)) {
      layers.push([n.id]);
    }
  }

  const positions = new Map<string, { x: number; y: number }>();
  layers.forEach((layer, layerIdx) => {
    const span = Math.max(layer.length - 1, 0);
    layer.forEach((id, idx) => {
      positions.set(id, {
        x: layerIdx * 260,
        y: idx * 90 - (span * 90) / 2,
      });
    });
  });
  return positions;
}

function toFlowNodes(
  nodes: ApiNode[],
  edges: ApiEdge[],
  rootId: string,
  selectedId?: string,
): Node[] {
  const positions = layoutNodes(rootId, nodes, edges);
  return nodes.map((n) => ({
    id: n.id,
    position: positions.get(n.id) ?? { x: 0, y: 0 },
    data: {
      label: (
        <div className="text-center">
          <div className="text-[10px] uppercase tracking-wide opacity-70">{n.label}</div>
          <div className="max-w-[140px] truncate text-xs font-medium">{n.name}</div>
        </div>
      ),
    },
    style: {
      background: nodeColor(n),
      color: "#0B0E14",
      border: selectedId === n.id ? "2px solid #E6EAF2" : "1px solid #26304A",
      borderRadius: 8,
      padding: "8px 12px",
      fontSize: 12,
      width: 160,
    },
  }));
}

function toFlowEdges(edges: ApiEdge[]): Edge[] {
  return edges.map((e, i) => ({
    id: e.id || `${e.source}-${e.type}-${e.target}-${i}`,
    source: e.source,
    target: e.target,
    label: e.type.replace(/_/g, " "),
    labelStyle: { fill: "#8A93A6", fontSize: 10 },
    style: { stroke: "#26304A" },
    animated: e.type === "SUPPLIES" || e.type === "DEPENDS_ON",
  }));
}

function normalizeEdges(raw: Array<Record<string, unknown>>): ApiEdge[] {
  return raw.map((e, i) => ({
    id: String(e.id ?? `${e.source_id}-${e.type}-${e.target_id}-${i}`),
    source: String(e.source_id ?? e.source),
    target: String(e.target_id ?? e.target),
    type: String(e.type ?? "RELATED"),
    properties: (e.properties as Record<string, unknown>) ?? {},
  }));
}

export default function GraphExplorer({
  rootNode,
  mode,
  depth = 2,
  onNodeSelect,
}: GraphExplorerProps) {
  const [nodes, setNodes] = useState<ApiNode[]>([]);
  const [edges, setEdges] = useState<ApiEdge[]>([]);
  const [selectedId, setSelectedId] = useState<string>(rootNode.id);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (mode === "neighborhood") {
        const hood = await getGraphNeighbors(rootNode.id, depth);
        setNodes(hood.nodes as ApiNode[]);
        setEdges(normalizeEdges(hood.edges as Array<Record<string, unknown>>));
      } else {
        const [hood, impact] = await Promise.all([
          getGraphNeighbors(rootNode.id, depth),
          getGraphImpact(rootNode.id, depth),
        ]);
        const nodeMap = new Map<string, ApiNode>();
        for (const n of hood.nodes as ApiNode[]) nodeMap.set(n.id, n);

        const chainIds = new Set<string>([rootNode.id]);
        for (const p of impact.impact.affected_products) chainIds.add(p.id);
        for (const c of impact.impact.affected_customers.slice(0, 6)) chainIds.add(c.id);
        for (const d of impact.impact.affected_departments) chainIds.add(d.id);
        for (const e of impact.impact.affected_employees.slice(0, 5)) chainIds.add(e.id);

        const filteredNodes = [...nodeMap.values()].filter((n) => chainIds.has(n.id));
        const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
        const filteredEdges = normalizeEdges(hood.edges as Array<Record<string, unknown>>).filter(
          (e) => filteredNodeIds.has(e.source) && filteredNodeIds.has(e.target),
        );
        setNodes(filteredNodes);
        setEdges(filteredEdges);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load graph");
    } finally {
      setLoading(false);
    }
  }, [rootNode.id, mode, depth]);

  useEffect(() => {
    setSelectedId(rootNode.id);
    load();
  }, [rootNode.id, mode, depth, load]);

  const flowNodes = useMemo(
    () => toFlowNodes(nodes, edges, rootNode.id, selectedId),
    [nodes, edges, rootNode.id, selectedId],
  );
  const flowEdges = useMemo(() => toFlowEdges(edges), [edges]);

  const onNodeClick: NodeMouseHandler = useCallback(
    (_, node) => {
      setSelectedId(node.id);
      const hit = nodes.find((n) => n.id === node.id);
      if (hit && onNodeSelect) onNodeSelect(hit);
    },
    [nodes, onNodeSelect],
  );

  if (loading) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-border bg-base text-sm text-text-muted">
        Loading graph…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-warning/40 bg-warning/10 px-4 text-sm text-warning">
        {error}
      </div>
    );
  }

  if (nodes.length === 0) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-lg border border-border bg-base text-sm text-text-muted">
        No graph nodes found for this selection.
      </div>
    );
  }

  return (
    <div className="h-[420px] overflow-hidden rounded-lg border border-border bg-base">
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        onNodeClick={onNodeClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={1.5}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#26304A" gap={20} />
        <Controls className="!border-border !bg-surface !shadow-none [&>button]:!border-border [&>button]:!bg-elevated [&>button]:!fill-text-muted" />
        <MiniMap
          nodeColor={(n) => {
            const hit = nodes.find((x) => x.id === n.id);
            return hit ? nodeColor(hit) : "#26304A";
          }}
          maskColor="rgba(11, 14, 20, 0.8)"
          className="!border-border !bg-surface"
        />
      </ReactFlow>
    </div>
  );
}
