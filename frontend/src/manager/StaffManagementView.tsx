import {
  Copy,
  Eye,
  KeyRound,
  Plus,
  Power,
  PowerOff,
  RefreshCw,
  Save,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel } from "../components/ui";
import {
  apiRequest,
  type Branch,
  type PasswordSetupToken,
  type RoleName,
  type StaffInviteResponse,
  type User,
} from "../services/api";

type Props = {
  context: AppContext;
  token: string;
  branches: Branch[];
};

type StaffDraft = {
  first_name: string;
  last_name: string;
  role_name: StaffRole;
  branch_ids: string[];
};

type NewStaffForm = StaffDraft & {
  email: string;
};

type StaffRole = Exclude<RoleName, "ADMIN">;

const STAFF_ROLES: StaffRole[] = ["OWNER", "MANAGER", "CASHIER", "KITCHEN"];

const DEFAULT_NEW_STAFF: NewStaffForm = {
  email: "",
  first_name: "",
  last_name: "",
  role_name: "CASHIER",
  branch_ids: [],
};

function draftFromUser(user: User): StaffDraft {
  return {
    first_name: user.first_name ?? "",
    last_name: user.last_name ?? "",
    role_name: (user.role_name === "ADMIN" || !user.role_name ? "CASHIER" : user.role_name),
    branch_ids: user.branch_ids ?? [],
  };
}

function requiresBranchAssignment(roleName: StaffRole) {
  return roleName === "CASHIER" || roleName === "KITCHEN";
}

function workerName(user: User) {
  const name = `${user.first_name ?? ""} ${user.last_name ?? ""}`.trim();
  return name || user.email;
}

function formatTenure(createdAt: string | null) {
  if (!createdAt) {
    return "Start date unavailable";
  }
  const startedAt = new Date(createdAt);
  if (Number.isNaN(startedAt.getTime())) {
    return "Start date unavailable";
  }
  const days = Math.max(
    0,
    Math.floor((Date.now() - startedAt.getTime()) / (1000 * 60 * 60 * 24)),
  );
  if (days === 0) {
    return "Started today";
  }
  if (days === 1) {
    return "1 day with the restaurant";
  }
  if (days < 31) {
    return `${days} days with the restaurant`;
  }
  const months = Math.floor(days / 30);
  if (months < 12) {
    return `${months} month${months === 1 ? "" : "s"} with the restaurant`;
  }
  const years = Math.floor(days / 365);
  return `${years} year${years === 1 ? "" : "s"} with the restaurant`;
}

function formatStartDate(createdAt: string | null) {
  if (!createdAt) {
    return "Unknown";
  }
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function branchLabels(user: User, branches: Branch[]) {
  const labels = user.branch_assignments?.length
    ? user.branch_assignments.map((branch) => `${branch.name} (${branch.code})`)
    : user.branch_ids
        .map((branchId) => branches.find((branch) => branch.id === branchId))
        .filter((branch): branch is Branch => Boolean(branch))
        .map((branch) => `${branch.name} (${branch.code})`);
  return labels.length ? labels : ["All active branches by role"];
}

function roleSummary(roleName: RoleName | null) {
  if (roleName === "OWNER") {
    return "Full restaurant administration, staff, branches, inventory, kitchen, cashier, audit, and reports.";
  }
  if (roleName === "MANAGER") {
    return "Operational management for cashier, kitchen, inventory, and reports.";
  }
  if (roleName === "CASHIER") {
    return "Cashier operations for assigned branches only.";
  }
  if (roleName === "KITCHEN") {
    return "Kitchen board and stock alerts for assigned branches only.";
  }
  return "No operational console access.";
}

function toggleBranchId(branchIds: string[], branchId: string) {
  if (branchIds.includes(branchId)) {
    return branchIds.filter((currentBranchId) => currentBranchId !== branchId);
  }
  return [...branchIds, branchId];
}

function setupUrlFromToken(invite: PasswordSetupToken) {
  return `${window.location.origin}${invite.setup_url_path}`;
}

export function StaffManagementView({ context, token, branches }: Props) {
  const [users, setUsers] = useState<User[]>([]);
  const [drafts, setDrafts] = useState<Record<string, StaffDraft>>({});
  const [newStaff, setNewStaff] = useState<NewStaffForm>(DEFAULT_NEW_STAFF);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [savingUserId, setSavingUserId] = useState<string | null>(null);
  const [latestSetupUrl, setLatestSetupUrl] = useState<string | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);

  const activeStaffCount = useMemo(
    () => users.filter((user) => user.is_active).length,
    [users],
  );
  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId) ?? users[0] ?? null,
    [selectedUserId, users],
  );

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextUsers = await apiRequest<User[]>("/api/v1/auth/users", {
        token,
        params: { restaurant_id: context.restaurant.id },
      });
      setUsers(nextUsers);
      setDrafts(Object.fromEntries(nextUsers.map((user) => [user.id, draftFromUser(user)])));
      setSelectedUserId((current) =>
        current && nextUsers.some((user) => user.id === current)
          ? current
          : nextUsers[0]?.id ?? null,
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load staff");
    } finally {
      setIsLoading(false);
    }
  }, [context.restaurant.id, token]);

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  function updateNewStaff<K extends keyof NewStaffForm>(field: K, value: NewStaffForm[K]) {
    setNewStaff((current) => ({
      ...current,
      [field]: value,
    }));
  }

  function updateDraft<K extends keyof StaffDraft>(
    userId: string,
    field: K,
    value: StaffDraft[K],
  ) {
    setDrafts((current) => ({
      ...current,
      [userId]: {
        ...current[userId],
        [field]: value,
      },
    }));
  }

  function validateStaffPayload(roleName: StaffRole, branchIds: string[]) {
    if (requiresBranchAssignment(roleName) && branchIds.length === 0) {
      setError("Cashier and kitchen users must be assigned to at least one active branch");
      return false;
    }
    return true;
  }

  async function createStaff(event: React.FormEvent) {
    event.preventDefault();
    setNotice(null);
    setError(null);
    setLatestSetupUrl(null);
    if (!validateStaffPayload(newStaff.role_name, newStaff.branch_ids)) {
      return;
    }
    try {
      const invite = await apiRequest<StaffInviteResponse>("/api/v1/auth/users/invite", {
        method: "POST",
        token,
        body: {
          ...newStaff,
          email: newStaff.email.trim(),
          first_name: newStaff.first_name.trim(),
          last_name: newStaff.last_name.trim(),
          restaurant_id: context.restaurant.id,
        },
      });
      setLatestSetupUrl(setupUrlFromToken(invite.invite));
      setNewStaff(DEFAULT_NEW_STAFF);
      setNotice("Staff member created. Share the password setup link with them.");
      await loadUsers();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create staff member");
    }
  }

  async function patchStaff(user: User, body: Partial<StaffDraft> & { is_active?: boolean }) {
    setSavingUserId(user.id);
    setNotice(null);
    setError(null);
    try {
      await apiRequest<User>(`/api/v1/auth/users/${user.id}`, {
        method: "PATCH",
        token,
        body,
      });
      setNotice("Staff member updated");
      await loadUsers();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update staff member");
    } finally {
      setSavingUserId(null);
    }
  }

  function saveStaff(user: User) {
    const draft = drafts[user.id];
    if (!draft || !validateStaffPayload(draft.role_name, draft.branch_ids)) {
      return;
    }
    void patchStaff(user, {
      first_name: draft.first_name.trim(),
      last_name: draft.last_name.trim(),
      role_name: draft.role_name,
      branch_ids: draft.branch_ids,
    });
  }

  function toggleStaffStatus(user: User) {
    void patchStaff(user, { is_active: !user.is_active });
  }

  async function createPasswordReset(user: User) {
    setSavingUserId(user.id);
    setNotice(null);
    setError(null);
    setLatestSetupUrl(null);
    try {
      const invite = await apiRequest<PasswordSetupToken>(
        `/api/v1/auth/users/${user.id}/password-reset`,
        {
          method: "POST",
          token,
        },
      );
      setLatestSetupUrl(setupUrlFromToken(invite));
      setNotice("Password setup link created");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not create password setup link");
    } finally {
      setSavingUserId(null);
    }
  }

  async function copySetupUrl() {
    if (!latestSetupUrl) {
      return;
    }
    try {
      await navigator.clipboard.writeText(latestSetupUrl);
      setNotice("Password setup link copied");
    } catch {
      setError("Could not copy link. Select the link and copy it manually.");
    }
  }

  return (
    <div className="view-grid two-columns">
      <div className="view-stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}
        {isLoading ? <Notice>Loading staff</Notice> : null}
        {latestSetupUrl ? (
          <Panel title="Password Setup Link">
            <div className="invite-link-box">
              <input readOnly value={latestSetupUrl} />
              <button className="secondary-action" type="button" onClick={copySetupUrl}>
                <Copy size={17} />
                Copy
              </button>
            </div>
          </Panel>
        ) : null}

        <Panel title="Worker Profile">
          {selectedUser ? (
            <div className="staff-profile">
              <div className="staff-profile-header">
                <span className="profile-avatar">{workerName(selectedUser).slice(0, 2).toUpperCase()}</span>
                <div>
                  <h3>{workerName(selectedUser)}</h3>
                  <span>{selectedUser.email}</span>
                </div>
                <span className={selectedUser.is_active ? "status-pill" : "status-pill inactive"}>
                  {selectedUser.is_active ? "Active" : "Inactive"}
                </span>
              </div>
              <div className="staff-profile-grid">
                <div>
                  <span>Role</span>
                  <strong>{selectedUser.role_name ?? "Unassigned"}</strong>
                </div>
                <div>
                  <span>Started</span>
                  <strong>{formatStartDate(selectedUser.created_at)}</strong>
                </div>
                <div>
                  <span>Tenure</span>
                  <strong>{formatTenure(selectedUser.created_at)}</strong>
                </div>
              </div>
              <div className="staff-profile-section">
                <span>Branch access</span>
                <div className="branch-chip-list">
                  {branchLabels(selectedUser, branches).map((branch) => (
                    <span className="branch-chip" key={branch}>
                      {branch}
                    </span>
                  ))}
                </div>
              </div>
              <div className="staff-profile-section">
                <span>Access summary</span>
                <p>{roleSummary(selectedUser.role_name)}</p>
              </div>
            </div>
          ) : (
            <EmptyState>Select a worker to view their profile</EmptyState>
          )}
        </Panel>

        <Panel title="Add Staff">
          <form className="staff-form" onSubmit={createStaff}>
            <Field label="First name">
              <input
                value={newStaff.first_name}
                onChange={(event) => updateNewStaff("first_name", event.target.value)}
                required
              />
            </Field>
            <Field label="Last name">
              <input
                value={newStaff.last_name}
                onChange={(event) => updateNewStaff("last_name", event.target.value)}
                required
              />
            </Field>
            <Field label="Email">
              <input
                type="email"
                value={newStaff.email}
                onChange={(event) => updateNewStaff("email", event.target.value)}
                required
              />
            </Field>
            <Field label="Role">
              <select
                value={newStaff.role_name}
                onChange={(event) => updateNewStaff("role_name", event.target.value as StaffRole)}
              >
                {STAFF_ROLES.map((role) => (
                  <option key={role} value={role}>
                    {role}
                  </option>
                ))}
              </select>
            </Field>
            <fieldset className="branch-checklist">
              <legend>Branch access</legend>
              {branches.map((branch) => (
                <label key={branch.id}>
                  <input
                    type="checkbox"
                    checked={newStaff.branch_ids.includes(branch.id)}
                    onChange={() =>
                      updateNewStaff("branch_ids", toggleBranchId(newStaff.branch_ids, branch.id))
                    }
                  />
                  <span>{branch.name}</span>
                </label>
              ))}
            </fieldset>
            <button className="primary-action" type="submit">
              <Plus size={18} />
              Add staff
            </button>
          </form>
        </Panel>
      </div>

      <div className="view-stack">
        <Panel
          title="Staff"
          action={
            <button className="icon-button" type="button" onClick={loadUsers} title="Refresh">
              <RefreshCw size={17} />
            </button>
          }
        >
          <div className="toolbar-line">
            <span className="status-pill">{activeStaffCount} active</span>
            <span className="status-pill">{users.length} total</span>
          </div>

          <div className="staff-list">
            {users.map((user) => {
              const draft = drafts[user.id] ?? draftFromUser(user);
              const isSaving = savingUserId === user.id;
              return (
                <div className="staff-row" key={user.id}>
                  <div className="staff-heading">
                    <Users size={18} />
                    <div>
                      <strong>
                        {workerName(user)}
                      </strong>
                      <span>
                        {user.email} | {formatTenure(user.created_at)}
                      </span>
                    </div>
                    <span className={user.is_active ? "status-pill" : "status-pill inactive"}>
                      {user.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>

                  <div className="staff-edit-grid">
                    <Field label="First name">
                      <input
                        value={draft.first_name}
                        onChange={(event) =>
                          updateDraft(user.id, "first_name", event.target.value)
                        }
                      />
                    </Field>
                    <Field label="Last name">
                      <input
                        value={draft.last_name}
                        onChange={(event) => updateDraft(user.id, "last_name", event.target.value)}
                      />
                    </Field>
                    <Field label="Role">
                      <select
                        value={draft.role_name}
                        onChange={(event) =>
                          updateDraft(user.id, "role_name", event.target.value as StaffRole)
                        }
                      >
                        {STAFF_ROLES.map((role) => (
                          <option key={role} value={role}>
                            {role}
                          </option>
                        ))}
                      </select>
                    </Field>
                  </div>

                  <fieldset className="branch-checklist">
                    <legend>Branch access</legend>
                    {branches.map((branch) => (
                      <label key={branch.id}>
                        <input
                          type="checkbox"
                          checked={draft.branch_ids.includes(branch.id)}
                          onChange={() =>
                            updateDraft(
                              user.id,
                              "branch_ids",
                              toggleBranchId(draft.branch_ids, branch.id),
                            )
                          }
                        />
                        <span>{branch.name}</span>
                      </label>
                    ))}
                  </fieldset>

                  <div className="staff-permission-note">
                    <ShieldCheck size={16} />
                    <span>{roleSummary(draft.role_name)}</span>
                  </div>

                  <div className="button-row">
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => setSelectedUserId(user.id)}
                    >
                      <Eye size={17} />
                      Profile
                    </button>
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => saveStaff(user)}
                      disabled={isSaving}
                    >
                      <Save size={17} />
                      Save
                    </button>
                    <button
                      className="secondary-action"
                      type="button"
                      onClick={() => createPasswordReset(user)}
                      disabled={isSaving || !user.is_active}
                    >
                      <KeyRound size={17} />
                      Setup link
                    </button>
                    <button
                      className={user.is_active ? "secondary-action danger-action" : "secondary-action"}
                      type="button"
                      onClick={() => toggleStaffStatus(user)}
                      disabled={isSaving}
                    >
                      {user.is_active ? <PowerOff size={17} /> : <Power size={17} />}
                      {user.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </div>
                </div>
              );
            })}
            {!users.length ? <EmptyState>No staff found</EmptyState> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}
