import { useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../api";

export default function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    setSubmitting(true);

    try {
      const data = await apiFetch(
        "/auth/password-reset-request",
        {
          method: "POST",
          auth: false,
          body: JSON.stringify({ email }),
        }
      );
      setMessage(data.message);
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="public-auth-page">
      <form
        className="public-auth-card forgot-card"
        onSubmit={submit}
      >
        <div className="public-auth-header">
          <div className="login-mobile-icon signup-icon">
            IN
          </div>
          <div>
            <h1>Forgot Password</h1>
            <p>Request help restoring your account.</p>
          </div>
        </div>

        <div className="approval-banner">
          <strong>Internal recovery workflow</strong>
          <span>
            For this emergency-response system, password
            reset requests are reviewed by an administrator.
          </span>
        </div>

        {error && (
          <div className="login-error">{error}</div>
        )}

        {message && (
          <div className="signup-success">
            <span>{message}</span>
          </div>
        )}

        <label className="login-label">
          Account email
          <input
            className="login-input"
            type="email"
            value={email}
            onChange={(event) =>
              setEmail(event.target.value)
            }
            placeholder="name@gmail.com"
            required
          />
        </label>

        <button
          className="login-submit"
          type="submit"
          disabled={submitting}
        >
          {submitting
            ? "Sending request..."
            : "Request Password Reset"}
        </button>

        <div className="signup-prompt">
          <Link to="/login">Back to sign in</Link>
        </div>
      </form>
    </div>
  );
}
