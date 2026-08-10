import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { Invitation, WaitlistRow } from "../api/types";

export default function InvitationsPanel() {
  const { t } = useTranslation();
  const [items, setItems] = useState<Invitation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newEmail, setNewEmail] = useState("");
  const [newNote, setNewNote] = useState("");
  const [creating, setCreating] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const [waitlist, setWaitlist] = useState<WaitlistRow[]>([]);
  const [waitlistLoading, setWaitlistLoading] = useState(true);
  const [invitingId, setInvitingId] = useState<string | null>(null);

  async function reload() {
    setLoading(true);
    try {
      const list = await api.listInvitations();
      setItems(list);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function reloadWaitlist() {
    setWaitlistLoading(true);
    try {
      const list = await api.listWaitlist();
      setWaitlist(list);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setWaitlistLoading(false);
    }
  }

  async function reloadAll() {
    await Promise.all([reload(), reloadWaitlist()]);
  }

  useEffect(() => {
    reloadAll();
  }, []);

  async function onCreate(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    setError(null);
    try {
      await api.createInvitation({
        email: newEmail.trim().toLowerCase() || undefined,
        note: newNote.trim() || undefined,
      });
      setNewEmail("");
      setNewNote("");
      await reload();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : String(e2));
    } finally {
      setCreating(false);
    }
  }

  async function onRevoke(id: string) {
    if (!confirm(t("settings.invitations.confirmRevoke"))) return;
    try {
      await api.revokeInvitation(id);
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function copyLink(inv: Invitation) {
    try {
      await navigator.clipboard.writeText(inv.share_url);
      setCopiedId(inv.id);
      setTimeout(() => setCopiedId((c) => (c === inv.id ? null : c)), 1500);
    } catch {
      window.prompt(t("settings.invitations.copyFallback"), inv.share_url);
    }
  }

  async function onInviteFromWaitlist(row: WaitlistRow) {
    setInvitingId(row.id);
    try {
      // Si un intento anterior creó la invitación pero se cayó antes de marcar
      // la fila, un retry no debe crear una segunda invitación para el mismo
      // correo — reusa la activa ya cargada.
      const existing = items.find((i) => i.email === row.email && i.state === "active");
      if (!existing) {
        await api.createInvitation({ email: row.email, note: "waitlist" });
      }
      await api.markWaitlistInvited(row.id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      await reloadAll();
      setInvitingId(null);
    }
  }

  return (
    <section style={{ marginTop: "1.5rem" }}>
      <h2 className="k-mono" style={{ fontSize: "0.9rem", color: "var(--ink-3)" }}>
        {t("settings.invitations.section")}
      </h2>
      <p className="k-mono" style={{ color: "var(--ink-3)", marginTop: ".5rem" }}>
        {t("settings.invitations.help")}
      </p>

      {error && <div className="k-error" role="alert" style={{ marginTop: ".5rem" }}>{error}</div>}

      <form onSubmit={onCreate} style={{ marginTop: "1rem" }}>
        <label className="k-mono" style={{ display: "block" }}>
          {t("settings.invitations.emailLabel")}
        </label>
        <input
          className="snew__input"
          type="email"
          placeholder={t("settings.invitations.emailPlaceholder")}
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          disabled={creating}
        />

        <label className="k-mono" style={{ display: "block", marginTop: ".75rem" }}>
          {t("settings.invitations.noteLabel")}
        </label>
        <input
          className="snew__input"
          type="text"
          maxLength={255}
          placeholder={t("settings.invitations.notePlaceholder")}
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          disabled={creating}
        />

        <div className="snew__actions" style={{ marginTop: "1rem" }}>
          <button type="submit" className="k-btn" disabled={creating}>
            {creating ? t("settings.invitations.creating") : t("settings.invitations.createBtn")}
          </button>
        </div>
      </form>

      <div style={{ marginTop: "1.5rem" }}>
        {loading ? (
          <p className="k-mono">{t("common.loading")}</p>
        ) : items.length === 0 ? (
          <p className="k-mono" style={{ color: "var(--ink-3)" }}>
            {t("settings.invitations.empty")}
          </p>
        ) : (
          <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: ".75rem" }}>
            {items.map((inv) => (
              <li
                key={inv.id}
                style={{
                  border: "1px solid var(--ink-3)",
                  borderRadius: 4,
                  padding: ".75rem",
                  opacity: inv.state === "active" ? 1 : 0.6,
                }}
              >
                <div className="k-mono" style={{ display: "flex", justifyContent: "space-between", gap: ".5rem" }}>
                  <span>{inv.email ?? t("settings.invitations.anyEmail")}</span>
                  <span style={{ color: "var(--ink-3)" }}>
                    {t(`settings.invitations.state.${inv.state}`)}
                  </span>
                </div>
                {inv.note && (
                  <div className="k-mono" style={{ color: "var(--ink-3)", marginTop: ".25rem" }}>
                    {inv.note}
                  </div>
                )}
                <div
                  className="k-mono"
                  style={{
                    color: "var(--ink-3)",
                    marginTop: ".5rem",
                    fontSize: "0.8rem",
                    wordBreak: "break-all",
                  }}
                >
                  {inv.share_url}
                </div>
                <div className="snew__actions" style={{ marginTop: ".5rem" }}>
                  {inv.state === "active" && (
                    <>
                      <button
                        type="button"
                        className="k-btn k-btn--ghost"
                        onClick={() => copyLink(inv)}
                      >
                        {copiedId === inv.id
                          ? t("settings.invitations.copied")
                          : t("settings.invitations.copyBtn")}
                      </button>
                      <button
                        type="button"
                        className="k-btn k-btn--ghost"
                        onClick={() => onRevoke(inv.id)}
                      >
                        {t("settings.invitations.revokeBtn")}
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      <section style={{ marginTop: "2rem" }}>
        <h2 className="k-mono" style={{ fontSize: "0.9rem", color: "var(--ink-3)" }}>
          {t("settings.waitlist.title")}
        </h2>

        <div style={{ marginTop: "1rem" }}>
          {waitlistLoading ? (
            <p className="k-mono">{t("common.loading")}</p>
          ) : waitlist.length === 0 ? (
            <p className="k-mono" style={{ color: "var(--ink-3)" }}>
              {t("settings.waitlist.empty")}
            </p>
          ) : (
            <ul style={{ listStyle: "none", padding: 0, display: "grid", gap: ".75rem" }}>
              {waitlist.map((row) => (
                <li
                  key={row.id}
                  style={{
                    border: "1px solid var(--ink-3)",
                    borderRadius: 4,
                    padding: ".75rem",
                    opacity: row.invited_at ? 0.6 : 1,
                  }}
                >
                  <div className="k-mono" style={{ display: "flex", justifyContent: "space-between", gap: ".5rem" }}>
                    <span>{row.email}</span>
                    <span style={{ color: "var(--ink-3)" }}>
                      {new Date(row.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="snew__actions" style={{ marginTop: ".5rem" }}>
                    {row.invited_at ? (
                      <span className="k-mono" style={{ color: "var(--ink-3)" }}>
                        {t("settings.waitlist.invited")}
                      </span>
                    ) : (
                      <button
                        type="button"
                        className="k-btn k-btn--ghost"
                        disabled={invitingId === row.id}
                        onClick={() => onInviteFromWaitlist(row)}
                      >
                        {t("settings.waitlist.invite")}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </section>
    </section>
  );
}
