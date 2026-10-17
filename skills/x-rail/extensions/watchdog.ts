let flagged = false;

export function markWatchdog(): void {
  flagged = true;
}

export function takeWatchdog(): boolean {
  const value = flagged;
  flagged = false;
  return value;
}
