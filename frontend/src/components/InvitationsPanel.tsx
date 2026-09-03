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
  const [wlError, setWlError] = useState<string | null>(null);

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
      setWlError(null);
    } catch (e) {
      setWlError(e instanceof Error ? e.message : String(e));
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
      // correo — reusa la activa, pero decide sobre datos frescos: `items` del
      // state puede estar vacío (aún no cargó) o stale (una activa cacheada ya
      // revocada), y en ambos casos duplicaríamos o nos saltaríamos el create.
      // ponytail: check-then-act client-side; ventana de carrera solo con dos admins simultáneos — endpoint atómico si algún día importa
      const fresh = await api.listInvitations();
      const rowEmail = row.email.toLowerCase();
      const existing = fresh.find(
        (i) => i.email?.toLowerCase() === rowEmail && i.state === "active",
      );
      if (!existing) {
        await api.createInvitation({ email: row.email, note: "waitlist" });
      }
      await api.markWaitlistInvited(row.id);
    } catch (e) {
      setWlError(e instanceof Error ? e.message : String(e));
    } finally {
      await reloadAll();
      setInvitingId(null);
    }
  }

  return (
    <section>
      <p className="k-cap k-cap--rule">{t("settings.invitations.section")}</p>
      <p className="k-note">{t("settings.invitations.help")}</p>

      {error && <p className="k-error" role="alert">{error}</p>}

      <form onSubmit={onCreate}>
        <label className="k-field">
          <span className="k-field__label">{t("settings.invitations.emailLabel")}</span>
          <input
            className="k-field__input"
            type="email"
            placeholder={t("settings.invitations.emailPlaceholder")}
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            disabled={creating}
          />
        </label>

        <label className="k-field">
          <span className="k-field__label">{t("settings.invitations.noteLabel")}</span>
          <input
            className="k-field__input"
            type="text"
            maxLength={255}
            placeholder={t("settings.invitations.notePlaceholder")}
            value={newNote}
            onChange={(e) => setNewNote(e.target.value)}
            disabled={creating}
          />
        </label>

        <div className="k-wrap">
          <button type="submit" className="k-btn" disabled={creating} aria-busy={creating}>
            {creating ? t("settings.invitations.creating") : t("settings.invitations.createBtn")}
          </button>
        </div>
      </form>

      {loading ? (
        <span className="k-spinner" role="status" aria-label={t("common.loading")} />
      ) : items.length === 0 ? (
        <p className="k-note">{t("settings.invitations.empty")}</p>
      ) : (
        <ul>
          {items.map((inv) => (
            <li key={inv.id}>
              {/* La caja, el radio y el atenuado que este panel llevaba en
                  `style={{}}` son la fila con caja del átomo 4, y «revocada»
                  es su estado bloqueado. */}
              <div
                className="k-row k-row--boxed k-row--quiet"
                data-state={inv.state === "active" ? undefined : "locked"}
              >
                <span className="k-row__title">
                  {inv.email ?? t("settings.invitations.anyEmail")}
                </span>
                <span className="k-row__meta">
                  {t(`settings.invitations.state.${inv.state}`)}
                </span>
                {inv.note && <span className="k-row__sub">{inv.note}</span>}
                <span className="k-row__sub">{inv.share_url}</span>
                {inv.state === "active" && (
                  <span className="k-wrap">
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
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      <p className="k-cap k-cap--rule">{t("settings.waitlist.title")}</p>

      {wlError && <p className="k-error" role="alert">{wlError}</p>}

      {waitlistLoading ? (
        <span className="k-spinner" role="status" aria-label={t("common.loading")} />
      ) : waitlist.length === 0 ? (
        <p className="k-note">{t("settings.waitlist.empty")}</p>
      ) : (
        <ul>
          {waitlist.map((row) => (
            <li key={row.id}>
              <div
                className="k-row k-row--boxed k-row--quiet"
                data-state={row.invited_at ? "locked" : undefined}
              >
                <span className="k-row__title">{row.email}</span>
                <span className="k-row__meta">
                  {new Date(row.created_at).toLocaleDateString()}
                </span>
                {row.invited_at ? (
                  <span className="k-row__sub">{t("settings.waitlist.invited")}</span>
                ) : (
                  <span className="k-wrap">
                    <button
                      type="button"
                      className="k-btn k-btn--ghost"
                      disabled={invitingId === row.id}
                      aria-busy={invitingId === row.id}
                      onClick={() => onInviteFromWaitlist(row)}
                    >
                      {t("settings.waitlist.invite")}
                    </button>
                  </span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
