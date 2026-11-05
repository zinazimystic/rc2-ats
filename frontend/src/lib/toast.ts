import { toast as sonner, type ExternalToast } from "sonner";
import { friendlyError } from "./errors";

type Msg = string | { title: string; description?: string };
interface Opts {
  description?: string;
  action?: { label: string; onClick: () => void };
  id?: string | number;
  duration?: number;
}

function parts(m: Msg): [string, string | undefined] {
  return typeof m === "string" ? [m, undefined] : [m.title, m.description];
}
function build(o?: Opts, desc?: string): ExternalToast {
  return { description: o?.description ?? desc, action: o?.action, id: o?.id, duration: o?.duration };
}

/** The single entry point for user feedback. Every mutation uses this (success AND error). */
export const notify = {
  success(m: Msg, o?: Opts) {
    const [t, d] = parts(m);
    return sonner.success(t, build(o, d));
  },
  info(m: Msg, o?: Opts) {
    const [t, d] = parts(m);
    return sonner.info(t, build(o, d));
  },
  warning(m: Msg, o?: Opts) {
    const [t, d] = parts(m);
    return sonner.warning(t, build(o, d));
  },
  /** Accepts a string, `{title, description}` or any thrown value; thrown values are mapped to friendly copy. */
  error(m: unknown, o?: Opts) {
    if (m && typeof m === "object" && "title" in m) {
      const x = m as { title: string; description?: string };
      return sonner.error(x.title, build(o, x.description));
    }
    return sonner.error(friendlyError(m), build(o));
  },
  loading(m: string, o?: Opts) {
    return sonner.loading(m, build(o));
  },
  dismiss(id?: string | number) {
    sonner.dismiss(id);
  },
  promise<T>(p: Promise<T>, msgs: { loading: string; success: string | ((v: T) => string); error?: string | ((e: unknown) => string) }) {
    sonner.promise(p, {
      loading: msgs.loading,
      success: msgs.success,
      error: (e: unknown) => (typeof msgs.error === "function" ? msgs.error(e) : (msgs.error ?? friendlyError(e))),
    });
    return p;
  },
};

/** Drop-in for the old sonner `toast` import: toast.success / error / info / warning. */
export const toast = notify;
