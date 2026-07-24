import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import L from "leaflet";
import {
  CircleMarker,
  MapContainer,
  Marker,
  Popup,
  TileLayer,
  useMap,
} from "react-leaflet";
import MarkerClusterGroup from "react-leaflet-cluster";
import { AlertTriangle, Clock3, Filter, Layers3 } from "lucide-react";
import "leaflet/dist/leaflet.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.css";
import "react-leaflet-cluster/dist/assets/MarkerCluster.Default.css";
import { apiGet } from "../../lib/apiClient";
import LoadingState from "../ui/LoadingState";
import SplitPaneShell from "../ui/SplitPaneShell";
import EmptyState from "../ui/EmptyState";

const KARNATAKA_CENTER = [15.3173, 75.7139];

const TIME_SLOTS = [
  { value: "all", label: "All day", range: "00:00–24:00" },
  { value: "night", label: "Night", range: "00:00–06:00" },
  { value: "morning", label: "Morning", range: "06:00–12:00" },
  { value: "afternoon", label: "Afternoon", range: "12:00–18:00" },
  { value: "evening", label: "Evening", range: "18:00–24:00" },
];

const PERIOD_OPTIONS = [
  { value: "all", label: "All months / seasons" },
  { value: "month:01", label: "January" },
  { value: "month:02", label: "February" },
  { value: "month:03", label: "March" },
  { value: "month:04", label: "April" },
  { value: "month:05", label: "May" },
  { value: "month:06", label: "June" },
  { value: "month:07", label: "July" },
  { value: "month:08", label: "August" },
  { value: "month:09", label: "September" },
  { value: "month:10", label: "October" },
  { value: "month:11", label: "November" },
  { value: "month:12", label: "December" },
  { value: "season:summer", label: "Summer · Mar–May" },
  { value: "season:monsoon", label: "Monsoon · Jun–Sep" },
  { value: "season:post_monsoon", label: "Post-monsoon · Oct–Nov" },
  { value: "season:winter", label: "Winter · Dec–Feb" },
];

const normalMarkerIcon = L.divIcon({
  className: "vetro-marker-icon",
  iconSize: [18, 18],
  iconAnchor: [9, 9],
  html: '<span class="vetro-crime-marker"></span>',
});

const emergingMarkerIcon = L.divIcon({
  className: "vetro-marker-icon",
  iconSize: [18, 18],
  iconAnchor: [9, 9],
  html: '<span class="vetro-crime-marker vetro-crime-marker--emerging"></span>',
});

function HeatmapLayer({ points }) {
  const map = useMap();
  const heatPoints = useMemo(
    () => points.map((point) => [point.lat, point.lng, 1]),
    [points],
  );

  useEffect(() => {
    if (!heatPoints.length || typeof L.heatLayer !== "function") return undefined;

    const heatLayer = L.heatLayer(heatPoints, {
      radius: 30,
      blur: 24,
      maxZoom: 15,
      minOpacity: 0.35,
      gradient: {
        0.2: "#2563eb",
        0.42: "#22c55e",
        0.64: "#facc15",
        0.82: "#f97316",
        1: "#dc2626",
      },
    }).addTo(map);

    return () => map.removeLayer(heatLayer);
  }, [heatPoints, map]);

  return null;
}

function FitMapBounds({ points, warnings }) {
  const map = useMap();

  useEffect(() => {
    const coordinates = [
      ...points.map((point) => [point.lat, point.lng]),
      ...warnings.map((warning) => [warning.lat, warning.lng]),
    ];

    if (!coordinates.length) return;
    map.fitBounds(L.latLngBounds(coordinates), { padding: [40, 40], maxZoom: 13 });
  }, [map, points, warnings]);

  return null;
}

function coordinateLabel(lat, lng) {
  return `${Number(lat).toFixed(5)}, ${Number(lng).toFixed(5)}`;
}

function displayDate(value) {
  return value || "Not recorded";
}

export default function HotspotMapView() {
  const navigate = useNavigate();
  const [points, setPoints] = useState([]);
  const [emergingClusters, setEmergingClusters] = useState([]);
  const [crimeTypeOptions, setCrimeTypeOptions] = useState([]);
  const [crimeType, setCrimeType] = useState("");
  const [timeSlotIndex, setTimeSlotIndex] = useState(0);
  const [period, setPeriod] = useState("all");
  const [mapMode, setMapMode] = useState("markers");
  const [heatmapReady, setHeatmapReady] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedPoint, setSelectedPoint] = useState(null);

  const selectedTimeSlot = TIME_SLOTS[timeSlotIndex];

  useEffect(() => {
    apiGet("/analytics/crime-types")
      .then((rows) => setCrimeTypeOptions(rows.map((row) => row.crime_type)))
      .catch((requestError) => console.error("Failed to load crime types:", requestError));
  }, []);

  useEffect(() => {
    let active = true;

    // leaflet.heat 0.2.0's distributed script registers against global L.
    // Import it only after exposing the same Leaflet instance Vite imported.
    window.L = L;
    import("leaflet.heat")
      .then(() => {
        if (typeof L.heatLayer !== "function") {
          throw new Error("Leaflet heat layer did not register correctly.");
        }
        if (active) setHeatmapReady(true);
      })
      .catch((requestError) => {
        if (active) setError(requestError.message);
      });

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    const query = new URLSearchParams({
      limit: "5000",
      time_slot: selectedTimeSlot.value,
    });

    if (crimeType) query.set("crime_type", crimeType);
    if (period.startsWith("month:")) query.set("month", period.slice(6));
    if (period.startsWith("season:")) query.set("season", period.slice(7));

    setIsLoading(true);
    setError(null);
    setSelectedPoint(null);

    apiGet(`/map/hotspots?${query.toString()}`)
      .then((payload) => {
        if (!active) return;
        // The array fallback keeps a rolling upgrade from breaking an older API.
        setPoints(Array.isArray(payload) ? payload : payload.incidents ?? []);
        setEmergingClusters(Array.isArray(payload) ? [] : payload.emergingClusters ?? []);
      })
      .catch((requestError) => {
        if (!active) return;
        setError(requestError.message);
        setPoints([]);
        setEmergingClusters([]);
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });

    return () => {
      active = false;
    };
  }, [crimeType, period, selectedTimeSlot.value]);

  return (
    <SplitPaneShell
      sidebar={
        <>
          <div className="px-4 py-3 border-b border-line">
            <h2 className="font-mono text-xs uppercase tracking-wider text-accent">
              Hotspot Intelligence
            </h2>

            <div className="mt-3 space-y-3">
              <label className="block">
                <span className="flex items-center gap-2 text-[10px] font-mono uppercase text-ink-faint">
                  <Filter className="w-3.5 h-3.5" /> Crime type
                </span>
                <select
                  value={crimeType}
                  onChange={(event) => setCrimeType(event.target.value)}
                  className="mt-1.5 w-full bg-surface-panel border border-line rounded px-2 py-1.5 text-xs
                             text-ink-secondary font-mono focus:outline-none focus:border-accent"
                >
                  <option value="">All Crime Types</option>
                  {crimeTypeOptions.map((type) => (
                    <option key={type} value={type}>{type}</option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="text-[10px] font-mono uppercase text-ink-faint">Month / season</span>
                <select
                  value={period}
                  onChange={(event) => setPeriod(event.target.value)}
                  className="mt-1.5 w-full bg-surface-panel border border-line rounded px-2 py-1.5 text-xs
                             text-ink-secondary font-mono focus:outline-none focus:border-accent"
                >
                  {PERIOD_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>{option.label}</option>
                  ))}
                </select>
              </label>

              <div>
                <div className="flex items-center justify-between gap-2 text-[10px] font-mono uppercase text-ink-faint">
                  <span className="flex items-center gap-2"><Clock3 className="w-3.5 h-3.5" /> Time of day</span>
                  <span className="text-accent">{selectedTimeSlot.range}</span>
                </div>
                <input
                  aria-label="Time of day"
                  className="mt-2 w-full accent-accent"
                  type="range"
                  min="0"
                  max={TIME_SLOTS.length - 1}
                  value={timeSlotIndex}
                  onChange={(event) => setTimeSlotIndex(Number(event.target.value))}
                />
                <p className="mt-1 text-[11px] text-ink-secondary">{selectedTimeSlot.label}</p>
              </div>

              <div>
                <span className="flex items-center gap-2 text-[10px] font-mono uppercase text-ink-faint">
                  <Layers3 className="w-3.5 h-3.5" /> Map layer
                </span>
                <div className="mt-1.5 grid grid-cols-2 rounded border border-line p-0.5">
                  <button
                    type="button"
                    onClick={() => setMapMode("markers")}
                    className={`rounded px-2 py-1.5 text-[10px] font-mono uppercase transition-colors ${
                      mapMode === "markers"
                        ? "bg-accent text-surface-base"
                        : "text-ink-faint hover:text-ink-secondary"
                    }`}
                  >
                    Markers
                  </button>
                  <button
                    type="button"
                    onClick={() => setMapMode("heatmap")}
                    className={`rounded px-2 py-1.5 text-[10px] font-mono uppercase transition-colors ${
                      mapMode === "heatmap"
                        ? "bg-accent text-surface-base"
                        : "text-ink-faint hover:text-ink-secondary"
                    }`}
                  >
                    Heatmap
                  </button>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-ink-faint mt-3 leading-snug">
              {points.length} case{points.length !== 1 ? "s" : ""} shown · {mapMode === "heatmap"
                ? "density is aggregated live"
                : "markers cluster as you zoom"}
            </p>
          </div>

          <div className="flex-1 overflow-y-auto">
            <section className="px-4 py-3 border-b border-line">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-3.5 h-3.5 text-status-error" />
                <h3 className="font-mono text-[10px] uppercase tracking-wider text-status-error">
                  Live early warnings
                </h3>
              </div>

              {emergingClusters.length ? (
                <div className="mt-2 space-y-2">
                  {emergingClusters.map((cluster) => (
                    <article
                      key={cluster.cluster_id}
                      className="border border-status-error/35 bg-status-error/10 rounded px-2.5 py-2"
                    >
                      <p className="text-xs text-ink-secondary leading-snug">
                        <span className="font-semibold text-status-error">Early Warning:</span>{" "}
                        Emerging {cluster.crime_type} Cluster
                      </p>
                      <p className="mt-1 text-[10px] font-mono text-ink-dim">
                        {coordinateLabel(cluster.lat, cluster.lng)}
                      </p>
                      <p className="mt-1 text-[10px] text-ink-faint">
                        {cluster.recent_incident_count} incidents in 7 days · baseline {cluster.expected_weekly_baseline}/week
                      </p>
                    </article>
                  ))}
                </div>
              ) : (
                <p className="mt-2 text-[11px] leading-snug text-ink-faint">
                  No atypical location cluster has exceeded the 4-incident, 7-day threshold.
                </p>
              )}
            </section>

            {selectedPoint ? (
              <section>
                <div className="px-4 py-2.5 border-b border-line flex items-center justify-between">
                  <span className="text-[11px] font-mono uppercase text-ink-faint">Selected case</span>
                  <button
                    type="button"
                    onClick={() => setSelectedPoint(null)}
                    className="text-[10px] font-mono uppercase text-ink-dim hover:text-accent"
                  >
                    Clear
                  </button>
                </div>
                <button
                  type="button"
                  onClick={() => navigate(`/network?case=${selectedPoint.case_id}`)}
                  className="w-full text-left px-4 py-3 hover:bg-surface-panel/60 transition-colors"
                >
                  <p className="text-xs text-ink-secondary">{selectedPoint.crime_type}</p>
                  <p className="text-[10px] text-ink-dim font-mono mt-0.5">
                    Case #{selectedPoint.case_id} · {displayDate(selectedPoint.crime_registered_date)}
                  </p>
                  <p className="text-[10px] text-accent font-mono mt-1.5">View in Network Graph →</p>
                </button>
              </section>
            ) : (
              <EmptyState
                title="No case selected"
                hint="Click a marker to inspect its case details and open its network graph."
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

          <FitMapBounds points={points} warnings={emergingClusters} />

          {mapMode === "heatmap" && heatmapReady ? (
            <HeatmapLayer points={points} />
          ) : (
            <MarkerClusterGroup chunkedLoading>
              {points.map((point) => (
                <Marker
                  key={point.case_id}
                  position={[point.lat, point.lng]}
                  icon={point.is_emerging ? emergingMarkerIcon : normalMarkerIcon}
                  eventHandlers={{ click: () => setSelectedPoint(point) }}
                >
                  <Popup className="vetro-popup">
                    <div className="font-mono text-xs space-y-1">
                      {point.is_emerging && (
                        <span className="inline-flex rounded bg-status-error/20 px-1.5 py-0.5 text-[9px] uppercase text-status-error">
                          Emerging cluster
                        </span>
                      )}
                      <p><strong>{point.crime_type}</strong></p>
                      <p>Case #{point.case_id} · {displayDate(point.crime_registered_date)}</p>
                      <p className="text-[10px] text-ink-dim">{coordinateLabel(point.lat, point.lng)}</p>
                      <button
                        type="button"
                        onClick={() => navigate(`/network?case=${point.case_id}`)}
                        className="text-[10px] text-accent hover:underline"
                      >
                        Open Network Graph →
                      </button>
                    </div>
                  </Popup>
                </Marker>
              ))}
            </MarkerClusterGroup>
          )}

          {/* Warning centres stay visible even when density heatmap is selected. */}
          {emergingClusters.map((cluster) => (
            <CircleMarker
              key={cluster.cluster_id}
              center={[cluster.lat, cluster.lng]}
              radius={18}
              pathOptions={{
                color: "#ef4444",
                weight: 3,
                fillColor: "#dc2626",
                fillOpacity: 0.25,
                className: "vetro-emerging-ring",
              }}
            >
              <Popup className="vetro-popup">
                <div className="font-mono text-xs space-y-1">
                  <p className="text-status-error"><strong>Early Warning</strong></p>
                  <p>Emerging {cluster.crime_type} Cluster</p>
                  <p>{cluster.recent_incident_count} incidents registered in the last 7 days</p>
                  <p className="text-[10px] text-ink-dim">{coordinateLabel(cluster.lat, cluster.lng)}</p>
                </div>
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </SplitPaneShell>
  );
}
