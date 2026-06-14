"use client";

import { useSyncExternalStore } from "react";

const WORKSPACE_STORAGE_KEY = "mtc-dashboard:workspace:v2";
const WORKSPACE_CHANGE_EVENT = "mtc-dashboard:workspace-change";

function subscribe(onStoreChange: () => void) {
  function onStorage(event: StorageEvent) {
    if (event.key === WORKSPACE_STORAGE_KEY) onStoreChange();
  }
  window.addEventListener("storage", onStorage);
  window.addEventListener(WORKSPACE_CHANGE_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener(WORKSPACE_CHANGE_EVENT, onStoreChange);
  };
}

function getSnapshot() {
  return window.localStorage.getItem(WORKSPACE_STORAGE_KEY) || "";
}

export function useStoredWorkspaceId() {
  return useSyncExternalStore<string | null>(subscribe, getSnapshot, () => null);
}

export function storeWorkspaceId(classId: string) {
  if (classId) {
    window.localStorage.setItem(WORKSPACE_STORAGE_KEY, classId);
  } else {
    window.localStorage.removeItem(WORKSPACE_STORAGE_KEY);
  }
  window.dispatchEvent(new Event(WORKSPACE_CHANGE_EVENT));
}
