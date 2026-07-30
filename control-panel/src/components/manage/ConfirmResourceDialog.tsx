import React, { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type ConfirmResourceDialogProps = {
  open: boolean;
  resourceLabel: string;
  expectedValue: string;
  onConfirm: () => void;
  onCancel: () => void;
  busy?: boolean;
};

export function ConfirmResourceDialog({
  open,
  resourceLabel,
  expectedValue,
  onConfirm,
  onCancel,
  busy = false,
}: ConfirmResourceDialogProps) {
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (open) {
      setTyped("");
    }
  }, [open, expectedValue]);

  const matches = typed === expectedValue;

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onCancel()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Confirm destructive action</DialogTitle>
          <DialogDescription>
            Type the {resourceLabel} exactly to confirm. This only affects your local emulator.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <p className="font-mono text-xs text-muted-foreground">{expectedValue}</p>
          <input
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            placeholder={resourceLabel}
            autoComplete="off"
          />
        </div>
        <DialogFooter className="gap-2 sm:gap-0">
          <Button type="button" variant="outline" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button type="button" variant="default" disabled={!matches || busy} onClick={onConfirm}>
            {busy ? "Working..." : "Confirm"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
