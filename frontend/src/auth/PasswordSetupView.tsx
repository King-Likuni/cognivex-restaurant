import { CheckCircle2, KeyRound, LogIn } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Field, Notice, Panel } from "../components/ui";
import { apiRequest, type PasswordSetupPreview } from "../services/api";

function readToken() {
  return new URLSearchParams(window.location.search).get("token") ?? "";
}

export function PasswordSetupView() {
  const token = useMemo(() => readToken(), []);
  const [preview, setPreview] = useState<PasswordSetupPreview | null>(null);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isComplete, setIsComplete] = useState(false);

  const loadPreview = useCallback(async () => {
    if (!token) {
      setError("Password setup link is missing a token");
      return;
    }
    setError(null);
    try {
      const nextPreview = await apiRequest<PasswordSetupPreview>(
        `/api/v1/auth/password-setup/${encodeURIComponent(token)}`,
      );
      setPreview(nextPreview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Password setup link is invalid");
    }
  }, [token]);

  useEffect(() => {
    void loadPreview();
  }, [loadPreview]);

  async function submitPassword(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    setIsSubmitting(true);
    try {
      await apiRequest("/api/v1/auth/password-setup/confirm", {
        method: "POST",
        body: { token, password },
      });
      setIsComplete(true);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not set password");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="password-setup-page">
      <Panel title="Set Password">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {isComplete ? (
          <div className="password-setup-complete">
            <CheckCircle2 size={38} />
            <strong>Password updated</strong>
            <a className="primary-action" href="/">
              <LogIn size={18} />
              Sign in
            </a>
          </div>
        ) : (
          <form className="staff-form" onSubmit={submitPassword}>
            {preview ? (
              <Notice>
                Setting password for {preview.first_name} {preview.last_name} ({preview.email})
              </Notice>
            ) : null}
            <Field label="New password">
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={8}
                required
              />
            </Field>
            <Field label="Confirm password">
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={8}
                required
              />
            </Field>
            <button className="primary-action" type="submit" disabled={isSubmitting || !preview}>
              <KeyRound size={18} />
              {isSubmitting ? "Saving password" : "Set password"}
            </button>
          </form>
        )}
      </Panel>
    </main>
  );
}
