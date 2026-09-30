import { useCallback, useEffect, useRef, useState } from "react";
import {
  Bell,
  Check,
  CheckCheck,
  ExternalLink,
  RefreshCw,
  X,
} from "lucide-react";
import { apiFetch } from "../api";

const REFRESH_INTERVAL_MS = 30_000;

function formatAlertTime(value) {
  if (!value) return "Time unavailable";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}

function severityClass(value) {
  const severity = String(value || "MODERATE").toLowerCase();
  return `notification-severity-${severity}`;
}

export default function NotificationBell({ compact = false }) {
  const [alerts, setAlerts] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const shellRef = useRef(null);

  const loadAlerts = useCallback(async (silent = false) => {
    if (!silent) {
      setLoading(true);
    }

    try {
      const data = await apiFetch("/alerts?limit=20");

      setAlerts(Array.isArray(data?.alerts) ? data.alerts : []);
      setUnreadCount(Number(data?.unread_count || 0));
      setError("");
    } catch (err) {
      if (!silent) {
        setError(err.message || "Unable to load disaster alerts.");
      }
    } finally {
      if (!silent) {
        setLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    loadAlerts();

    const interval = window.setInterval(() => {
      loadAlerts(true);
    }, REFRESH_INTERVAL_MS);

    const handleFocus = () => {
      loadAlerts(true);
    };

    window.addEventListener("focus", handleFocus);

    return () => {
      window.clearInterval(interval);
      window.removeEventListener("focus", handleFocus);
    };
  }, [loadAlerts]);

  useEffect(() => {
    if (!open) return undefined;

    function handleOutsideClick(event) {
      if (!shellRef.current?.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
    };
  }, [open]);

  async function markRead(alertId) {
    const current = alerts.find(
      (alert) => String(alert.alert_id) === String(alertId)
    );

    if (!current || current.read) {
      return true;
    }

    try {
      await apiFetch(
        `/alerts/${encodeURIComponent(alertId)}/read`,
        {
          method: "POST",
        }
      );

      setAlerts((currentAlerts) =>
        currentAlerts.map((alert) =>
          String(alert.alert_id) === String(alertId)
            ? { ...alert, read: true }
            : alert
        )
      );

      setUnreadCount((count) => Math.max(0, count - 1));
      return true;
    } catch (err) {
      setError(err.message || "Unable to mark the alert as read.");
      return false;
    }
  }

  async function markAllRead() {
    if (!unreadCount) return;

    try {
      await apiFetch("/alerts/read-all", {
        method: "POST",
      });

      setAlerts((currentAlerts) =>
        currentAlerts.map((alert) => ({
          ...alert,
          read: true,
        }))
      );
      setUnreadCount(0);
      setError("");
    } catch (err) {
      setError(err.message || "Unable to mark alerts as read.");
    }
  }

  async function checkNow() {
    setRefreshing(true);
    setError("");

    try {
      await apiFetch("/alerts/check", {
        method: "POST",
      });
      await loadAlerts(true);
    } catch (err) {
      setError(err.message || "Unable to check live disaster feeds.");
    } finally {
      setRefreshing(false);
    }
  }

  async function openSource(alert) {
    if (!alert.read) {
      await markRead(alert.alert_id);
    }

    if (alert.external_link) {
      window.open(
        alert.external_link,
        "_blank",
        "noopener,noreferrer"
      );
    }
  }

  function togglePanel() {
    const next = !open;
    setOpen(next);

    if (next) {
      loadAlerts(true);
    }
  }

  return (
    <div
      ref={shellRef}
      className={`notification-shell ${
        compact ? "notification-shell-compact" : ""
      }`}
    >
      <button
        type="button"
        className="notification-button"
        onClick={togglePanel}
        aria-label={
          unreadCount
            ? `${unreadCount} unread disaster alerts`
            : "Disaster alerts"
        }
        aria-expanded={open}
        title="Disaster alerts"
      >
        <Bell size={19} strokeWidth={2} />

        {unreadCount > 0 && (
          <span className="notification-count">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <section
          className="notification-panel"
          aria-label="Disaster alerts panel"
        >
          <div className="notification-panel-header">
            <div>
              <strong>Disaster Alerts</strong>
              <span>
                {unreadCount
                  ? `${unreadCount} unread`
                  : "No unread alerts"}
              </span>
            </div>

            <div className="notification-header-actions">
              <button
                type="button"
                className="notification-icon-action"
                onClick={checkNow}
                disabled={refreshing}
                aria-label="Check live disaster feeds"
                title="Check live disaster feeds"
              >
                <RefreshCw
                  size={16}
                  className={refreshing ? "notification-spin" : ""}
                />
              </button>

              <button
                type="button"
                className="notification-icon-action"
                onClick={() => setOpen(false)}
                aria-label="Close disaster alerts"
                title="Close"
              >
                <X size={16} />
              </button>
            </div>
          </div>

          {unreadCount > 0 && (
            <button
              type="button"
              className="notification-mark-all"
              onClick={markAllRead}
            >
              <CheckCheck size={15} />
              Mark all as read
            </button>
          )}

          {error && (
            <div className="notification-error">
              {error}
            </div>
          )}

          {loading ? (
            <div className="notification-empty">
              Loading disaster alerts…
            </div>
          ) : alerts.length === 0 ? (
            <div className="notification-empty">
              <Bell size={22} />
              <strong>No matching disaster alerts</strong>
              <span>
                Alerts appear here when a configured live-feed event
                matches your saved location and alert preferences.
              </span>
            </div>
          ) : (
            <div className="notification-list">
              {alerts.map((alert) => (
                <article
                  key={alert.alert_id}
                  className={`notification-card ${
                    alert.read ? "" : "notification-card-unread"
                  }`}
                >
                  <div className="notification-card-top">
                    <span
                      className={`notification-severity ${severityClass(
                        alert.severity
                      )}`}
                    >
                      {String(alert.severity || "MODERATE").toUpperCase()}
                    </span>

                    <span className="notification-source">
                      {alert.source || "LIVE FEED"}
                    </span>
                  </div>

                  <h4>{alert.title || "Disaster alert"}</h4>

                  <p>
                    {alert.message ||
                      "A disaster event matched your configured alert criteria."}
                  </p>

                  <div className="notification-meta">
                    <span>
                      {alert.disaster_type || "Disaster"}
                    </span>

                    {alert.distance_km !== undefined &&
                      alert.distance_km !== null && (
                        <span>
                          {Number(alert.distance_km).toFixed(1)} km away
                        </span>
                      )}

                    <span>
                      {formatAlertTime(
                        alert.event_time || alert.created_at
                      )}
                    </span>
                  </div>

                  <div className="notification-card-actions">
                    {!alert.read && (
                      <button
                        type="button"
                        className="notification-read-button"
                        onClick={() => markRead(alert.alert_id)}
                      >
                        <Check size={14} />
                        Mark read
                      </button>
                    )}

                    {alert.external_link && (
                      <button
                        type="button"
                        className="notification-source-button"
                        onClick={() => openSource(alert)}
                      >
                        <ExternalLink size={14} />
                        Open live source
                      </button>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}

          <div className="notification-disclaimer">
            Prototype in-app notifications based on public live feeds
            and saved user preferences. They are not official government
            warnings.
          </div>
        </section>
      )}
    </div>
  );
}
