import { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import CytoscapeComponent from "react-cytoscapejs";

/**
 * Renders a {nodes, edges} graph (single-case: /graph/case/{id}, or the
 * client-built aggregate offender graph) as Cytoscape. Node/edge shape
 * for the single-case graph is unchanged from what the backend already
 * produced before any frontend existed to consume it -- victim/accused
 * nodes carry age/gender so onNodeClick can show a detail panel without
 * a second fetch, and (added later) the single-case payload's top-level
 * `case_context` (crime type/district/date/brief/MO if already
 * extracted) rides along on the same request so the hover tooltip below
 * needs zero extra fetches of its own.
 */

const NODE_COLORS = {
  case: "#D4A24C",
  victim: "#5B8DB8",
  accused: "#B0503C",
  arrest_event: "#3A6B4C",
};

const LEGEND_ITEMS = [
  { type: "case", label: "Case" },
  { type: "victim", label: "Victim" },
  { type: "accused", label: "Accused" },
  { type: "arrest_event", label: "Arrest Event" },
];

function toElements(graph) {
  const nodes = graph.nodes.map((n) => ({
    data: {
      id: n.id, label: n.label, type: n.type, age: n.age, gender: n.gender,
      crossCase: n.cross_case, caseCount: n.case_count,
    },
    classes: [n.cross_case && "cross-case", n.similar_mo && "similar-mo"]
      .filter(Boolean)
      .join(" ") || undefined,
  }));
  const edges = graph.edges.map((e, i) => ({
    data: {
      id: `e${i}_${e.source}_${e.target}`,
      source: e.source,
      target: e.target,
      label: e.weight > 1 ? `${e.weight} cases` : (e.label ?? ""),
      weight: e.weight ?? 1,
      edgeType: e.type ?? "default",
    },
    classes: e.type === "similar-mo" ? "similar-mo" : undefined,
  }));
  return [...nodes, ...edges];
}

const stylesheet = [
  {
    selector: "node",
    style: {
      "background-color": (el) => NODE_COLORS[el.data("type")] ?? "#4A5268",
      label: "data(label)",
      color: "#E4E7EC",
      "font-size": 9,
      "font-family": "monospace",
      "text-valign": "bottom",
      "text-margin-y": 4,
      width: 26,
      height: 26,
      "border-width": 2,
      "border-color": "#0B1120",
    },
  },
  {
    // Same amber accent used everywhere else in this app for a
    // "repeat offender" signal (the risk-tier badges) -- dashed, not
    // solid, so it reads as a distinct persistent marker rather than
    // being confused with the solid-amber hover-highlight below.
    selector: "node.cross-case",
    style: { "border-color": "#D4A24C", "border-width": 3, "border-style": "dashed" },
  },
  {
    // A case pulled in by "Find Similar-MO Cases" -- visually distinct
    // from the case being viewed, since it's a suggested lead, not a
    // confirmed part of this case's own record.
    selector: "node.similar-mo",
    style: { "border-color": "#8B6FD6", "border-width": 3, "border-style": "dotted" },
  },
  {
    selector: "node.dimmed",
    style: { opacity: 0.25 },
  },
  {
    selector: "node.highlighted, node.path-highlight",
    style: { "border-color": "#D4A24C", "border-width": 3 },
  },
  {
    selector: "edge",
    style: {
      width: (el) =>
        el.data("edgeType") === "co-accused"
          ? 1.5 + Math.min(el.data("weight") ?? 1, 5) * 1.3
          : 1.5,
      "line-color": "#2A3348",
      "target-arrow-color": "#2A3348",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      label: "data(label)",
      "font-size": 7,
      "font-family": "monospace",
      color: "#6B7488",
      "text-rotation": "autorotate",
    },
  },
  {
    selector: "edge.similar-mo",
    style: {
      "line-color": "#8B6FD6", "target-arrow-color": "#8B6FD6",
      "line-style": "dashed", "target-arrow-shape": "none",
    },
  },
  {
    selector: "edge.dimmed",
    style: { opacity: 0.15 },
  },
  {
    selector: "edge.path-highlight",
    style: { "line-color": "#D4A24C", "target-arrow-color": "#D4A24C", width: 3 },
  },
];

function Tooltip({ tooltip }) {
  if (!tooltip) return null;
  const { x, y, node, caseContext } = tooltip;
  return (
    <div
      className="absolute z-20 bg-surface-panel border border-line rounded px-3 py-2 shadow-lg
                 max-w-[260px] pointer-events-none"
      style={{ left: x + 14, top: y + 14 }}
    >
      <p className="text-xs text-ink-primary font-mono">{node.label}</p>
      <p className="text-[10px] text-ink-faint mt-0.5">
        {node.age != null && `Age ${node.age}`}
        {node.age != null && node.gender != null && " · "}
        {node.gender}
        {node.crossCase && " · repeat offender"}
      </p>
      {caseContext ? (
        <div className="mt-1.5 pt-1.5 border-t border-line">
          <p className="text-[10px] text-ink-dim font-mono uppercase tracking-wide">
            {caseContext.crime_type} &middot; {caseContext.district} &middot; {caseContext.date}
          </p>
          {caseContext.mo_summary ? (
            <p className="text-[11px] text-ink-secondary leading-snug mt-1">
              {caseContext.mo_summary}
            </p>
          ) : (
            caseContext.brief && (
              <p className="text-[11px] text-ink-faint leading-snug mt-1">{caseContext.brief}</p>
            )
          )}
        </div>
      ) : null}
      {node.type === "accused" && (
        <p className="text-[10px] text-accent font-mono uppercase tracking-wide mt-1.5">
          Click for full profile &rarr;
        </p>
      )}
    </div>
  );
}

export default function CaseGraph({ graph, onNodeClick, onCyReady }) {
  const navigate = useNavigate();
  const cyRef = useRef(null);
  const [tooltip, setTooltip] = useState(null);

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-ink-faint text-sm font-mono">
        No graph data
      </div>
    );
  }

  const caseContext = graph.case_context;

  return (
    <div className="relative h-full w-full">
      <CytoscapeComponent
        elements={toElements(graph)}
        stylesheet={stylesheet}
        layout={{ name: "cose", animate: false, padding: 40 }}
        minZoom={0.3}
        style={{ width: "100%", height: "100%" }}
        cy={(cy) => {
          cyRef.current = cy;
          cy.removeAllListeners();
          if (onCyReady) onCyReady(cy);

          cy.on("layoutstop", () => cy.fit(undefined, 40));

          cy.on("mouseover", "node", (evt) => {
            const node = evt.target;
            const neighborhood = node.closedNeighborhood();
            cy.elements().not(neighborhood).addClass("dimmed");
            neighborhood.addClass("highlighted");

            const data = node.data();
            if (data.type === "victim" || data.type === "accused") {
              const pos = evt.renderedPosition || node.renderedPosition();
              setTooltip({ x: pos.x, y: pos.y, node: data, caseContext });
            }
          });
          cy.on("mousemove", "node", (evt) => {
            const pos = evt.renderedPosition;
            if (pos) setTooltip((prev) => (prev ? { ...prev, x: pos.x, y: pos.y } : prev));
          });
          cy.on("mouseout", "node", () => {
            cy.elements().removeClass("dimmed highlighted");
            setTooltip(null);
          });

          cy.on("tap", "node", (evt) => {
            const data = evt.target.data();
            if (data.type === "accused") {
              navigate(`/offenders?name=${encodeURIComponent(data.label)}`);
              return;
            }
            if (onNodeClick) onNodeClick(data);
          });
        }}
      />
      <Tooltip tooltip={tooltip} />
      <div className="absolute bottom-3 left-3 bg-surface-panel/90 border border-line rounded px-3 py-2 flex flex-col gap-1">
        {LEGEND_ITEMS.map((item) => (
          <div key={item.type} className="flex items-center gap-2">
            <span
              className="w-2.5 h-2.5 rounded-full shrink-0"
              style={{ backgroundColor: NODE_COLORS[item.type] }}
            />
            <span className="text-[10px] font-mono text-ink-faint uppercase tracking-wide">
              {item.label}
            </span>
          </div>
        ))}
        <div className="flex items-center gap-2 pt-1 mt-1 border-t border-line">
          <span className="w-2.5 h-2.5 rounded-full shrink-0 border-2 border-dashed" style={{ borderColor: "#D4A24C" }} />
          <span className="text-[10px] font-mono text-ink-faint uppercase tracking-wide">
            Repeat offender
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full shrink-0 border-2" style={{ borderColor: "#8B6FD6", borderStyle: "dotted" }} />
          <span className="text-[10px] font-mono text-ink-faint uppercase tracking-wide">
            Similar MO
          </span>
        </div>
      </div>
    </div>
  );
}
