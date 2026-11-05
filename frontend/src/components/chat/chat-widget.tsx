"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useQuery } from "@tanstack/react-query";
import { MessageCircle } from "lucide-react";
import { api } from "@/lib/api";
import { useMe } from "@/lib/auth";
import { cn } from "@/lib/utils";
import { useOnline } from "./use-env";
import { useChat } from "./use-chat";
import type { ChatConfig } from "./types";
import "./chat.css";

const ChatPanel = dynamic(() => import("./panel"), { ssr: false });

/** Global floating assistant: launcher + lazily loaded panel. Conversation state lives here so replies finish while closed. */
export function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [mounted, setMounted] = useState(false);
  const [everOpened, setEverOpened] = useState(false);
  const [unread, setUnread] = useState(false);
  const [draft, setDraft] = useState("");
  const launcherRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const openRef = useRef(false);
  const wasOpen = useRef(false);
  const online = useOnline();

  const { data: me } = useMe();
  const userId = me === undefined ? undefined : (me?.id ?? null);

  const cfgQ = useQuery<ChatConfig>({
    queryKey: ["chat-config", userId ?? "anon"],
    queryFn: () => api<ChatConfig>("/chat/config"),
    enabled: everOpened && userId !== undefined,
    staleTime: 5 * 60_000,
    retry: false,
  });

  const chat = useChat({
    config: cfgQ.data,
    online,
    onRestoreDraft: (t) => setDraft((d) => (d ? d : t)),
    onReply: () => {
      if (!openRef.current) setUnread(true);
    },
  });
  const { reset } = chat;

  // Logout / account switch clears the conversation.
  const prevUser = useRef<string | null | undefined>(undefined);
  useEffect(() => {
    if (userId === undefined) return;
    if (prevUser.current !== undefined && prevUser.current !== userId) {
      reset();
      setDraft("");
      setUnread(false);
    }
    prevUser.current = userId;
  }, [userId, reset]);

  const openChat = useCallback(() => {
    clearTimeout(closeTimer.current);
    openRef.current = true;
    setMounted(true);
    setOpen(true);
    setEverOpened(true);
    setUnread(false);
  }, []);
  const closeChat = useCallback(() => {
    openRef.current = false;
    setOpen(false);
    clearTimeout(closeTimer.current);
    closeTimer.current = setTimeout(() => setMounted(false), 180);
  }, []);
  useEffect(() => () => clearTimeout(closeTimer.current), []);

  // Esc closes; focus returns to the launcher.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !e.isComposing && !e.defaultPrevented) closeChat();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, closeChat]);
  useEffect(() => {
    if (wasOpen.current && !open) launcherRef.current?.focus({ preventScroll: true });
    wasOpen.current = open;
  }, [open]);

  return (
    <div className="print:hidden">
      <button
        ref={launcherRef}
        type="button"
        onClick={() => (open ? closeChat() : openChat())}
        aria-label={unread ? "Open RC3 Assistant, new reply" : "Open RC3 Assistant"}
        aria-expanded={open}
        title="Chat with the RC3 Assistant"
        tabIndex={open ? -1 : 0}
        aria-hidden={open || undefined}
        className={cn(
          "rc-pulse fixed right-[max(1rem,env(safe-area-inset-right))] bottom-[max(1rem,env(safe-area-inset-bottom))] z-40 inline-flex size-12 items-center justify-center rounded-full bg-gradient-to-br from-[#2f6bff] to-[#5b4bff] text-white shadow-lg shadow-primary/30 transition duration-200 hover:scale-105 hover:shadow-xl focus-visible:ring-3 focus-visible:ring-primary/40 focus-visible:outline-none active:scale-95 sm:right-5 sm:bottom-5 sm:size-14",
          open && "pointer-events-none scale-75 opacity-0",
        )}
      >
        <MessageCircle className="size-6" />
        {unread && <span className="absolute top-0.5 right-0.5 size-3 rounded-full border-2 border-background bg-destructive" aria-hidden />}
      </button>
      {mounted && (
        <ChatPanel
          state={open ? "open" : "closed"}
          config={cfgQ.data}
          configLoading={cfgQ.isLoading || (everOpened && userId === undefined)}
          configFailed={cfgQ.isError}
          onRecheck={() => void cfgQ.refetch()}
          chat={chat}
          draft={draft}
          setDraft={setDraft}
          inputRef={inputRef}
          online={online}
          onClose={closeChat}
        />
      )}
    </div>
  );
}
