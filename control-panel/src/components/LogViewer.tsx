import React, { useEffect, useState } from "react";
import { Copy, Loader2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type LogViewerProps = {
  serviceId: string | null;
  serviceName: string;
  isOpen: boolean;
  onClose: () => void;
};

export function LogViewer({ serviceId, serviceName, isOpen, onClose }: LogViewerProps) {
  const [logs, setLogs] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen || !serviceId) return;

    const fetchLogs = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(`/api/logs/${encodeURIComponent(serviceId)}?tail=200`);
        if (!response.ok) {
          throw new Error(`Failed to fetch logs: ${response.statusText}`);
        }
        const data = (await response.json()) as { logs: string };
        setLogs(data.logs || "(no logs available)");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    };

    void fetchLogs();
  }, [isOpen, serviceId]);

  const copyToClipboard = () => {
    void navigator.clipboard.writeText(logs);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <div className="flex items-center justify-between w-full">
            <DialogTitle>{serviceName} — Logs</DialogTitle>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </DialogHeader>

        <div className="flex-1 overflow-hidden flex flex-col gap-3">
          {loading && (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="animate-spin mr-2 h-4 w-4" />
              Fetching logs...
            </div>
          )}

          {error && (
            <div className="p-3 rounded bg-red-950/30 border border-red-900/50 text-red-200 text-sm">
              {error}
            </div>
          )}

          {!loading && !error && (
            <>
              <div className="flex-1 overflow-auto bg-muted/50 rounded p-3 border border-border/60 font-mono text-xs leading-relaxed text-foreground/90">
                {logs.split("\n").map((line, idx) => (
                  <div key={idx} className="whitespace-pre-wrap break-words">
                    {line}
                  </div>
                ))}
              </div>

              <Button
                size="sm"
                variant="outline"
                onClick={copyToClipboard}
                className="self-end"
              >
                <Copy className="mr-2 h-4 w-4" />
                {copied ? "Copied!" : "Copy logs"}
              </Button>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
