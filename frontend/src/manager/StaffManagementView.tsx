import { Plus, Power, PowerOff, RefreshCw, Save, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel } from "../components/ui";
import { apiRequest, type Branch, type RoleName, type User } from "../services/api";

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
  password: string;
};

type StaffRole = Exclude<RoleName, "ADMIN">;

const STAFF_ROLES: StaffRole[] = ["OWNER", "MANAGER", "CASHIER", "KITCHEN"];

const DEFAULT_NEW_STAFF: NewStaffForm = {
  email: "",
  password: "",
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

function toggleBranchId(branchIds: string[], branchId: string) {
  if (branchIds.includes(branchId)) {
    return branchIds.filter((currentBranchId) => currentBranchId !== branchId);
  }
  return [...branchIds, branchId];
}

export function StaffManagementView({ context, token, branches }: Props) {
  const [users, setUsers] = useState<User[]>([]);
  const [drafts, setDrafts] = useState<Record<string, StaffDraft>>({});
  const [newStaff, setNewStaff] = useState<NewStaffForm>(DEFAULT_NEW_STAFF);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [savingUserId, setSavingUserId] = useState<string | null>(null);

  const activeStaffCount = useMemo(
    () => users.filter((user) => user.is_active).length,
    [users],
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
    if (!validateStaffPayload(newStaff.role_name, newStaff.branch_ids)) {
      return;
    }
    try {
      await apiRequest<User>("/api/v1/auth/users", {
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
      setNewStaff(DEFAULT_NEW_STAFF);
      setNotice("Staff member created");
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

  return (
    <div className="view-grid two-columns">
      <div className="view-stack">
        {error ? <Notice tone="error">{error}</Notice> : null}
        {notice ? <Notice tone="success">{notice}</Notice> : null}
        {isLoading ? <Notice>Loading staff</Notice> : null}

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
            <Field label="Temporary password">
              <input
                type="password"
                value={newStaff.password}
                onChange={(event) => updateNewStaff("password", event.target.value)}
                minLength={8}
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
                        {user.first_name} {user.last_name}
                      </strong>
                      <span>{user.email}</span>
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

                  <div className="button-row">
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
