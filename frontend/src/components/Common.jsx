import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { apiFetch } from "../api";

export const INDIA_BOUNDS = [
  [6, 68],
  [38, 98],
];

export function PageHeader({ title, subtitle }) {
  return (
    <div className="page-header">
      <h1>{title}</h1>
      {subtitle && <p>{subtitle}</p>}
    </div>
  );
}

export function MetricCard({ label, value, hint }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value ?? "—"}</div>
      {hint && <div className="metric-hint">{hint}</div>}
    </div>
  );
}

export function StatusBadge({ value }) {
  const v = String(value || "UNKNOWN");
  const cls = v.toLowerCase().replaceAll(" ", "-");

  return (
    <span className={`status-badge status-${cls}`}>
      {v.toUpperCase()}
    </span>
  );
}


export function DataContextStrip({
  mode = "PROJECT DATA",
  source = "Disaster AI India",
  updatedAt = null,
  status = null,
}) {
  const normalized = String(mode || "PROJECT DATA")
  .toLowerCase()
  .replace(/[^a-z0-9]+/g, "-")
  .replace(/^-+|-+$/g, "");

  const timeText = updatedAt
    ? new Date(updatedAt).toLocaleString()
    : "Current session";

  return (
    <div className="data-context-strip">
      <span className={`data-mode-badge data-mode-${normalized}`}>
        {mode}
      </span>

      <span>
        <strong>Source:</strong> {source}
      </span>

      <span>
        <strong>Last updated:</strong> {timeText}
      </span>

      {status && (
        <span>
          <strong>Status:</strong> {status}
        </span>
      )}
    </div>
  );
}

export function EmergencyHelpCard({
  compact = false,
}) {
  return (
    <aside
      className={
        compact
          ? "emergency-help-card compact"
          : "emergency-help-card"
      }
    >
      <div>
        <span className="emergency-help-kicker">
          EMERGENCY HELP
        </span>
        <strong>Need immediate assistance?</strong>
        <small>
          112 is India's pan-India emergency response number.
        </small>
      </div>

      <a
        className="emergency-call-button"
        href="tel:112"
      >
        Call 112
      </a>
    </aside>
  );
}

export function ErrorBlock({ error, onRetry }) {
  if (!error) return null;

  return (
    <div className="state-box error-box retry-error-box">
      <span>{error}</span>
      {onRetry && (
        <button
          type="button"
          className="small-button"
          onClick={onRetry}
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function LoadingBlock({ text = "Loading..." }) {
  return <div className="state-box">{text}</div>;
}

export function RecordPicker({ rowId, setRowId }) {
  const [types, setTypes] = useState([]);
  const [type, setType] = useState("");
  const [records, setRecords] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/disasters/types")
      .then((data) => setTypes(data.supported_disasters || []))
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    const path = type
      ? `/disasters?disaster_type=${encodeURIComponent(type)}&limit=100`
      : "/disasters?limit=100";

    apiFetch(path)
      .then((data) => {
        const rows = data.data || [];
        setRecords(rows);

        if (
          rows.length &&
          !rows.some((row) => Number(row.row_id) === Number(rowId))
        ) {
          setRowId(rows[0].row_id);
        }
      })
      .catch((err) => setError(err.message));
  }, [type]);

  return (
    <div className="selector-card compact-selector">
      <div className="selector-title">Select Indian disaster record</div>

      <div className="selector-grid compact-picker-grid">
        <label>
          Disaster type
          <select value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">All disaster types</option>
            {types.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>

        <label>
          Incident
          <select
            value={rowId ?? ""}
            onChange={(event) => setRowId(Number(event.target.value))}
          >
            {records.map((row) => (
              <option key={row.row_id} value={row.row_id}>
                #{row.row_id} · {row.disaster_type} · {row.disaster_subtype} · affected{" "}
                {Number(row.affected_population || 0).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
      </div>

      {error && <div className="inline-error">{error}</div>}
    </div>
  );
}

function ValueView({ value, depth = 0 }) {
  if (value === null || value === undefined) {
    return <span className="muted">N/A</span>;
  }

  if (typeof value !== "object") {
    return <strong>{String(value)}</strong>;
  }

  if (Array.isArray(value)) {
    if (!value.length) {
      return <span className="muted">None</span>;
    }

    return (
      <div className="tag-list">
        {value.map((item, index) =>
          typeof item === "object" ? (
            <div className="object-card" key={index}>
              <ValueView value={item} depth={depth + 1} />
            </div>
          ) : (
            <span className="soft-tag" key={index}>
              {String(item)}
            </span>
          )
        )}
      </div>
    );
  }

  return (
    <div className={depth === 0 ? "kv-grid" : "nested-grid"}>
      {Object.entries(value).map(([key, item]) => (
        <div className="kv-item" key={key}>
          <span>{key.replaceAll("_", " ")}</span>
          <ValueView value={item} depth={depth + 1} />
        </div>
      ))}
    </div>
  );
}

export function SmartResult({ data }) {
  if (!data) return null;

  return (
    <section className="panel">
      <ValueView value={data} />
    </section>
  );
}

export function LeafletMap({ points = [], depots = [] }) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const boundaryRef = useRef(null);
  const dynamicLayerRef = useRef(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;

    const map = L.map(ref.current, {
      maxBounds: INDIA_BOUNDS,
      maxBoundsViscosity: 1,
      minZoom: 4,
      maxZoom: 12,
    }).setView([22.6, 79.5], 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    dynamicLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    let cancelled = false;

    apiFetch("/public/india-boundary", { auth: false })
      .then((boundary) => {
        if (cancelled || !mapRef.current) return;

        boundaryRef.current = L.geoJSON(boundary, {
          style: {
            color: "#1f4f7a",
            weight: 2,
            fillOpacity: 0.02,
          },
        }).addTo(mapRef.current);
      })
      .catch(() => {
        // Boundary overlay is helpful, but the map should still work without it.
      });

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      cancelled = true;
      map.remove();
      mapRef.current = null;
      boundaryRef.current = null;
      dynamicLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const group = dynamicLayerRef.current;

    if (!map || !group) return;

    group.clearLayers();

    const validPoints = points.filter(
      (point) =>
        Number.isFinite(Number(point.latitude)) &&
        Number.isFinite(Number(point.longitude))
    );

    const visibleBounds = [];

    validPoints.forEach((point) => {
      const palette = {
        CRITICAL: "#d92d20",
        HIGH: "#f79009",
        MODERATE: "#f7c948",
        LOW: "#2e90fa",
      };

      const level = String(point.impact_class || "").toUpperCase();
      const color = palette[level] || "#2f80ed";
      const latitude = Number(point.latitude);
      const longitude = Number(point.longitude);

      L.circleMarker([latitude, longitude], {
        radius: 6 + Number(point.severity_score || 0) * 5,
        weight: 1.6,
        color,
        fillColor: color,
        fillOpacity: 0.78,
      })
        .addTo(group)
        .bindPopup(
          `<strong>${point.disaster_type}</strong><br/>` +
            `Incident #${point.row_id}<br/>` +
            `Affected: ${Number(point.affected_population || 0).toLocaleString()}<br/>` +
            `Severity: ${(Number(point.severity_score || 0) * 100).toFixed(0)}%` +
            (point.impact_class ? `<br/>Impact: ${point.impact_class}` : "")
        );

      visibleBounds.push([latitude, longitude]);
    });

    depots.forEach((depot) => {
      const latitude = Number(depot.latitude);
      const longitude = Number(depot.longitude);

      if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return;

      L.circleMarker([latitude, longitude], {
        radius: 7,
        weight: 2,
        color: "#0f766e",
        fillColor: "#14b8a6",
        fillOpacity: 0.92,
      })
        .addTo(group)
        .bindPopup(
          `<strong>${depot.name}</strong><br/>` +
            `${depot.city}, ${depot.state}, India<br/>` +
            `Resource depot · ${depot.status}`
        );

      visibleBounds.push([latitude, longitude]);
    });

    if (visibleBounds.length > 1) {
      map.fitBounds(L.latLngBounds(visibleBounds), {
        padding: [20, 20],
        maxZoom: 6,
      });
    } else {
      map.setView([22.6, 79.5], 5);
    }

    setTimeout(() => map.invalidateSize(), 80);
  }, [points, depots]);

  return <div ref={ref} className="leaflet-map" />;
}
