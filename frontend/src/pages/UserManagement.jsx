import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../api";
import {
  PageHeader,
  StatusBadge,
} from "../components/Common";

const ROLE_OPTIONS = [
  "ADMIN",
  "CITIZEN",
  "RELIEF_COORDINATOR",
  "FIELD_TEAM",
];

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] =
    useState("RELIEF_COORDINATOR");
  const [region, setRegion] = useState("India");

  const [resetUser, setResetUser] = useState(null);
  const [resetPassword, setResetPassword] =
    useState("");

  async function load() {
    setLoading(true);
    setError("");

    try {
      const data = await apiFetch("/admin/users");
      setUsers(data.users || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  const pending = useMemo(
    () =>
      users.filter(
        (user) => user.account_status === "PENDING"
      ),
    [users]
  );

  const approved = useMemo(
    () =>
      users.filter(
        (user) => user.account_status === "APPROVED"
      ),
    [users]
  );

  const rejected = useMemo(
    () =>
      users.filter(
        (user) => user.account_status === "REJECTED"
      ),
    [users]
  );

  async function create(event) {
    event.preventDefault();
    setCreating(true);
    setError("");
    setMessage("");

    try {
      await apiFetch("/admin/users", {
        method: "POST",
        body: JSON.stringify({
          name,
          email,
          password,
          role,
          region,
        }),
      });

      setName("");
      setEmail("");
      setPassword("");
      setRole("RELIEF_COORDINATOR");
      setRegion("India");
      setMessage(
        "Authorized user account created successfully."
      );
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  }

  async function patchUser(userId, patch) {
    setError("");
    setMessage("");

    try {
      await apiFetch(`/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify(patch),
      });

      setMessage("User updated successfully.");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  async function approveUser(user) {
    await patchUser(user.user_id, {
      role: user.requested_role || "FIELD_TEAM",
      account_status: "APPROVED",
    });
  }

  async function rejectUser(user) {
    await patchUser(user.user_id, {
      account_status: "REJECTED",
    });
  }

  async function resetPasswordNow() {
    if (!resetUser || resetPassword.length < 8) {
      setError(
        "Enter a temporary password with at least 8 characters."
      );
      return;
    }

    try {
      await apiFetch(
        `/admin/users/${resetUser.user_id}/reset-password`,
        {
          method: "POST",
          body: JSON.stringify({
            new_password: resetPassword,
          }),
        }
      );

      setMessage(
        `Password reset for ${resetUser.name}.`
      );
      setResetUser(null);
      setResetPassword("");
      await load();
    } catch (err) {
      setError(err.message);
    }
  }

  function UserIdentity({ user }) {
    return (
      <div>
        <strong>{user.name}</strong>
        <small>{user.email}</small>
        {user.organization && (
          <small>{user.organization}</small>
        )}
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        title="User Management"
        subtitle="Approve account requests, assign roles and manage authorized Disaster AI India users."
      />

      {error && (
        <div className="state-box error-box">
          {error}
        </div>
      )}

      {message && (
        <div className="state-box success-box">
          {message}
        </div>
      )}

      <div className="user-summary-grid">
        <div>
          <span>Pending Approval</span>
          <strong>{pending.length}</strong>
        </div>
        <div>
          <span>Approved Users</span>
          <strong>{approved.length}</strong>
        </div>
        <div>
          <span>Rejected Requests</span>
          <strong>{rejected.length}</strong>
        </div>
      </div>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>Pending Account Requests</h3>
            <p>
              Staff access requests require review. Citizen accounts are active immediately and appear in Approved Users.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="state-box">
            Loading users...
          </div>
        ) : pending.length === 0 ? (
          <div className="state-box">
            No pending account requests.
          </div>
        ) : (
          <div className="pending-user-grid">
            {pending.map((user) => (
              <article
                className="pending-user-card"
                key={user.user_id}
              >
                <div className="pending-user-head">
                  <UserIdentity user={user} />
                  <StatusBadge value="PENDING" />
                </div>

                <div className="pending-user-details">
                  <span>
                    <small>Requested role</small>
                    <strong>
                      {String(
                        user.requested_role
                      ).replaceAll("_", " ")}
                    </strong>
                  </span>
                  <span>
                    <small>Provider</small>
                    <strong>
                      {user.auth_provider}
                    </strong>
                  </span>
                  <span>
                    <small>State</small>
                    <strong>
                      {user.state || "Not provided"}
                    </strong>
                  </span>
                  <span>
                    <small>District</small>
                    <strong>
                      {user.district || "Not provided"}
                    </strong>
                  </span>
                </div>

                <div className="pending-user-actions">
                  <button
                    className="primary-button"
                    onClick={() => approveUser(user)}
                  >
                    Approve
                  </button>

                  <button
                    className="small-button danger-button"
                    onClick={() => rejectUser(user)}
                  >
                    Reject
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>Create User Directly</h3>
            <p>
              Administrators may still create trusted staff
              accounts without the public approval workflow.
            </p>
          </div>
        </div>

        <form
          className="admin-user-form"
          onSubmit={create}
        >
          <label>
            Name
            <input
              value={name}
              onChange={(event) =>
                setName(event.target.value)
              }
              required
            />
          </label>

          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              placeholder="name@gmail.com"
              required
            />
          </label>

          <label>
            Temporary password
            <input
              type="password"
              minLength={8}
              value={password}
              onChange={(event) =>
                setPassword(event.target.value)
              }
              required
            />
          </label>

          <label>
            Role
            <select
              value={role}
              onChange={(event) =>
                setRole(event.target.value)
              }
            >
              {ROLE_OPTIONS.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>

          <label>
            Region / unit
            <input
              value={region}
              onChange={(event) =>
                setRegion(event.target.value)
              }
              required
            />
          </label>

          <button
            className="primary-button"
            disabled={creating}
          >
            {creating
              ? "Creating..."
              : "Create User"}
          </button>
        </form>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <h3>Approved Users</h3>
            <p>
              Active staff accounts with operational access.
            </p>
          </div>
        </div>

        {loading ? (
          <div className="state-box">
            Loading users...
          </div>
        ) : (
          <div className="table-container">
            <table className="data-table user-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Provider</th>
                  <th>Status</th>
                  <th>Last Login</th>
                  <th>Reset</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {approved.map((user) => (
                  <tr key={user.user_id}>
                    <td>
                      <UserIdentity user={user} />
                    </td>

                    <td>
                      <select
                        value={user.role}
                        onChange={(event) =>
                          patchUser(user.user_id, {
                            role: event.target.value,
                          })
                        }
                      >
                        {ROLE_OPTIONS.map((item) => (
                          <option key={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    </td>

                    <td>{user.auth_provider}</td>

                    <td>
                      <StatusBadge
                        value={
                          user.is_active
                            ? "ACTIVE"
                            : "INACTIVE"
                        }
                      />
                    </td>

                    <td>
                      {user.last_login_at
                        ? new Date(
                            user.last_login_at
                          ).toLocaleString()
                        : "Never"}
                    </td>

                    <td>
                      {user.reset_requested_at ? (
                        <StatusBadge
                          value="REQUESTED"
                        />
                      ) : (
                        "—"
                      )}
                    </td>

                    <td className="user-actions">
                      <button
                        className="small-button"
                        onClick={() =>
                          patchUser(user.user_id, {
                            is_active:
                              !user.is_active,
                          })
                        }
                      >
                        {user.is_active
                          ? "Disable"
                          : "Enable"}
                      </button>

                      <button
                        className="small-button"
                        onClick={() =>
                          setResetUser(user)
                        }
                      >
                        Reset Password
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {rejected.length > 0 && (
        <section className="panel">
          <div className="panel-heading">
            <div>
              <h3>Rejected Requests</h3>
              <p>
                Rejected accounts remain blocked unless an
                administrator approves them later.
              </p>
            </div>
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Requested Role</th>
                  <th>Provider</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {rejected.map((user) => (
                  <tr key={user.user_id}>
                    <td>
                      <UserIdentity user={user} />
                    </td>
                    <td>
                      {String(
                        user.requested_role
                      ).replaceAll("_", " ")}
                    </td>
                    <td>{user.auth_provider}</td>
                    <td>
                      <button
                        className="small-button"
                        onClick={() =>
                          approveUser(user)
                        }
                      >
                        Approve Instead
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {resetUser && (
        <div
          className="modal-backdrop"
          onClick={() => setResetUser(null)}
        >
          <div
            className="modal-card"
            onClick={(event) =>
              event.stopPropagation()
            }
          >
            <h3>Reset Password</h3>
            <p>
              Set a temporary password for{" "}
              <strong>{resetUser.name}</strong>.
            </p>

            <input
              type="password"
              minLength={8}
              value={resetPassword}
              onChange={(event) =>
                setResetPassword(event.target.value)
              }
              placeholder="Temporary password"
            />

            <div className="modal-actions">
              <button
                className="small-button"
                onClick={() => setResetUser(null)}
              >
                Cancel
              </button>

              <button
                className="primary-button"
                onClick={resetPasswordNow}
              >
                Reset Password
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
