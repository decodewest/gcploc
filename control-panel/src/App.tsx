import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Container,
  Eye,
  Moon,
  RefreshCw,
  Server,
  Sun,
  TerminalSquare,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { LogViewer } from "@/components/LogViewer";
import { ResourceInspector, type InspectableServiceId } from "@/components/ResourceInspector";

type ServiceStatus = "running" | "stopped" | "degraded";

type Service = {
  id: string;
  label: string;
  container: string;
  port: number;
  status: ServiceStatus;
  profile: string;
  quickCmd: string;
};

type DockerStatEntry = {
  cpu: string;
  memory: string;
};

type ObserveSummary = {
  ok?: boolean;
  summary?: string;
};

type ApiSnapshot = {
  timestamp: number;
  services: Service[];
  dependents: string[];
  dockerStats?: Record<string, DockerStatEntry>;
  summaries?: Partial<Record<InspectableServiceId, ObserveSummary>>;
};

const INSPECTABLE_IDS = new Set<string>(["gcs", "pubsub", "cloudtasks"]);

const defaultServices: Service[] = [];

const statusToBadgeVariant: Record<ServiceStatus, "default" | "outline" | "muted"> = {
  running: "default",
  stopped: "muted",
  degraded: "outline",
};

const statusLabel: Record<ServiceStatus, string> = {
  running: "RUNNING",
  stopped: "STOPPED",
  degraded: "DEGRADED",
};

function findDockerStats(
  dockerStats: Record<string, DockerStatEntry> | undefined,
  container: string,
): DockerStatEntry | undefined {
  if (!dockerStats) {
    return undefined;
  }
  const exact = dockerStats[`gcploc_${container}`];
  if (exact) {
    return exact;
  }
  return Object.entries(dockerStats).find(([key]) => key === `gcploc_${container}` || key.endsWith(container))?.[1];
}

function formatMemUsage(raw: string): string {
  const part = raw.split("/")[0]?.trim() ?? raw.trim();
  return part.replace(/\s+/g, "");
}

function zeroInventoryTemplate(serviceId: string): string | null {
  switch (serviceId) {
    case "cloudtasks":
      return "0 queues · 0 tasks";
    case "pubsub":
      return "0 topics · 0 subs";
    case "gcs":
      return "0 buckets · 0 B";
    default:
      return null;
  }
}

function buildServiceSummaryLine(
  service: Service,
  summaries: ApiSnapshot["summaries"],
  dockerStats: ApiSnapshot["dockerStats"],
): string {
  const parts: string[] = [];
  const inventoryTemplate = zeroInventoryTemplate(service.id);
  const stopped = service.status === "stopped";

  if (stopped) {
    if (inventoryTemplate) {
      parts.push(inventoryTemplate);
    }
    parts.push("cpu 0%", "mem 0B");
    return parts.join(" · ");
  }

  const summaryEntry = summaries?.[service.id as InspectableServiceId];
  if (summaryEntry?.summary) {
    parts.push(summaryEntry.summary);
  } else if (inventoryTemplate) {
    parts.push(inventoryTemplate);
  }

  const stats = findDockerStats(dockerStats, service.container);
  if (stats) {
    const cpu = stats.cpu.replace(/\s+/g, "");
    const mem = formatMemUsage(stats.memory);
    parts.push(`cpu ${cpu}`, `mem ${mem}`);
  } else {
    parts.push("cpu 0%", "mem 0B");
  }

  return parts.join(" · ");
}

function App() {
  const [isDark, setIsDark] = useState(true);
  const [services, setServices] = useState<Service[]>(defaultServices);
  const [dependents, setDependents] = useState<string[]>([]);
  const [dockerStats, setDockerStats] = useState<Record<string, DockerStatEntry>>({});
  const [summaries, setSummaries] = useState<ApiSnapshot["summaries"]>({});
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [streamStatus, setStreamStatus] = useState<"connecting" | "live" | "degraded">("connecting");
  const [selectedServiceId, setSelectedServiceId] = useState<string | null>(null);
  const [inspectServiceId, setInspectServiceId] = useState<InspectableServiceId | null>(null);

  const selectedService = useMemo(
    () => services.find((s) => s.id === selectedServiceId),
    [services, selectedServiceId],
  );

  const inspectService = useMemo(
    () => services.find((s) => s.id === inspectServiceId),
    [services, inspectServiceId],
  );

  const applySnapshot = (payload: ApiSnapshot) => {
    setServices(payload.services ?? defaultServices);
    setDependents(payload.dependents ?? []);
    setDockerStats(payload.dockerStats ?? {});
    setSummaries(payload.summaries ?? {});
    setLastUpdated(payload.timestamp ?? Math.floor(Date.now() / 1000));
  };

  const loadSnapshot = async () => {
    try {
      const response = await fetch("/api/status", { cache: "no-store" });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const payload = (await response.json()) as ApiSnapshot;
      applySnapshot(payload);
      return true;
    } catch {
      return false;
    }
  };

  useEffect(() => {
    void loadSnapshot();

    const source = new EventSource("/api/events");
    setStreamStatus("connecting");

    source.addEventListener("snapshot", (event) => {
      try {
        applySnapshot(JSON.parse((event as MessageEvent).data) as ApiSnapshot);
        setStreamStatus("live");
      } catch {
        setStreamStatus("degraded");
      }
    });

    source.addEventListener("docker", () => {
      setStreamStatus("live");
      void loadSnapshot();
    });

    source.addEventListener("heartbeat", () => {
      setStreamStatus("live");
    });

    source.onerror = () => {
      setStreamStatus("degraded");
    };

    const fallback = window.setInterval(() => {
      void loadSnapshot();
    }, 30_000);

    return () => {
      window.clearInterval(fallback);
      source.close();
    };
  }, []);

  const runningCount = useMemo(() => services.filter((service) => service.status === "running").length, [services]);

  const toggleTheme = () => {
    const next = !isDark;
    setIsDark(next);
    document.documentElement.classList.toggle("dark", next);
  };

  return (
    <div className="min-h-screen px-4 py-8 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="flex flex-col gap-4 rounded-xl border bg-card/80 p-5 backdrop-blur sm:flex-row sm:items-center sm:justify-between">
          <div className="space-y-1">
            <p className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Local GCP Emulator Dashboard</p>
            <h1 className="text-2xl font-semibold">Control Panel</h1>
            <p className="text-sm text-muted-foreground">
              Live service status stream with fallback sync for resilient local observability.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => void loadSnapshot()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={toggleTheme}>
              {isDark ? <Sun className="mr-2 h-4 w-4" /> : <Moon className="mr-2 h-4 w-4" />}
              {isDark ? "Light" : "Dark"}
            </Button>
          </div>
        </header>

        <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Running services"
            value={`${runningCount}/${services.length}`}
            icon={<Server className="h-4 w-4" />}
          />
          <MetricCard title="Network" value="gcploc_net" icon={<Container className="h-4 w-4" />} />
          <MetricCard title="Clients" value={String(dependents.length)} icon={<AlertTriangle className="h-4 w-4" />} />
          <MetricCard
            title="Stream"
            value={streamStatus.toUpperCase()}
            icon={isDark ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
          />
        </section>

        <section className="space-y-3">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold">Emulator services</h2>
            <p className="text-sm text-muted-foreground">
              Compose-managed emulator containers with live summaries and resource usage when running.
            </p>
          </div>
          <div className="grid gap-4 lg:grid-cols-3">
            {services.map((service) => {
              const canInspect = INSPECTABLE_IDS.has(service.id);
              const actionsDisabled = service.status === "stopped";
              const summaryLine = buildServiceSummaryLine(service, summaries, dockerStats);

              return (
                <Card key={service.id} className="border-border/80">
                  <CardHeader>
                    <div className="flex items-center justify-between gap-3">
                      <CardTitle>{service.label}</CardTitle>
                      <Badge variant={statusToBadgeVariant[service.status]}>{statusLabel[service.status]}</Badge>
                    </div>
                    <CardDescription>Container: {service.container}</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm">
                    <Row label="Profile" value={service.profile} />
                    <Row label="Endpoint" value={`${service.container}:${service.port}`} />
                    <p className="truncate text-xs text-muted-foreground" title={summaryLine}>
                      {summaryLine}
                    </p>
                  </CardContent>
                  <CardFooter className="flex flex-row gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      className="flex-1 justify-start"
                      disabled={actionsDisabled}
                      title={
                        actionsDisabled
                          ? "Start this service to view container logs"
                          : "View container logs"
                      }
                      onClick={() => setSelectedServiceId(service.id)}
                    >
                      <TerminalSquare className="mr-2 h-4 w-4" />
                      View logs
                    </Button>
                    {canInspect ? (
                      <Button
                        variant="outline"
                        size="sm"
                        className="flex-1 justify-start"
                        disabled={actionsDisabled}
                        title={
                          actionsDisabled
                            ? "Start this service to inspect resources"
                            : "Inspect emulator resources (observation only)"
                        }
                        onClick={() => setInspectServiceId(service.id as InspectableServiceId)}
                      >
                        <Eye className="mr-2 h-4 w-4" />
                        Inspect
                      </Button>
                    ) : null}
                  </CardFooter>
                </Card>
              );
            })}
          </div>
        </section>

        <section className="space-y-3">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold">Connected clients</h2>
            <p className="text-sm text-muted-foreground">
              Non-gcploc containers currently attached to gcploc_net (discovered; not hard-coded).
            </p>
          </div>
          <Card className="border-border/80">
          <CardHeader>
            <CardTitle>Network attachments</CardTitle>
            <CardDescription>Peers sharing the emulator network right now.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex flex-wrap gap-2">
              {dependents.length === 0 ? (
                <span className="text-muted-foreground">None attached</span>
              ) : (
                dependents.map((name) => (
                  <Badge key={name} variant="outline">
                    {name}
                  </Badge>
                ))
              )}
            </div>
            <p className="text-xs text-muted-foreground">
              Last updated: {lastUpdated ? new Date(lastUpdated * 1000).toLocaleTimeString() : "pending"}
            </p>
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                Stop confirmation preview
              </p>
              <div className="rounded-lg border border-border/80 bg-muted/60 p-3 font-mono text-xs leading-relaxed">
                [gcploc] Warning: containers currently attached to gcploc_net were detected:{"\n"}
                {dependents.length === 0 ? "- none" : dependents.map((name) => `- ${name}`).join("\n")}
                {"\n"}
                Proceed and stop emulator services? [y/N]
              </div>
            </div>
          </CardContent>
        </Card>
        </section>
      </div>

      <LogViewer
        serviceId={selectedServiceId}
        serviceName={selectedService?.label || ""}
        isOpen={selectedServiceId !== null}
        onClose={() => setSelectedServiceId(null)}
      />

      <ResourceInspector
        serviceId={inspectServiceId}
        serviceName={inspectService?.label || ""}
        isOpen={inspectServiceId !== null}
        onClose={() => setInspectServiceId(null)}
      />
    </div>
  );
}

type MetricCardProps = {
  title: string;
  value: string;
  icon: JSX.Element;
};

function MetricCard({ title, value, icon }: MetricCardProps) {
  return (
    <Card className="border-border/80">
      <CardHeader className="space-y-2">
        <div className="text-muted-foreground">{icon}</div>
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-xl tracking-tight">{value}</CardTitle>
      </CardHeader>
    </Card>
  );
}

type RowProps = {
  label: string;
  value: string;
};

function Row({ label, value }: RowProps) {
  return (
    <div className="flex items-center justify-between border-b border-border/70 pb-2 text-xs uppercase tracking-wide text-muted-foreground last:border-none last:pb-0">
      <span>{label}</span>
      <span className="font-medium text-foreground normal-case tracking-normal">{value}</span>
    </div>
  );
}

export default App;
