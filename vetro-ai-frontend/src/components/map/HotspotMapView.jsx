import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import { Filter } from "lucide-react";
import "leaflet/dist/leaflet.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.Default.css";
import { apiGet } from "../../lib/apiClient";
import LoadingState from "../ui/LoadingState";
import SplitPaneShell from "../ui/SplitPaneShell";
import EmptyState from "../ui/EmptyState";

// Karnataka's approximate center -- reasonable default view before any
// data loads or if a query returns nothing.
const KARNATAKA_CENTER = [15.3173, 75.7139];

export default function HotspotMapView() {
  const navigate = useNavigate();
  const [points, setPoints] = useState([]);
  const [crimeTypeOptions, setCrimeTypeOptions] = useState([]);
  const [crimeType, setCrimeType] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPoint, setSelectedPoint] = useState(null);

  useEffect(() => {
    apiGet("/analytics/crime-types")
      .then((rows) => setCrimeTypeOptions(rows.map((r) => r.crime_type)))
      .catch((err) => console.error("Failed to load crime types:", err));
  }, []);

  useEffect(() => {
    setIsLoading(true);
    setSelectedPoint(null);
    const query = crimeType ? `?limit=5000&crime_type=${encodeURIComponent(crimeType)}` : "?limit=5000";
    apiGet(`/map/hotspots${query}`)
      .then(setPoints)
      .catch((err) => setError(err.message))
      .finally(() => setIsLoading(false));
  }, [crimeType]);

  return (
    <SplitPaneShell
      sidebar={
        <>
          <div className="px-4 py-3 border-b border-line">
            <h2 className="font-mono text-xs uppercase tracking-wider text-accent">
              Hotspot Map
            </h2>
            <div className="flex items-center gap-2 mt-3">
              <Filter className="w-3.5 h-3.5 text-ink-faint shrink-0" />
              <select
                value={crimeType}
                onChange={(e) => setCrimeType(e.target.value)}
                className="w-full bg-surface-panel border border-line rounded px-2 py-1.5 text-xs
                           text-ink-secondary font-mono focus:outline-none focus:border-accent"
              >
                <option value="">All Crime Types</option>
                {crimeTypeOptions.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
            <p className="text-[11px] text-ink-faint mt-2 leading-snug">
              {points.length} case{points.length !== 1 ? "s" : ""} plotted &middot; markers cluster
              automatically, zoom in to split them apart
            </p>
          </div>
          <div className="flex-1 overflow-y-auto">
            {selectedPoint ? (
              <div>
                <div className="px-4 py-2.5 border-b border-line flex items-center justify-between">
                  <span className="text-[11px] font-mono uppercase text-ink-faint">Selected case</span>
                  <button
                    onClick={() => setSelectedPoint(null)}
                    className="text-[10px] font-mono uppercase text-ink-dim hover:text-accent"
                  >
                    Clear
                  </button>
                </div>
                <button
                  onClick={() => navigate(`/network?case=${selectedPoint.case_id}`)}
                  className="w-full text-left px-4 py-3 hover:bg-surface-panel/60 transition-colors"
                >
                  <p className="text-xs text-ink-secondary">{selectedPoint.crime_type}</p>
                  <p className="text-[10px] text-ink-dim font-mono mt-0.5">
                    Case #{selectedPoint.case_id} &middot; {selectedPoint.date}
                  </p>
                  <p className="text-[10px] text-accent font-mono mt-1.5">View in Network Graph &rarr;</p>
                </button>
              </div>
            ) : (
              <EmptyState
                title="No case selected"
                hint="Click a marker on the map to see its details. Click a cluster to zoom in."
              />
            )}
          </div>
        </>
      }
    >
      <div className="h-full relative">
        {isLoading && (
          <div className="absolute inset-0 z-[1000] bg-surface-base/70">
            <LoadingState size="lg" />
          </div>
        )}
        {error && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-[1000] bg-status-error/20 border border-status-error
                           text-status-error text-xs font-mono px-3 py-1.5 rounded">
            Failed to load hotspots: {error}
          </div>
        )}
        <MapContainer
          center={KARNATAKA_CENTER}
          zoom={7}
          className="h-full w-full"
          style={{ background: "#0B1120" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <MarkerClusterGroup chunkedLoading>
            {points.map((p) => (
              <CircleMarker
                key={p.case_id}
                center={[p.lat, p.lng]}
                radius={7}
                eventHandlers={{ click: () => setSelectedPoint(p) }}
                pathOptions={{
                  color: "#D4A24C",
                  fillColor: "#D4A24C",
                  fillOpacity: 0.55,
                  weight: 1.5,
                }}
              >
                <Popup className="vetro-popup">
                  <div className="font-mono text-xs">
                    <strong>{p.crime_type}</strong>
                    <br />
                    Case #{p.case_id} &middot; {p.date}
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </MarkerClusterGroup>
        </MapContainer>
      </div>
    </SplitPaneShell>
  );
}
