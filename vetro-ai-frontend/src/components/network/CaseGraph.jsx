import { useRef } from "react";
import CytoscapeComponent from "react-cytoscapejs";

/**
 * Renders the {nodes, edges} shape /graph/case/{id} already returns
 * (see api/routes/graph.py, infrastructure/persistence/postgres_repository.py
 * get_case_network) as a Cytoscape graph. Node/edge shape is unchanged
 * from what the backend already produced for this feature, before any
 * frontend existed to consume it -- victim/accused nodes now also carry
 * age/gender so onNodeClick can show a detail panel without a second fetch.
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
    data: { id: n.id, label: n.label, type: n.type, age: n.age, gender: n.gender, crossCase: n.cross_case, caseCount: n.case_count },
    classes: n.cross_case ? "cross-case" : undefined,
  }));
  const edges = graph.edges.map((e, i) => ({
    data: {
      id: `e${i}_${e.source}_${e.target}`,
      source: e.source,
      target: e.target,
      label: e.label ?? "",
    },
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
    selector: "node.dimmed",
    style: { opacity: 0.25 },
  },
  {
    selector: "node.highlighted",
    style: { "border-color": "#D4A24C", "border-width": 3 },
  },
  {
    selector: "edge",
    style: {
      width: 1.5,
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
    selector: "edge.dimmed",
    style: { opacity: 0.15 },
  },
];

export default function CaseGraph({ graph, onNodeClick }) {
  const cyRef = useRef(null);

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-ink-faint text-sm font-mono">
        No graph data
      </div>
    );
  }

  return (
    <div className="relative h-full w-full">
      <CytoscapeComponent
        elements={toElements(graph)}
        stylesheet={stylesheet}
        layout={{ name: "cose", animate: false, padding: 40 }}
        style={{ width: "100%", height: "100%" }}
        cy={(cy) => {
          cyRef.current = cy;
          cy.removeAllListeners();

          cy.on("layoutstop", () => cy.fit(undefined, 40));

          cy.on("mouseover", "node", (evt) => {
            const node = evt.target;
            const neighborhood = node.closedNeighborhood();
            cy.elements().not(neighborhood).addClass("dimmed");
            neighborhood.addClass("highlighted");
          });
          cy.on("mouseout", "node", () => {
            cy.elements().removeClass("dimmed highlighted");
          });

          if (onNodeClick) {
            cy.on("tap", "node", (evt) => {
              onNodeClick(evt.target.data());
            });
          }
        }}
      />
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
      </div>
    </div>
  );
}
