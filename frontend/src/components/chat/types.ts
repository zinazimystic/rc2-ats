export type ChatRole = "user" | "assistant";
export type MsgStatus = "streaming" | "done" | "stopped" | "interrupted";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  ts: number;
  status: MsgStatus;
  finish?: string;
}

export interface ChatConfig {
  max_chars: number;
  max_messages: number;
  suggestions: string[];
  greeting: string;
  available: boolean;
}

export type Phase = "idle" | "waiting" | "streaming";

export interface ChatNotice {
  text: string;
  tone: "info" | "error";
  retryable: boolean;
}

export const DEFAULT_CONFIG: ChatConfig = {
  max_chars: 2000,
  max_messages: 20,
  suggestions: [],
  greeting: "Hi! I'm the RC3 Assistant. Ask me anything about using the platform.",
  available: true,
};
