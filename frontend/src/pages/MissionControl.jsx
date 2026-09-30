import { useEffect, useState } from "react";
import { apiFetch } from "../api";
import { PageHeader, RecordPicker, StatusBadge, ErrorBlock } from "../components/Common";
import { useAuth } from "../auth/AuthContext";

const statuses = ["ASSIGNED", "EN_ROUTE", "ON_SITE", "COMPLETED", "CANCELLED"];

export default function MissionControl() {
  const { user } = useAuth();
  const canAssign = user?.role === "ADMIN" || user?.role === "RELIEF_COORDINATOR";
  const [rowId, setRowId] = useState(0);
  const [name, setName] = useState("Emergency Relief Mission");
  const [rescue, setRescue] = useState(1);
  const [medical, setMedical] = useState(1);
  const [logistics, setLogistics] = useState(1);
  const [vehicles, setVehicles] = useState(1);
  const [personnel, setPersonnel] = useState(10);
  const [notes, setNotes] = useState("");
  const [fieldTeams, setFieldTeams] = useState([]);
  const [assignedTo, setAssignedTo] = useState("");
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    setError("");
    try {
      const data = await apiFetch("/missions");
      setMissions(data.missions || []);
    } catch (e) {
      setError(e.message);
    }
  }

  useEffect(() => {
    load();
    if (canAssign) {
      apiFetch("/auth/field-teams")
        .then((data) => setFieldTeams(data.users || []))
        .catch(() => setFieldTeams([]));
    }
  }, [canAssign]);

  async function create(event) {
    event.preventDefault();
    setLoading(true); setError("");
    try {
      await apiFetch("/missions", {
        method: "POST",
        body: JSON.stringify({
          row_id: Number(rowId),
          mission_name: name,
          rescue_teams: Number(rescue),
          medical_teams: Number(medical),
          logistics_teams: Number(logistics),
          vehicles: Number(vehicles),
          personnel: Number(personnel),
          assigned_to_user_id: assignedTo ? Number(assignedTo) : null,
          notes,
        }),
      });
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function updateStatus(id, status) {
    try {
      await apiFetch(`/missions/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status, note: "Updated from secure command dashboard" }),
      });
      await load();
    } catch (e) {
      setError(e.message);
    }
  }

  return (
    <div>
      <PageHeader
        title={user?.role === "FIELD_TEAM" ? "My Field Missions" : "Mission Assignment & Field Team Tracking"}
        subtitle={user?.role === "FIELD_TEAM" ? "View missions assigned to your account and update field status." : "Assign missions to authorized field-team users and track progress from dispatch to completion."}
      />

      {canAssign && (
        <>
          <RecordPicker rowId={rowId} setRowId={setRowId} />
          <form className="mission-form" onSubmit={create}>
            <label>Mission name<input value={name} onChange={(e) => setName(e.target.value)} required /></label>
            <label>Assign field team
              <select value={assignedTo} onChange={(e) => setAssignedTo(e.target.value)}>
                <option value="">Unassigned</option>
                {fieldTeams.map((team) => <option key={team.user_id} value={team.user_id}>{team.name} · {team.region}</option>)}
              </select>
            </label>
            <label>Rescue teams<input type="number" min="0" value={rescue} onChange={(e) => setRescue(e.target.value)} /></label>
            <label>Medical teams<input type="number" min="0" value={medical} onChange={(e) => setMedical(e.target.value)} /></label>
            <label>Logistics teams<input type="number" min="0" value={logistics} onChange={(e) => setLogistics(e.target.value)} /></label>
            <label>Vehicles<input type="number" min="0" value={vehicles} onChange={(e) => setVehicles(e.target.value)} /></label>
            <label>Personnel<input type="number" min="0" value={personnel} onChange={(e) => setPersonnel(e.target.value)} /></label>
            <label className="full-field">Notes<input value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
            <button className="primary-button" disabled={loading}>{loading ? "Assigning..." : "Create Mission"}</button>
          </form>
        </>
      )}

      <ErrorBlock error={error} />

      <section className="panel">
        <div className="panel-heading">
          <div><h3>{user?.role === "FIELD_TEAM" ? "Assigned Mission Board" : "Mission Board"}</h3><p>{missions.length} missions visible to your account</p></div>
        </div>
        {missions.length ? (
          <div className="mission-board">
            {missions.map((mission) => (
              <article className="mission-card" key={mission.mission_id}>
                <div className="mission-card-head">
                  <div>
                    <strong>{mission.mission_name}</strong>
                    <span>#{mission.row_id} · {mission.disaster_type} · {mission.mission_id}</span>
                    <small>Assigned to: {mission.assigned_to_name || "Unassigned"}</small>
                  </div>
                  <StatusBadge value={mission.status} />
                </div>
                <div className="mission-stats">
                  <span>Rescue <b>{mission.rescue_teams}</b></span>
                  <span>Medical <b>{mission.medical_teams}</b></span>
                  <span>Logistics <b>{mission.logistics_teams}</b></span>
                  <span>Vehicles <b>{mission.vehicles}</b></span>
                  <span>Personnel <b>{mission.personnel}</b></span>
                </div>
                <label>Status
                  <select value={mission.status} onChange={(e) => updateStatus(mission.mission_id, e.target.value)}>
                    {statuses.map((status) => <option key={status}>{status}</option>)}
                  </select>
                </label>
              </article>
            ))}
          </div>
        ) : <div className="state-box">No missions assigned yet.</div>}
      </section>
    </div>
  );
}
