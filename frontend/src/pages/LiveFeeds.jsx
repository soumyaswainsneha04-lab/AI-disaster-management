import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import {
  PageHeader,
  StatusBadge,
  ErrorBlock,
  LoadingBlock,
  DataContextStrip,
} from "../components/Common";

function formatEventTime(value) {
  if (value === null || value === undefined || value === "") return "";
  if (typeof value === "number") {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
}

export default function LiveFeeds() {
  const [status, setStatus] = useState(null);
  const [source, setSource] = useState("USGS");
  const [events, setEvents] = useState([]);
  const [filterNote, setFilterNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  useEffect(() => {
    apiFetch("/feeds/status")
      .then(setStatus)
      .catch((err) => setError(err.message));
  }, []);

  async function fetchLive(which) {
    setSource(which);
    setLoading(true);
    setError("");
    setEvents([]);
    setFilterNote("");

    try {
      const data = await apiFetch(
        which === "USGS" ? "/feeds/usgs?limit=30" : "/feeds/gdacs?limit=30"
      );
      setEvents(data.events || []);
      setFilterNote(data.filter || "India-only filter");
      setLastUpdated(new Date().toISOString());
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <PageHeader
        title="India Live Disaster Feeds"
        subtitle="USGS and GDACS results are restricted to India instead of the wider rectangular map region."
      />

      <DataContextStrip
        mode="LIVE DATA"
        source={source === "USGS" ? "USGS public earthquake feed" : "GDACS public disaster feed"}
        updatedAt={lastUpdated}
        status="India-filtered"
      />

      {status && (
        <div className="feed-status-grid">
          {Object.entries(status)
            .filter(([, value]) => typeof value === "object")
            .map(([key, value]) => (
              <div className="feed-status-card" key={key}>
                <span>{key.replaceAll("_", " ")}</span>
                <StatusBadge value={value.status} />
                <small>{value.source || value.note}</small>
              </div>
            ))}
        </div>
      )}

      <div className="feed-actions">
        <button className="primary-button" onClick={() => fetchLive("USGS")}>
          Load India USGS Earthquakes
        </button>
        <button className="primary-button" onClick={() => fetchLive("GDACS")}>
          Load India GDACS Events
        </button>
      </div>

      <ErrorBlock error={error} onRetry={() => fetchLive(source)} />
      {loading && (
        <LoadingBlock text={`Loading India-only ${source} events...`} />
      )}

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>{source} · India</h3>
            <p>
              Events outside the India boundary are removed before they reach
              this screen.
            </p>
          </div>
          {filterNote && <span className="india-filter-pill">{filterNote}</span>}
        </div>

        {events.length ? (
          <div className="live-event-list">
            {events.map((event, index) => (
              <article className="live-event-card" key={event.id || event.link || index}>
                <div className="live-event-main">
                  <strong>{event.place || event.title || "India event"}</strong>
                  <span>
                    {event.magnitude != null ? `Magnitude ${event.magnitude}` : ""}
                    {event.depth_km != null ? ` · Depth ${event.depth_km} km` : ""}
                  </span>
                  <small>{formatEventTime(event.published || event.time)}</small>
                </div>

                {event.latitude != null && event.longitude != null && (
                  <div className="live-coordinate-chip">
                    {Number(event.latitude).toFixed(3)}, {Number(event.longitude).toFixed(3)}
                  </div>
                )}
              </article>
            ))}
          </div>
        ) : (
          <div className="state-box">
            No India event loaded yet, or the current public feed has no event
            that passes the India-only filter.
          </div>
        )}
      </section>
    </div>
  );
}
