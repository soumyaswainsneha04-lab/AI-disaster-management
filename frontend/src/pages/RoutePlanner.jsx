import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { apiFetch } from "../api";
import {
  PageHeader,
  ErrorBlock,
  LoadingBlock,
  MetricCard,
  INDIA_BOUNDS,
  DataContextStrip,
} from "../components/Common";

function RouteMap({ result }) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const layerRef = useRef(null);

  useEffect(() => {
    if (!ref.current || mapRef.current) return;

    const map = L.map(ref.current, {
      maxBounds: INDIA_BOUNDS,
      maxBoundsViscosity: 1,
      minZoom: 4,
    }).setView([22.6, 79.5], 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    layerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      map.remove();
      mapRef.current = null;
      layerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const group = layerRef.current;
    if (!map || !group || !result) return;

    group.clearLayers();

    const colors = ["#2f80ed", "#7c3aed", "#16a34a", "#f79009", "#d92d20"];
    const allPoints = [];

    (result.routes || []).forEach((route, index) => {
      const color = colors[index % colors.length];
      const geometry =
        route.route_geometry?.length > 1
          ? route.route_geometry.map(([lat, lon]) => [Number(lat), Number(lon)])
          : route.stops.map((stop) => [Number(stop.latitude), Number(stop.longitude)]);

      allPoints.push(...geometry);

      L.polyline(geometry, {
        color,
        weight: 5,
        opacity: 0.88,
        dashArray: route.route_source === "Haversine fallback" ? "10 8" : undefined,
      }).addTo(group);

      route.stops.forEach((stop, stopIndex) => {
        const isDepot = stop.type === "DEPOT";
        L.circleMarker([stop.latitude, stop.longitude], {
          radius: isDepot ? 8 : 6,
          color,
          weight: 2,
          fillColor: isDepot ? "#ffffff" : color,
          fillOpacity: 0.95,
        })
          .addTo(group)
          .bindPopup(
            isDepot
              ? `Vehicle ${route.vehicle_id} · Depot`
              : `Vehicle ${route.vehicle_id} · Stop ${stopIndex} · ${stop.disaster_type || "Disaster"} #${stop.row_id}`
          );
      });
    });

    if (allPoints.length > 1) {
      map.fitBounds(L.latLngBounds(allPoints), {
        padding: [30, 30],
        maxZoom: 8,
      });
    }

    setTimeout(() => map.invalidateSize(), 80);
  }, [result]);

  return <div ref={ref} className="operations-map route-road-map" />;
}

export default function RoutePlanner() {
  const [records, setRecords] = useState([]);
  const [depots, setDepots] = useState([]);
  const [depotId, setDepotId] = useState("");
  const [selected, setSelected] = useState([]);
  const [vehicles, setVehicles] = useState(1);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([apiFetch("/disasters?limit=60"), apiFetch("/inventory")])
      .then(([disasterData, inventoryData]) => {
        setRecords(disasterData.data || []);
        setDepots(inventoryData.depots || []);
        if (inventoryData.depots?.length) {
          setDepotId(inventoryData.depots[0].depot_id);
        }
      })
      .catch((err) => setError(err.message));
  }, []);

  const depot = depots.find((item) => item.depot_id === depotId);

  async function run() {
    if (!selected.length) {
      setError("Select at least one disaster zone.");
      return;
    }
    if (!depot) {
      setError("Select a resource depot.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await apiFetch("/routing/optimize", {
        method: "POST",
        body: JSON.stringify({
          depot_latitude: depot.latitude,
          depot_longitude: depot.longitude,
          row_ids: selected,
          vehicle_count: Number(vehicles),
          average_speed_kmph: 40,
        }),
      });
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="India Delivery Routes"
        subtitle="OR-Tools chooses the stop order; when available, the map uses real road geometry from OSRM instead of straight lines."
      />

      <DataContextStrip
        mode="AI / OPTIMIZATION"
        source="OR-Tools + OSRM road routing"
        updatedAt={result ? new Date().toISOString() : null}
        status={result?.road_routes_found ? "Road geometry available" : "Ready"}
      />

      <div className="route-controls compact-route-controls">
        <label>
          Resource depot
          <select value={depotId} onChange={(event) => setDepotId(event.target.value)}>
            {depots.map((item) => (
              <option key={item.depot_id} value={item.depot_id}>
                {item.city}, {item.state}
              </option>
            ))}
          </select>
        </label>

        <label>
          Vehicles
          <input
            type="number"
            min="1"
            max="5"
            value={vehicles}
            onChange={(event) => setVehicles(event.target.value)}
          />
        </label>

        <button className="primary-button" onClick={run} disabled={loading}>
          {loading ? "Building Road Routes..." : "Optimize Routes"}
        </button>
      </div>

      {depot && (
        <div className="source-depot-strip">
          <div>
            <span>Selected Depot</span>
            <strong>{depot.name}</strong>
            <small>
              {depot.city}, {depot.state}, India · {Number(depot.latitude).toFixed(4)}, {Number(depot.longitude).toFixed(4)}
            </small>
          </div>
        </div>
      )}

      <div className="route-zone-grid compact-route-zones">
        {records.map((record) => (
          <label
            className={`route-zone-option ${selected.includes(record.row_id) ? "selected" : ""}`}
            key={record.row_id}
          >
            <input
              type="checkbox"
              checked={selected.includes(record.row_id)}
              onChange={() =>
                setSelected((current) =>
                  current.includes(record.row_id)
                    ? current.filter((id) => id !== record.row_id)
                    : current.length < 15
                      ? [...current, record.row_id]
                      : current
                )
              }
            />
            <span>#{record.row_id} · {record.disaster_type}</span>
            <small>{record.disaster_subtype}</small>
          </label>
        ))}
      </div>

      <ErrorBlock error={error} onRetry={selected.length ? run : undefined} />
      {loading && <LoadingBlock text="Optimizing stop order and requesting road geometry..." />}

      {result && (
        <>
          <div className="metrics-grid">
            <MetricCard label="Vehicles" value={result.vehicle_count} />
            <MetricCard label="Road / Route Distance" value={`${result.total_route_distance_km} km`} />
            <MetricCard label="Depot" value={depot?.city} />
            <MetricCard label="Road Routes Found" value={`${result.road_routes_found}/${result.vehicle_count}`} />
          </div>

          <div className="route-result-grid">
            {(result.routes || []).map((route) => (
              <article className="route-result-card" key={route.vehicle_id}>
                <div>
                  <span>Vehicle {route.vehicle_id}</span>
                  <strong>{route.distance_km} km</strong>
                </div>
                <div>
                  <span>Estimated response time</span>
                  <strong>{route.estimated_minutes} min</strong>
                </div>
                <div>
                  <span>Map route source</span>
                  <strong>{route.route_source}</strong>
                </div>
                <div>
                  <span>Stops</span>
                  <strong>{Math.max((route.stops || []).length - 2, 0)}</strong>
                </div>
              </article>
            ))}
          </div>

          <section className="panel">
            <RouteMap result={result} />
          </section>

          <div className="note-box">{result.note}</div>
        </>
      )}
    </div>
  );
}
