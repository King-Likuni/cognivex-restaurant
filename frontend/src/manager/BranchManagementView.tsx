import { Building2, Power, PowerOff, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import type { AppContext } from "../App";
import { EmptyState, Field, Notice, Panel } from "../components/ui";
import { apiRequest, type Branch, type BranchUpdate } from "../services/api";

type Props = {
  context: AppContext;
  token: string;
  onBranchesChanged: () => void;
};

type BranchDraft = {
  name: string;
  code: string;
  location: string;
};

function draftFromBranch(branch: Branch): BranchDraft {
  return {
    name: branch.name,
    code: branch.code,
    location: branch.location ?? "",
  };
}

export function BranchManagementView({ context, token, onBranchesChanged }: Props) {
  const [branches, setBranches] = useState<Branch[]>([]);
  const [drafts, setDrafts] = useState<Record<string, BranchDraft>>({});
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [savingBranchId, setSavingBranchId] = useState<string | null>(null);

  const activeBranchCount = useMemo(
    () => branches.filter((branch) => branch.is_active).length,
    [branches],
  );

  const loadBranches = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const nextBranches = await apiRequest<Branch[]>(
        `/api/v1/restaurants/${context.restaurant.id}/branches`,
        {
          token,
          params: { include_inactive: true },
        },
      );
      setBranches(nextBranches);
      setDrafts(
        Object.fromEntries(nextBranches.map((branch) => [branch.id, draftFromBranch(branch)])),
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load branches");
    } finally {
      setIsLoading(false);
    }
  }, [context.restaurant.id, token]);

  useEffect(() => {
    void loadBranches();
  }, [loadBranches]);

  function updateDraft(branchId: string, field: keyof BranchDraft, value: string) {
    setDrafts((current) => ({
      ...current,
      [branchId]: {
        ...current[branchId],
        [field]: value,
      },
    }));
  }

  async function patchBranch(branch: Branch, body: BranchUpdate, successMessage: string) {
    setSavingBranchId(branch.id);
    setNotice(null);
    setError(null);
    try {
      await apiRequest<Branch>(
        `/api/v1/restaurants/${context.restaurant.id}/branches/${branch.id}`,
        {
          method: "PATCH",
          token,
          body,
        },
      );
      setNotice(successMessage);
      await loadBranches();
      onBranchesChanged();
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not update branch");
    } finally {
      setSavingBranchId(null);
    }
  }

  function saveBranch(branch: Branch) {
    const draft = drafts[branch.id];
    if (!draft) {
      return;
    }
    void patchBranch(
      branch,
      {
        name: draft.name.trim(),
        code: draft.code.trim(),
        location: draft.location.trim() || null,
      },
      "Branch details saved",
    );
  }

  function toggleBranch(branch: Branch) {
    const nextStatus = !branch.is_active;
    void patchBranch(
      branch,
      { is_active: nextStatus },
      nextStatus ? "Branch reactivated" : "Branch deactivated",
    );
  }

  return (
    <div className="view-stack">
      {error ? <Notice tone="error">{error}</Notice> : null}
      {notice ? <Notice tone="success">{notice}</Notice> : null}
      {isLoading ? <Notice>Loading branches</Notice> : null}

      <Panel
        title="Branches"
        action={
          <button className="icon-button" type="button" onClick={loadBranches} title="Refresh">
            <RefreshCw size={17} />
          </button>
        }
      >
        <div className="toolbar-line">
          <span className="status-pill">{activeBranchCount} active</span>
          <span className="status-pill">{branches.length} total</span>
        </div>

        <div className="branch-admin-list">
          {branches.map((branch) => {
            const draft = drafts[branch.id] ?? draftFromBranch(branch);
            const isSaving = savingBranchId === branch.id;
            const disablingLastActive = branch.is_active && activeBranchCount <= 1;
            return (
              <div className="branch-admin-row" key={branch.id}>
                <div className="branch-admin-heading">
                  <Building2 size={18} />
                  <div>
                    <strong>{branch.name}</strong>
                    <span>{branch.code}</span>
                  </div>
                  <span className={branch.is_active ? "status-pill" : "status-pill inactive"}>
                    {branch.is_active ? "Active" : "Inactive"}
                  </span>
                </div>

                <div className="branch-admin-grid">
                  <Field label="Name">
                    <input
                      value={draft.name}
                      onChange={(event) => updateDraft(branch.id, "name", event.target.value)}
                    />
                  </Field>
                  <Field label="Code">
                    <input
                      value={draft.code}
                      onChange={(event) => updateDraft(branch.id, "code", event.target.value)}
                      maxLength={12}
                    />
                  </Field>
                  <Field label="Location">
                    <input
                      value={draft.location}
                      onChange={(event) => updateDraft(branch.id, "location", event.target.value)}
                    />
                  </Field>
                </div>

                <div className="button-row">
                  <button
                    className="secondary-action"
                    type="button"
                    onClick={() => saveBranch(branch)}
                    disabled={isSaving}
                  >
                    <Save size={17} />
                    Save
                  </button>
                  <button
                    className={
                      branch.is_active ? "secondary-action danger-action" : "secondary-action"
                    }
                    type="button"
                    onClick={() => toggleBranch(branch)}
                    disabled={isSaving || disablingLastActive}
                    title={disablingLastActive ? "At least one active branch is required" : ""}
                  >
                    {branch.is_active ? <PowerOff size={17} /> : <Power size={17} />}
                    {branch.is_active ? "Deactivate" : "Reactivate"}
                  </button>
                </div>
              </div>
            );
          })}
          {!branches.length ? <EmptyState>No branches found</EmptyState> : null}
        </div>
      </Panel>
    </div>
  );
}
