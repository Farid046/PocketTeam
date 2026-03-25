import React from "react";

export function KillSwitchBanner(): React.ReactElement {
  return (
    <div className="fixed top-0 left-0 right-0 z-50 flex items-center justify-center bg-red-700 py-2 animate-pulse">
      <span className="text-white font-bold tracking-widest text-sm uppercase">
        ⚠ KILL SWITCH ACTIVE — All operations halted
      </span>
    </div>
  );
}
