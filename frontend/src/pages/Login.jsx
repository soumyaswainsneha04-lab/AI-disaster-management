import { useCallback, useState } from "react";
import {
  Link,
  Navigate,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import GoogleSignInButton from "../components/GoogleSignInButton";
import LanguageSelector from "../components/LanguageSelector";
import { useLanguage } from "../i18n/LanguageContext";

export default function Login() {
  const {
    login,
    googleLogin,
    isAuthenticated,
    loading,
  } = useAuth();

  const { t } = useLanguage();

  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(false);
  const [showPassword, setShowPassword] =
    useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (!loading && isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setInfo("");
    setSubmitting(true);

    const result = await login(
      email.trim(),
      password,
      remember
    );

    if (!result.ok) {
      setError(result.message);
      setSubmitting(false);
      return;
    }

    navigate("/", {
      replace: true,
    });
  }

  const handleGoogle = useCallback(
    async (credential) => {
      setError("");
      setInfo("");
      setSubmitting(true);

      const result = await googleLogin(
        credential,
        { remember }
      );

      setSubmitting(false);

      if (!result.ok) {
        setError(result.message);
        return;
      }

      if (result.pending) {
        setInfo(result.message);
        return;
      }

      navigate("/", {
        replace: true,
      });
    },
    [googleLogin, remember, navigate, location.state]
  );

  return (
    <div className="login-page">
      <section className="login-hero">
        <div className="login-brand">
          <img
            src="/pwa-192x192.png"
            alt="Disaster AI India"
            className="brand-logo-img"
          />

          <div>
            <strong data-no-translate>
              Disaster AI India
            </strong>
            <span>
              {t("India Emergency Response Intelligence Platform")}
            </span>
          </div>
        </div>

        <div className="login-hero-copy">
          <span className="login-kicker">
            {t("SECURE EMERGENCY RESPONSE PLATFORM")}
          </span>

          <h1>
            {t(
              "Disaster awareness and response support for people and emergency teams across India."
            )}
          </h1>

          <p>
            {t(
              "Citizens can check nearby disaster conditions and safety guidance. Authorized response teams receive additional operational tools."
            )}
          </p>

          <div className="login-stat-grid">
            <div>
              <strong>5</strong>
              <span>{t("Disaster types")}</span>
            </div>
            <div>
              <strong>{t("India")}</strong>
              <span>{t("Operational scope")}</span>
            </div>
            <div>
              <strong>RBAC</strong>
              <span>{t("Role-based access")}</span>
            </div>
          </div>
        </div>

        <p className="login-hero-note">
          {t(
            "Academic emergency-response application · Citizen accounts are available to the public"
          )}
        </p>
      </section>

      <section className="login-form-section">
        <div className="auth-language-floating">
          <LanguageSelector compact />
        </div>

        <form className="login-card" onSubmit={submit}>
          <div className="login-heading">
            <img
              src="/pwa-192x192.png"
              alt="Disaster AI India"
              className="brand-logo-img"
            />

            <div>
              <h2 data-no-translate>Disaster AI India</h2>
              <p>{t("Emergency Response Intelligence Platform")}</p>
            </div>
          </div>

          {error && (
            <div className="login-error">{error}</div>
          )}

          {info && (
            <div className="login-info">{info}</div>
          )}

          <label className="login-label">
            {t("Email")}
            <input
              className="login-input"
              type="email"
              value={email}
              onChange={(event) =>
                setEmail(event.target.value)
              }
              autoComplete="username"
              placeholder="name@gmail.com"
              required
            />
          </label>

          <label className="login-label">
            {t("Password")}
            <div className="password-wrap">
              <input
                className="login-input"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) =>
                  setPassword(event.target.value)
                }
                autoComplete="current-password"
                placeholder={t("Enter your password")}
                minLength={8}
                required
              />

              <button
                type="button"
                onClick={() =>
                  setShowPassword((value) => !value)
                }
              >
                {showPassword ? t("Hide") : t("Show")}
              </button>
            </div>
          </label>

          <div className="login-options">
            <label className="remember-check">
              <input
                type="checkbox"
                checked={remember}
                onChange={(event) =>
                  setRemember(event.target.checked)
                }
              />
              <span>{t("Remember this device")}</span>
            </label>

            <Link
              className="forgot-link"
              to="/forgot-password"
            >
              {t("Forgot password?")}
            </Link>
          </div>

          <button
            className="login-submit"
            type="submit"
            disabled={submitting || loading}
          >
            {submitting
              ? t("Signing in securely...")
              : t("Sign in")}
          </button>

          <div className="auth-divider">
            <span>{t("OR")}</span>
          </div>

          <GoogleSignInButton
            onCredential={handleGoogle}
          />

          <Link to="/safety" className="guest-access-button">
            {t("Continue as Guest — Check My Safety")}
          </Link>

          <div className="signup-prompt">
            <span>{t("Don't have an account?")}</span>
            <Link to="/signup">{t("Create Account")}</Link>
          </div>

          <div className="secure-login-note">
            <strong>{t("Secure account access")}</strong>
            <span>
              {t(
                "Personal Gmail, government, NGO and organization email addresses are supported. Operational access begins only after administrator approval."
              )}
            </span>
          </div>
        </form>
      </section>
    </div>
  );
}