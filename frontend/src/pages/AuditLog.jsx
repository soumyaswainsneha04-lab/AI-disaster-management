import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import { PageHeader } from "../components/Common";

export default function AuditLog() {
  const [logs, setLogs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/admin/audit-logs?limit=200")
      .then((data) => setLogs(data.logs || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <PageHeader title="Audit Log" subtitle="Security and operational activity recorded by the backend." />
      {error && <div className="state-box error-box">{error}</div>}
      {loading ? <div className="state-box">Loading audit activity...</div> : (
        <section className="panel">
          <div className="table-container">
            <table className="data-table audit-table">
              <thead><tr><th>Time</th><th>User</th><th>Role</th><th>Action</th><th>Entity</th><th>Details</th></tr></thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.audit_id}>
                    <td>{new Date(log.timestamp).toLocaleString()}</td>
                    <td>{log.email || "System"}</td>
                    <td>{log.role || "—"}</td>
                    <td><strong>{String(log.action).replaceAll("_", " ")}</strong></td>
                    <td>{log.entity_type ? `${log.entity_type}${log.entity_id ? ` #${log.entity_id}` : ""}` : "—"}</td>
                    <td><code>{JSON.stringify(log.details || {})}</code></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
