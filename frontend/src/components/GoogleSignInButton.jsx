import { useEffect, useRef, useState } from "react";

const SCRIPT_ID = "google-identity-services";

function ensureGoogleScript() {
  return new Promise((resolve, reject) => {
    if (window.google?.accounts?.id) {
      resolve(window.google);
      return;
    }

    const existing = document.getElementById(SCRIPT_ID);
    if (existing) {
      existing.addEventListener("load", () => resolve(window.google), {
        once: true,
      });
      existing.addEventListener("error", reject, { once: true });
      return;
    }

    const script = document.createElement("script");
    script.id = SCRIPT_ID;
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.onload = () => resolve(window.google);
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

export default function GoogleSignInButton({
  onCredential,
  text = "signin_with",
}) {
  const containerRef = useRef(null);
  const [error, setError] = useState("");
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID || "";

  useEffect(() => {
    let cancelled = false;

    if (!clientId) {
      setError("Google sign-in is not configured.");
      return undefined;
    }

    ensureGoogleScript()
      .then(() => {
        if (cancelled || !containerRef.current) return;

        window.google.accounts.id.initialize({
          client_id: clientId,
          callback: (response) => {
            if (response?.credential) {
              onCredential(response.credential);
            }
          },
        });

        containerRef.current.innerHTML = "";

        window.google.accounts.id.renderButton(
          containerRef.current,
          {
            type: "standard",
            theme: "outline",
            size: "large",
            text,
            shape: "rectangular",
            width: Math.min(
              containerRef.current.clientWidth || 380,
              400
            ),
          }
        );
      })
      .catch(() => {
        if (!cancelled) {
          setError("Unable to load Google sign-in.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [clientId, onCredential, text]);

  if (!clientId) {
    return (
      <div className="google-not-configured">
        Google sign-in can be enabled with your Google OAuth Client ID.
      </div>
    );
  }

  return (
    <div>
      <div className="google-button-host" ref={containerRef} />
      {error && <div className="google-error">{error}</div>}
    </div>
  );
}
