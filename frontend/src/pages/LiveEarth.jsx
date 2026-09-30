import { useEffect, useMemo, useRef, useState } from "react";
import L from "leaflet";
import {
  Activity,
  Clock3,
  ExternalLink,
  Layers3,
  Play,
  RadioTower,
  RefreshCw,
  Satellite,
  Square,
} from "lucide-react";
import { apiFetch } from "../api";
import {
  DataContextStrip,
  ErrorBlock,
  PageHeader,
} from "../components/Common";

const INDIA_CENTER = [22.6, 79.5];
const INDIA_BOUNDS = [
  [6, 68],
  [38, 98],
];

const GIBS_WMS_URL =
  "https://gibs.earthdata.nasa.gov/wms/epsg3857/best/wms.cgi";

const SATELLITE_LAYERS = {
  infrared: {
    id: "Himawari_AHI_Band13_Clean_Infrared",
    label: "Infrared",
    shortLabel: "IR",
    description:
      "10.3 µm clean infrared for day-and-night cloud structure and weather-system monitoring.",
  },
  visible: {
    id: "Himawari_AHI_Band3_Red_Visible_1km",
    label: "Visible",
    shortLabel: "VIS",
    description:
      "0.64 µm red-visible imagery for daytime cloud and surface context.",
  },
  airMass: {
    id: "Himawari_AHI_Air_Mass",
    label: "Air Mass",
    shortLabel: "AIR",
    description:
      "Air-mass RGB imagery for viewing broader atmospheric structures.",
  },
};

function floorToTenMinutes(timestamp) {
  return Math.floor(timestamp / 600000) * 600000;
}

function buildAnchor(now = Date.now()) {
  // Keep a small safety lag so the newest requested frame is more likely to
  // exist in the public NRT imagery service.
  return floorToTenMinutes(now - 20 * 60 * 1000);
}

function formatUtc(timestamp) {
  return new Date(timestamp).toLocaleString("en-IN", {
    timeZone: "UTC",
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }) + " UTC";
}

function formatLocal(timestamp) {
  return new Date(timestamp).toLocaleString("en-IN", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function frameTimes(anchor) {
  return Array.from({ length: 13 }, (_, index) =>
    anchor - (12 - index) * 10 * 60 * 1000
  );
}

export default function LiveEarth() {
  const mapElementRef = useRef(null);
  const mapRef = useRef(null);
  const satelliteLayerRef = useRef(null);
  const boundaryLayerRef = useRef(null);
  const playbackRef = useRef(null);

  const [layerKey, setLayerKey] = useState("infrared");
  const [anchor, setAnchor] = useState(() => buildAnchor());
  const [frameIndex, setFrameIndex] = useState(12);
  const [playing, setPlaying] = useState(false);
  const [mapReady, setMapReady] = useState(false);
  const [error, setError] = useState("");

  const frames = useMemo(() => frameTimes(anchor), [anchor]);
  const selectedTime = frames[frameIndex] || anchor;
  const selectedLayer = SATELLITE_LAYERS[layerKey];

  useEffect(() => {
    if (!mapElementRef.current || mapRef.current) return undefined;

    const map = L.map(mapElementRef.current, {
      minZoom: 4,
      maxZoom: 9,
      maxBounds: INDIA_BOUNDS,
      maxBoundsViscosity: 1,
      zoomControl: true,
    }).setView(INDIA_CENTER, 5);

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: "&copy; OpenStreetMap contributors",
    }).addTo(map);

    mapRef.current = map;
    setMapReady(true);

    let cancelled = false;

    apiFetch("/public/india-boundary", { auth: false })
      .then((boundary) => {
        if (cancelled || !mapRef.current) return;

        boundaryLayerRef.current = L.geoJSON(boundary, {
          style: {
            color: "#0b5f63",
            weight: 2,
            fillOpacity: 0.01,
            dashArray: "6 5",
          },
        }).addTo(mapRef.current);
      })
      .catch(() => {
        // Satellite imagery remains usable if the project boundary endpoint
        // is temporarily unavailable.
      });

    setTimeout(() => map.invalidateSize(), 100);

    return () => {
      cancelled = true;
      if (playbackRef.current) {
        clearInterval(playbackRef.current);
      }
      map.remove();
      mapRef.current = null;
      satelliteLayerRef.current = null;
      boundaryLayerRef.current = null;
      setMapReady(false);
    };
  }, []);

  useEffect(() => {
    if (!mapReady || !mapRef.current) return undefined;

    const map = mapRef.current;
    setError("");

    if (satelliteLayerRef.current) {
      map.removeLayer(satelliteLayerRef.current);
      satelliteLayerRef.current = null;
    }

    try {
      const layer = L.tileLayer.wms(GIBS_WMS_URL, {
        layers: selectedLayer.id,
        format: "image/png",
        transparent: true,
        version: "1.3.0",
        attribution:
          "NASA GIBS / NASA Worldview; Himawari-9/AHI imagery provided through NASA SPoRT",
        time: new Date(selectedTime).toISOString(),
        opacity: 0.82,
        tileSize: 256,
        crossOrigin: true,
      });

      layer.on("tileerror", () => {
        setError(
          "The selected satellite frame is not available from NASA GIBS yet. Try Refresh or choose another frame."
        );
      });

      layer.addTo(map);
      satelliteLayerRef.current = layer;
      setTimeout(() => map.invalidateSize(), 80);
    } catch (err) {
      setError(err.message || "Unable to load satellite imagery.");
    }

    return undefined;
  }, [mapReady, selectedLayer.id, selectedTime]);

  useEffect(() => {
    if (!playing) {
      if (playbackRef.current) {
        clearInterval(playbackRef.current);
        playbackRef.current = null;
      }
      return undefined;
    }

    playbackRef.current = setInterval(() => {
      setFrameIndex((current) => (current >= frames.length - 1 ? 0 : current + 1));
    }, 1400);

    return () => {
      if (playbackRef.current) {
        clearInterval(playbackRef.current);
        playbackRef.current = null;
      }
    };
  }, [playing, frames.length]);

  function refresh() {
    setPlaying(false);
    setAnchor(buildAnchor());
    setFrameIndex(12);
  }

  return (
    <div className="live-earth-page">
      <PageHeader
        title="Live Earth"
        subtitle="Near-real-time satellite and weather intelligence for India using geostationary Himawari-9 imagery through NASA GIBS."
      />

      <DataContextStrip
        mode="LIVE DATA"
        source="NASA GIBS · Himawari-9/AHI"
        updatedAt={selectedTime}
        status="Near-real-time · 10-minute imagery cadence"
      />

      <section className="live-earth-hero">
        <div>
          <div className="live-earth-kicker">
            <span className="live-pulse" />
            SATELLITE WEATHER MONITORING
          </div>
          <h2>India from orbit</h2>
          <p>
            Track cloud structures and evolving weather systems with a time
            slider instead of relying on a static map snapshot.
          </p>
        </div>

        <div className="live-earth-source-badge">
          <Satellite size={20} />
          <div>
            <strong>Himawari-9 / AHI</strong>
            <span>Geostationary · NRT</span>
          </div>
        </div>
      </section>

      <ErrorBlock error={error} onRetry={refresh} />

      <div className="live-earth-grid">
        <section className="panel live-earth-map-panel">
          <div className="panel-heading live-earth-panel-heading">
            <div>
              <h3>India satellite view</h3>
              <p>{selectedLayer.description}</p>
            </div>

            <button
              type="button"
              className="small-button live-earth-refresh"
              onClick={refresh}
              title="Refresh latest available frame"
            >
              <RefreshCw size={15} />
              Refresh
            </button>
          </div>

          <div className="live-earth-map-wrap">
            <div ref={mapElementRef} className="live-earth-map" />

            <div className="live-earth-map-overlay">
              <span className="live-earth-overlay-pill">
                <RadioTower size={13} /> NRT
              </span>
              <span className="live-earth-overlay-pill">
                {selectedLayer.shortLabel}
              </span>
            </div>
          </div>

          <div className="live-earth-timeline">
            <div className="live-earth-timeline-head">
              <span>
                <Clock3 size={14} /> {formatUtc(selectedTime)}
              </span>
              <strong>{formatLocal(selectedTime)}</strong>
            </div>

            <input
              type="range"
              min="0"
              max={frames.length - 1}
              step="1"
              value={frameIndex}
              onChange={(event) => {
                setPlaying(false);
                setFrameIndex(Number(event.target.value));
              }}
              aria-label="Satellite timeline"
            />

            <div className="live-earth-timeline-labels">
              <span>{formatUtc(frames[0])}</span>
              <span>10 min/frame</span>
              <span>{formatUtc(frames[frames.length - 1])}</span>
            </div>

            <div className="live-earth-play-row">
              <button
                type="button"
                className="primary-button live-earth-play"
                onClick={() => setPlaying((value) => !value)}
              >
                {playing ? <Square size={15} /> : <Play size={15} />}
                {playing ? "Stop playback" : "Play last 2 hours"}
              </button>
              <span>
                Frames are requested on demand from the public satellite tile
                service.
              </span>
            </div>
          </div>
        </section>

        <aside className="live-earth-side-column">
          <section className="panel live-earth-control-panel">
            <div className="live-earth-section-title">
              <Layers3 size={17} />
              <span>Satellite layers</span>
            </div>

            <div className="live-earth-layer-list">
              {Object.entries(SATELLITE_LAYERS).map(([key, item]) => (
                <button
                  key={key}
                  type="button"
                  className={
                    key === layerKey
                      ? "live-earth-layer active"
                      : "live-earth-layer"
                  }
                  onClick={() => {
                    setPlaying(false);
                    setLayerKey(key);
                  }}
                >
                  <span className="live-earth-layer-icon">
                    <Activity size={16} />
                  </span>
                  <span>
                    <strong>{item.label}</strong>
                    <small>{item.description}</small>
                  </span>
                </button>
              ))}
            </div>
          </section>

          <section className="panel live-earth-status-panel">
            <div className="live-earth-section-title">
              <RadioTower size={17} />
              <span>Data trust</span>
            </div>

            <div className="live-earth-stat-grid">
              <div>
                <span>Source</span>
                <strong>NASA GIBS</strong>
              </div>
              <div>
                <span>Satellite</span>
                <strong>Himawari-9</strong>
              </div>
              <div>
                <span>Instrument</span>
                <strong>AHI</strong>
              </div>
              <div>
                <span>Cadence</span>
                <strong>10 min</strong>
              </div>
            </div>

            <div className="live-earth-trust-note">
              <strong>What “near-real-time” means</strong>
              <p>
                Satellite observations are processed before publication. This
                screen intentionally labels the imagery NRT rather than claiming
                zero-latency live video.
              </p>
            </div>
          </section>

          <section className="panel live-earth-links-panel">
            <div className="live-earth-section-title">
              <Satellite size={17} />
              <span>Official sources</span>
            </div>

            <a
              href="https://worldview.earthdata.nasa.gov/"
              target="_blank"
              rel="noreferrer"
              className="live-earth-source-link"
            >
              <span>NASA Worldview</span>
              <ExternalLink size={14} />
            </a>

            <a
              href="https://www.mosdac.gov.in/mosdac-live"
              target="_blank"
              rel="noreferrer"
              className="live-earth-source-link"
            >
              <span>ISRO MOSDAC LIVE</span>
              <ExternalLink size={14} />
            </a>
          </section>
        </aside>
      </div>

      <div className="note-box live-earth-note-box">
        <strong>Next integration:</strong> connect this satellite layer to
        Disaster AI India so a detected weather/disaster event can feed into
        the existing impact assessment, resource prediction, OR-Tools
        allocation and route-planning pipeline.
      </div>
    </div>
  );
}
