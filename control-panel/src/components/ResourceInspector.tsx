import React, { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Folder, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ManagePanel } from "@/components/manage/ManagePanel";

export type InspectableServiceId = "gcs" | "pubsub" | "cloudtasks";

type ResourceInspectorProps = {
  serviceId: InspectableServiceId | null;
  serviceName: string;
  isOpen: boolean;
  onClose: () => void;
};

type GcsBucketResponse = {
  ok: boolean;
  buckets?: string[];
  summary?: string;
  error?: string;
};

type GcsObjectRow = {
  name?: string;
  size?: string | number;
  updated?: string;
};

type GcsListingResponse = {
  ok: boolean;
  bucket?: string;
  prefix?: string;
  objects?: GcsObjectRow[];
  prefixes?: string[];
  summary?: string;
  error?: string;
};

type PubSubSubscription = {
  name?: string;
  topic?: string;
};

type PubSubResponse = {
  ok: boolean;
  topics?: string[];
  subscriptions?: Array<string | PubSubSubscription>;
  summary?: string;
  error?: string;
  partial?: boolean;
};

type CloudTaskRow = {
  name?: string;
  scheduleTime?: string | null;
  dispatchCount?: number | null;
};

type CloudQueueRow = {
  name?: string;
  taskCount?: number | null;
  tasks?: CloudTaskRow[] | null;
};

type CloudTasksResponse = {
  ok: boolean;
  queues?: CloudQueueRow[];
  summary?: string;
  error?: string;
  partial?: boolean;
};

function topicShortName(fullTopic: string): string {
  const parts = fullTopic.split("/");
  return parts[parts.length - 1] ?? fullTopic;
}

function subscriptionShortName(fullSub: string): string {
  const parts = fullSub.split("/");
  return parts[parts.length - 1] ?? fullSub;
}

function formatBytes(value: string | number | undefined): string {
  if (value === undefined || value === null || value === "") {
    return "\u2014";
  }
  const n = typeof value === "number" ? value : Number.parseInt(String(value), 10);
  if (Number.isNaN(n)) {
    return String(value);
  }
  if (n < 1024) {
    return `${n} B`;
  }
  if (n < 1024 * 1024) {
    return `${(n / 1024).toFixed(1)} KiB`;
  }
  return `${(n / (1024 * 1024)).toFixed(1)} MiB`;
}

function GcsInspector({ reloadToken }: { reloadToken: number }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [buckets, setBuckets] = useState<string[]>([]);
  const [selectedBucket, setSelectedBucket] = useState<string | null>(null);
  const [prefix, setPrefix] = useState("");
  const [objects, setObjects] = useState<GcsObjectRow[]>([]);
  const [folderPrefixes, setFolderPrefixes] = useState<string[]>([]);

  const loadBuckets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/observe/gcs", { cache: "no-store" });
      const data = (await response.json()) as GcsBucketResponse;
      if (!response.ok || !data.ok) {
        throw new Error(data.error || `Request failed (${response.status})`);
      }
      setBuckets(data.buckets ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setBuckets([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadListing = useCallback(async (bucket: string, nextPrefix: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ bucket, prefix: nextPrefix });
      const response = await fetch(`/api/observe/gcs?${params.toString()}`, { cache: "no-store" });
      const data = (await response.json()) as GcsListingResponse;
      if (!response.ok || !data.ok) {
        throw new Error(data.error || `Request failed (${response.status})`);
      }
      setSelectedBucket(bucket);
      setPrefix(nextPrefix);
      setObjects(data.objects ?? []);
      setFolderPrefixes(data.prefixes ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBuckets();
    setSelectedBucket(null);
    setPrefix("");
    setObjects([]);
    setFolderPrefixes([]);
  }, [loadBuckets, reloadToken]);

  const breadcrumbParts = useMemo(() => {
    if (!selectedBucket) {
      return [] as { label: string; prefix: string }[];
    }
    const crumbs: { label: string; prefix: string }[] = [{ label: selectedBucket, prefix: "" }];
    if (!prefix) {
      return crumbs;
    }
    const segments = prefix.replace(/\/$/, "").split("/").filter(Boolean);
    let acc = "";
    for (const segment of segments) {
      acc = `${acc}${segment}/`;
      crumbs.push({ label: segment, prefix: acc });
    }
    return crumbs;
  }, [selectedBucket, prefix]);

  const totalBytes = useMemo(() => {
    let sum = 0;
    for (const obj of objects) {
      const n = typeof obj.size === "number" ? obj.size : Number.parseInt(String(obj.size ?? ""), 10);
      if (!Number.isNaN(n)) {
        sum += n;
      }
    }
    return sum;
  }, [objects]);

  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs text-muted-foreground">
        Local object inventory for the Fake GCS emulator. Counts and sizes reflect emulator state, not cloud quotas.
      </p>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading...
        </div>
      ) : null}

      {error ? (
        <div className="rounded border border-red-900/50 bg-red-950/30 p-3 text-red-200">{error}</div>
      ) : null}

      {!selectedBucket ? (
        <div className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Buckets ({buckets.length})</p>
          {buckets.length === 0 && !loading ? <p className="text-muted-foreground">No buckets found.</p> : null}
          <ul className="divide-y divide-border/60 rounded border border-border/60">
            {buckets.map((bucket) => (
              <li key={bucket}>
                <button
                  type="button"
                  className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-muted/50"
                  onClick={() => void loadListing(bucket, "")}
                >
                  <span className="font-mono text-xs">{bucket}</span>
                  <span className="text-xs text-muted-foreground">Open</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-1 text-xs">
            <button type="button" className="text-primary hover:underline" onClick={() => {
                setSelectedBucket(null);
                setPrefix("");
                setObjects([]);
                setFolderPrefixes([]);
                void loadBuckets();
              }}>
              Buckets
            </button>
            {breadcrumbParts.map((crumb, idx) => (
              <React.Fragment key={`${crumb.prefix}-${idx}`}>
                <span className="text-muted-foreground">/</span>
                <button
                  type="button"
                  className="font-mono hover:underline"
                  onClick={() => void loadListing(selectedBucket, crumb.prefix)}
                >
                  {crumb.label}
                </button>
              </React.Fragment>
            ))}
          </div>

          {folderPrefixes.length > 0 ? (
            <div className="space-y-1">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Folders</p>
              <ul className="divide-y divide-border/60 rounded border border-border/60">
                {folderPrefixes.map((folderPrefix) => (
                  <li key={folderPrefix}>
                    <button
                      type="button"
                      className="flex w-full items-center gap-2 px-3 py-2 text-left hover:bg-muted/50"
                      onClick={() => void loadListing(selectedBucket, folderPrefix)}
                    >
                      <Folder className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="font-mono text-xs">{folderPrefix.replace(prefix, "") || folderPrefix}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          <div className="space-y-1">
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Objects ({objects.length}) · total {formatBytes(totalBytes)}
            </p>
            <ul className="max-h-64 divide-y divide-border/60 overflow-auto rounded border border-border/60">
              {objects.length === 0 ? (
                <li className="px-3 py-2 text-muted-foreground">No objects at this prefix.</li>
              ) : (
                objects.map((obj) => (
                  <li key={obj.name} className="flex items-center justify-between gap-2 px-3 py-2 font-mono text-xs">
                    <span className="truncate" title={obj.name}>
                      {(obj.name ?? "").replace(prefix, "") || obj.name}
                    </span>
                    <span className="shrink-0 text-muted-foreground">{formatBytes(obj.size)}</span>
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      )}
    </div>
  );
}

function PubSubInspector({ reloadToken }: { reloadToken: number }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topics, setTopics] = useState<string[]>([]);
  const [subscriptions, setSubscriptions] = useState<PubSubSubscription[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/observe/pubsub", { cache: "no-store" });
        const data = (await response.json()) as PubSubResponse;
        if (!response.ok || !data.ok) {
          throw new Error(data.error || `Request failed (${response.status})`);
        }
        setTopics(data.topics ?? []);
        setSubscriptions(
          (data.subscriptions ?? []).map((s) =>
            typeof s === "string" ? { name: s, topic: "" } : { name: s.name ?? "", topic: s.topic ?? "" },
          ),
        );
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [reloadToken]);

  const subsByTopic = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const topic of topics) {
      map.set(topic, []);
    }
    for (const sub of subscriptions) {
      const name = sub.name ?? "";
      const topicRef = sub.topic ?? "";
      if (topicRef && map.has(topicRef)) {
        map.get(topicRef)?.push(name);
        continue;
      }
      let matched = false;
      for (const topic of topics) {
        if (topicRef === topic || (topicRef && topicRef.includes(topic)) || name.includes(topic)) {
          map.get(topic)?.push(name);
          matched = true;
          break;
        }
      }
      if (!matched && topics[0] && name) {
        map.get(topics[0])?.push(name);
      }
    }
    return map;
  }, [topics, subscriptions]);

  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs text-muted-foreground">Read-only view of topics and subscriptions in the Pub/Sub emulator.</p>
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading...
        </div>
      ) : null}
      {error ? (
        <div className="rounded border border-red-900/50 bg-red-950/30 p-3 text-red-200">{error}</div>
      ) : null}
      {!loading && !error ? (
        <ul className="divide-y divide-border/60 rounded border border-border/60">
          {topics.length === 0 ? (
            <li className="px-3 py-2 text-muted-foreground">No topics found.</li>
          ) : (
            topics.map((topic) => {
              const topicSubs = subsByTopic.get(topic) ?? [];
              const isOpen = expanded[topic] ?? true;
              return (
                <li key={topic} className="px-3 py-2">
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 text-left"
                    onClick={() => setExpanded((prev) => ({ ...prev, [topic]: !isOpen }))}
                  >
                    {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    <span className="font-mono text-xs">{topicShortName(topic)}</span>
                    <span className="text-xs text-muted-foreground">({topicSubs.length} subs)</span>
                  </button>
                  {isOpen ? (
                    <ul className="ml-6 mt-2 space-y-1 border-l border-border/60 pl-3">
                      {topicSubs.length === 0 ? (
                        <li className="text-xs text-muted-foreground">No subscriptions</li>
                      ) : (
                        topicSubs.map((sub) => (
                          <li key={sub} className="font-mono text-xs text-muted-foreground">
                            {subscriptionShortName(sub)}
                          </li>
                        ))
                      )}
                    </ul>
                  ) : null}
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}

function CloudTasksInspector({ reloadToken }: { reloadToken: number }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [queues, setQueues] = useState<CloudQueueRow[]>([]);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/observe/cloudtasks", { cache: "no-store" });
        const data = (await response.json()) as CloudTasksResponse;
        if (!response.ok) {
          throw new Error(data.error || `Request failed (${response.status})`);
        }
        setQueues(data.queues ?? []);
        if (!data.ok && data.error) {
          setError(data.error);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [reloadToken]);

  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs text-muted-foreground">Read-only queue and task inventory from the Cloud Tasks emulator.</p>
      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Loading...
        </div>
      ) : null}
      {error ? (
        <div className="rounded border border-red-900/50 bg-red-950/30 p-3 text-red-200">{error}</div>
      ) : null}
      {!loading ? (
        <ul className="divide-y divide-border/60 rounded border border-border/60">
          {queues.length === 0 ? (
            <li className="px-3 py-2 text-muted-foreground">No queues found.</li>
          ) : (
            queues.map((queue) => {
              const key = queue.name ?? "queue";
              const isOpen = expanded[key] ?? false;
              const tasks = queue.tasks ?? [];
              return (
                <li key={key} className="px-3 py-2">
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 text-left"
                    onClick={() => setExpanded((prev) => ({ ...prev, [key]: !isOpen }))}
                  >
                    {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                    <span className="font-mono text-xs">{key}</span>
                    <span className="text-xs text-muted-foreground">
                      ({queue.taskCount ?? tasks.length} tasks)
                    </span>
                  </button>
                  {isOpen ? (
                    <div className="ml-6 mt-2 overflow-auto border-l border-border/60 pl-3">
                      <table className="w-full text-left text-xs">
                        <thead className="text-muted-foreground">
                          <tr>
                            <th className="pb-1 pr-2 font-medium">Task</th>
                            <th className="pb-1 pr-2 font-medium">Schedule</th>
                            <th className="pb-1 font-medium">Dispatch</th>
                          </tr>
                        </thead>
                        <tbody>
                          {tasks.length === 0 ? (
                            <tr>
                              <td colSpan={3} className="py-1 text-muted-foreground">
                                No tasks listed
                              </td>
                            </tr>
                          ) : (
                            tasks.map((task) => {
                              const taskLabel = task.name?.split("/").pop() ?? task.name ?? "\u2014";
                              return (
                                <tr key={task.name ?? taskLabel} className="border-t border-border/40">
                                  <td className="py-1 pr-2 font-mono">{taskLabel}</td>
                                  <td className="py-1 pr-2 text-muted-foreground">{task.scheduleTime ?? "\u2014"}</td>
                                  <td className="py-1 text-muted-foreground">
                                    {task.dispatchCount ?? "\u2014"}
                                  </td>
                                </tr>
                              );
                            })
                          )}
                        </tbody>
                      </table>
                    </div>
                  ) : null}
                </li>
              );
            })
          )}
        </ul>
      ) : null}
    </div>
  );
}

type InspectorTab = "observe" | "manage";

export function ResourceInspector({ serviceId, serviceName, isOpen, onClose }: ResourceInspectorProps) {
  const [tab, setTab] = React.useState<InspectorTab>("observe");
  const [observeReloadToken, setObserveReloadToken] = React.useState(0);

  React.useEffect(() => {
    if (isOpen) {
      setTab("observe");
    }
  }, [isOpen, serviceId]);

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="flex max-h-[85vh] max-w-3xl flex-col">
        <DialogHeader>
          <DialogTitle>{serviceName} — Emulator panel</DialogTitle>
          <DialogDescription>
            Observe resources or run scoped local manage actions (registered services only).
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2 border-b border-border/60 pb-2">
          <Button
            type="button"
            size="sm"
            variant={tab === "observe" ? "default" : "outline"}
            onClick={() => setTab("observe")}
          >
            Observe
          </Button>
          <Button
            type="button"
            size="sm"
            variant={tab === "manage" ? "default" : "outline"}
            onClick={() => setTab("manage")}
          >
            Manage
          </Button>
        </div>

        <div className="min-h-0 flex-1 overflow-auto pr-1">
          {tab === "observe" && serviceId === "gcs" ? (
            <GcsInspector reloadToken={observeReloadToken} />
          ) : null}
          {tab === "observe" && serviceId === "pubsub" ? (
            <PubSubInspector reloadToken={observeReloadToken} />
          ) : null}
          {tab === "observe" && serviceId === "cloudtasks" ? (
            <CloudTasksInspector reloadToken={observeReloadToken} />
          ) : null}
          {tab === "manage" && serviceId ? (
            <ManagePanel
              serviceId={serviceId}
              onActionSuccess={() => setObserveReloadToken((t) => t + 1)}
            />
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
