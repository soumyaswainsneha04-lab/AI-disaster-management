import { useCallback, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiFetch } from "../api";
import { useAuth } from "../auth/AuthContext";
import GoogleSignInButton from "../components/GoogleSignInButton";
import LanguageSelector from "../components/LanguageSelector";
import { useLanguage } from "../i18n/LanguageContext";

const ROLE_OPTIONS = [
  {
    value: "CITIZEN",
    label: "Citizen / Public User",
  },
  {
    value: "RELIEF_COORDINATOR",
    label: "Relief Coordinator",
  },
  {
    value: "FIELD_TEAM",
    label: "Field Team Member",
  },
];

export default function Signup() {
  const {
    googleLogin,
    login,
  } = useAuth();

  const navigate = useNavigate();
  const { t } = useLanguage();

  const [form, setForm] = useState({
    name: "",
    email: "",
    phone: "",
    organization: "",
    state: "",
    district: "",
    requested_role: "CITIZEN",
    password: "",
    confirm_password: "",
  });

  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function update(key, value) {
    setForm((current) => ({
      ...current,
      [key]: value,
    }));
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (form.password !== form.confirm_password) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);

    try {
      const data = await apiFetch("/auth/register", {
        method: "POST",
        auth: false,
        body: JSON.stringify({
          name: form.name,
          email: form.email,
          phone: form.phone,
          organization: form.organization,
          state: form.state,
          district: form.district,
          requested_role: form.requested_role,
          password: form.password,
        }),
      });

      if (
        form.requested_role === "CITIZEN" &&
        data.account_status === "APPROVED"
      ) {
        const loginResult = await login(
          form.email.trim(),
          form.password,
          false
        );

        if (loginResult.ok) {
          navigate("/", {
            replace: true,
          });
          return;
        }
      }

      setSuccess(data.message);
      update("password", "");
      update("confirm_password", "");
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  const handleGoogle = useCallback(
    async (credential) => {
      setError("");
      setSuccess("");
      setSubmitting(true);

      const result = await googleLogin(
        credential,
        {
          requestedRole: form.requested_role,
          phone: form.phone,
          organization: form.organization,
          state: form.state,
          district: form.district,
        }
      );

      setSubmitting(false);

      if (!result.ok) {
        setError(result.message);
        return;
      }

      if (result.pending) {
        setSuccess(result.message);
        return;
      }

      navigate("/", {
        replace: true,
      });
    },
    [
      googleLogin,
      form.requested_role,
      form.phone,
      form.organization,
      form.state,
      form.district,
    ]
  );

  return (
    <div className="public-auth-page">
      <div className="public-auth-card signup-card">
        <div className="auth-language-floating">
          <LanguageSelector compact />
        </div>
        <div className="public-auth-header">
          <div className="login-mobile-icon signup-icon">
            IN
          </div>
          <div>
            <h1>{t("Create Account")}</h1>
            <p>
              Create a public safety account or request authorized response access.
            </p>
          </div>
        </div>

        <div className="approval-banner">
          <strong>Citizen access is immediate</strong>
          <span>
            Citizen accounts can use public safety features immediately. Relief Coordinator and Field Team roles require administrator approval. Admin accounts cannot be self-created.
          </span>
        </div>

        {error && (
          <div className="login-error">{error}</div>
        )}

        {success && (
          <div className="signup-success">
            <strong>{form.requested_role === "CITIZEN" ? "Account created" : "Access request submitted"}</strong>
            <span>{success}</span>
            <Link to="/login">Go to sign in</Link>
          </div>
        )}

        {!success && (
          <>
            <form
              className="signup-form"
              onSubmit={submit}
            >
              <label>
                Full name
                <input
                  value={form.name}
                  onChange={(event) =>
                    update("name", event.target.value)
                  }
                  placeholder="Your full name"
                  required
                />
              </label>

              <label>
                Email
                <input
                  type="email"
                  value={form.email}
                  onChange={(event) =>
                    update("email", event.target.value)
                  }
                  placeholder="name@gmail.com"
                  required
                />
              </label>

              <label>
                Phone number
                <input
                  value={form.phone}
                  onChange={(event) =>
                    update("phone", event.target.value)
                  }
                  placeholder="+91 ..."
                />
              </label>

              <label>
                Organization
                <input
                  value={form.organization}
                  onChange={(event) =>
                    update(
                      "organization",
                      event.target.value
                    )
                  }
                  placeholder="Government / NGO / Organization"
                />
              </label>

              <label>
                State
                <input
                  value={form.state}
                  onChange={(event) =>
                    update("state", event.target.value)
                  }
                  placeholder="Odisha"
                />
              </label>

              <label>
                District
                <input
                  value={form.district}
                  onChange={(event) =>
                    update("district", event.target.value)
                  }
                  placeholder="Khordha"
                />
              </label>

              <label className="signup-role">
                Account type
                <select
                  value={form.requested_role}
                  onChange={(event) =>
                    update(
                      "requested_role",
                      event.target.value
                    )
                  }
                >
                  {ROLE_OPTIONS.map((role) => (
                    <option
                      key={role.value}
                      value={role.value}
                    >
                      {role.label}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Password
                <input
                  type="password"
                  minLength={8}
                  value={form.password}
                  onChange={(event) =>
                    update("password", event.target.value)
                  }
                  placeholder="At least 8 characters"
                  required
                />
              </label>

              <label>
                Confirm password
                <input
                  type="password"
                  minLength={8}
                  value={form.confirm_password}
                  onChange={(event) =>
                    update(
                      "confirm_password",
                      event.target.value
                    )
                  }
                  placeholder="Re-enter password"
                  required
                />
              </label>

              <button
                className="login-submit signup-submit"
                type="submit"
                disabled={submitting}
              >
                {submitting
                  ? "Submitting request..."
                  : "Create Account"}
              </button>
            </form>

            <div className="auth-divider">
              <span>OR SIGN UP WITH GOOGLE</span>
            </div>

            <p className="google-signup-help">
              Choose your account type above first. Google will provide your verified name and email.
            </p>

            <GoogleSignInButton
              onCredential={handleGoogle}
              text="signup_with"
            />
          </>
        )}

        <div className="signup-prompt">
          <span>Already have an account?</span>
          <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
