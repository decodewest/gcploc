import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmResourceDialog } from "@/components/manage/ConfirmResourceDialog";
import type { InspectableServiceId } from "@/components/ResourceInspector";

type FieldSpec = {
  name: string;
  label: string;
  type: string;
  required?: boolean;
};

type ActionSpec = {
  id: string;
  label: string;
  destructive: boolean;
  confirmField?: string | null;
  fields: FieldSpec[];
};

type CapabilitiesResponse = {
  services?: Partial<Record<InspectableServiceId, { actions: ActionSpec[] }>>;
};

type ManagePanelProps = {
  serviceId: InspectableServiceId;
  onActionSuccess?: () => void;
};

type PendingDestructive = {
  action: ActionSpec;
  payload: Record<string, string>;
  confirmField: string;
  expected: string;
};

function emptyValues(fields: FieldSpec[]): Record<string, string> {
  const out: Record<string, string> = {};
  for (const field of fields) {
    out[field.name] = "";
  }
  return out;
}

export function ManagePanel({ serviceId, onActionSuccess }: ManagePanelProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actions, setActions] = useState<ActionSpec[]>([]);
  const [valuesByAction, setValuesByAction] = useState<Record<string, Record<string, string>>>({});
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingDestructive | null>(null);

  const loadCapabilities = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/manage/capabilities", { cache: "no-store" });
      if (!response.ok) {
        if (response.status === 404) {
          throw new Error(
            "Manage API not found (HTTP 404). Restart the control panel (gcploc stop cp && gcploc start cp). A stale process may still own port 8787 (including under WSL).",
          );
        }
        throw new Error(`capabilities HTTP ${response.status}`);
      }
      const data = (await response.json()) as CapabilitiesResponse;
      const list = data.services?.[serviceId]?.actions ?? [];
      setActions(list);
      const initial: Record<string, Record<string, string>> = {};
      for (const action of list) {
        initial[action.id] = emptyValues(action.fields ?? []);
      }
      setValuesByAction(initial);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load capabilities");
      setActions([]);
    } finally {
      setLoading(false);
    }
  }, [serviceId]);

  useEffect(() => {
    void loadCapabilities();
    setMessage(null);
  }, [loadCapabilities]);
  const setField = (actionId: string, fieldName: string, value: string) => {
    setValuesByAction((prev) => ({
      ...prev,
      [actionId]: { ...prev[actionId], [fieldName]: value },
    }));
  };

  const buildPayload = (action: ActionSpec): Record<string, string> => {
    const values = valuesByAction[action.id] ?? {};
    const payload: Record<string, string> = {};
    for (const field of action.fields ?? []) {
      const val = (values[field.name] ?? "").trim();
      if (field.required && !val) {
        throw new Error(`${field.label} is required`);
      }
      if (val) {
        payload[field.name] = val;
      }
    }
    return payload;
  };

  const runAction = async (action: ActionSpec, payload: Record<string, string>, confirm?: string) => {
    setBusyAction(action.id);
    setMessage(null);
    setError(null);
    try {
      const body = confirm ? { ...payload, confirm } : payload;
      const response = await fetch(`/api/manage/${serviceId}/${action.id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = (await response.json()) as { ok?: boolean; error?: string; result?: unknown };
      if (!response.ok || !data.ok) {
        throw new Error(data.error || `Request failed (${response.status})`);
      }
      setMessage(`${action.label} succeeded.`);
      onActionSuccess?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed");
    } finally {
      setBusyAction(null);
      setPending(null);
    }
  };

  const onSubmit = (action: ActionSpec) => {
    try {
      const payload = buildPayload(action);
      if (action.destructive) {
        const confirmField = action.confirmField || "name";
        const expected = payload[confirmField];
        if (!expected) {
          setError(`Fill in ${confirmField} before confirming deletion.`);
          return;
        }
        setPending({ action, payload, confirmField, expected });
        return;
      }
      void runAction(action, payload);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Invalid form");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        Loading manage actions...
      </div>
    );
  }

  return (
    <div className="space-y-4 text-sm">
      <p className="text-xs text-muted-foreground">
        Scoped local management for this emulator only. Destructive actions require typing the resource name. Start/stop
        containers remains a CLI responsibility.
      </p>

      {error ? (
        <div className="rounded border border-red-900/50 bg-red-950/30 p-3 text-red-200">{error}</div>
      ) : null}
      {message ? (
        <div className="rounded border border-emerald-900/40 bg-emerald-950/20 p-3 text-emerald-100">{message}</div>
      ) : null}

      {actions.length === 0 ? (
        <p className="text-muted-foreground">No manage actions registered for this service.</p>
      ) : (
        <ul className="space-y-4">
          {actions.map((action) => {
            const values = valuesByAction[action.id] ?? {};
            const busy = busyAction === action.id;
            return (
              <li key={action.id} className="rounded-lg border border-border/70 p-4">
                <div className="mb-3 flex items-center justify-between gap-2">
                  <p className="font-medium">{action.label}</p>
                  {action.destructive ? (
                    <span className="text-xs uppercase tracking-wide text-amber-400">Destructive</span>
                  ) : null}
                </div>
                <div className="space-y-2">
                  {(action.fields ?? []).map((field) => (
                    <label key={field.name} className="block space-y-1">
                      <span className="text-xs text-muted-foreground">{field.label}</span>
                      {field.type === "textarea" ? (
                        <textarea
                          className="min-h-[72px] w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
                          value={values[field.name] ?? ""}
                          onChange={(e) => setField(action.id, field.name, e.target.value)}
                        />
                      ) : (
                        <input
                          className="w-full rounded-md border border-border bg-background px-3 py-2 font-mono text-xs"
                          value={values[field.name] ?? ""}
                          onChange={(e) => setField(action.id, field.name, e.target.value)}
                        />
                      )}
                    </label>
                  ))}
                </div>
                <Button
                  type="button"
                  size="sm"
                  className="mt-3"
                  variant={action.destructive ? "outline" : "default"}
                  disabled={busy}
                  onClick={() => onSubmit(action)}
                >
                  {busy ? "Working..." : action.label}
                </Button>
              </li>
            );
          })}
        </ul>
      )}

      <ConfirmResourceDialog
        open={pending !== null}
        resourceLabel={pending?.confirmField ?? "name"}
        expectedValue={pending?.expected ?? ""}
        busy={busyAction !== null}
        onCancel={() => setPending(null)}
        onConfirm={() => {
          if (!pending) {
            return;
          }
          void runAction(pending.action, pending.payload, pending.expected);
        }}
      />
    </div>
  );
}
