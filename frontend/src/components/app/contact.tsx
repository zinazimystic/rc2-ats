"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { BadgeCheck, Hash, Mail, MapPin, MessageCircle, Phone, PhoneCall, Ruler, ShieldAlert, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import { qk } from "@/lib/queries";
import { notify } from "@/lib/toast";
import { fmtDate } from "@/lib/format";
import type { ContactChecks, Msg, PhoneCheck, ProfileIn, ProfileOut, UserOut } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Notice } from "@/components/ui/notice";
import { OtpInput } from "@/components/ui/otp-input";
import { Switch } from "@/components/ui/switch";

function phoneBadges(p: PhoneCheck) {
  const cc = p.country_code ? `+${String(p.country_code).replace(/^\+/, "")}` : null;
  const country = [cc, p.country].filter(Boolean).join(" ");
  return (
    <>
      {p.valid ? <Badge variant="success"><ShieldCheck /> Valid number</Badge> : <Badge variant="destructive"><ShieldAlert /> {p.possible ? "Number looks wrong" : "Invalid number"}</Badge>}
      {country && <Badge variant="secondary"><Hash /> {country}</Badge>}
      {p.location && <Badge variant="secondary"><MapPin /> {p.location}</Badge>}
      {p.line_type && <Badge variant="secondary"><PhoneCall /> {p.line_type.replace(/_/g, " ")}</Badge>}
      {p.national_length != null && <Badge variant="muted"><Ruler /> {p.national_length} digits</Badge>}
    </>
  );
}

function whatsappBadge(p: PhoneCheck) {
  const w = p.whatsapp;
  if (w.status === "declared")
    return (
      <span className="inline-flex flex-wrap items-center gap-2">
        <Badge variant="success"><MessageCircle /> WhatsApp: declared by candidate</Badge>
        {w.link && <a className="text-xs font-medium text-primary hover:underline" href={w.link} target="_blank" rel="noreferrer">Chat on WhatsApp</a>}
      </span>
    );
  return <Badge variant="muted"><MessageCircle /> WhatsApp: {w.status === "not_declared" ? "not declared" : "unknown"}</Badge>;
}

/** Read-only contact summary for recruiters. Honest wording: WhatsApp is declared, never verified. */
export function ContactBadges({ checks }: { checks: ContactChecks | null | undefined }) {
  if (!checks) return null;
  const { email, phone } = checks;
  return (
    <div className="flex flex-wrap items-center gap-1.5" aria-label="Contact checks">
      {email.verified ? (
        <Badge variant="success" title={email.verified_at ? `Verified ${fmtDate(email.verified_at)}` : undefined}><BadgeCheck /> Email verified</Badge>
      ) : email.valid_format ? (
        <Badge variant="warning"><Mail /> Email not verified</Badge>
      ) : (
        <Badge variant="destructive"><Mail /> Email looks invalid</Badge>
      )}
      {phone ? (
        <>
          {phoneBadges(phone)}
          {whatsappBadge(phone)}
        </>
      ) : (
        <Badge variant="muted"><Phone /> No phone provided</Badge>
      )}
      {phone?.issues.map((i) => <span key={i} className="text-xs text-muted-foreground">{i}</span>)}
    </div>
  );
}

function VerifyEmailDialog({ open, onOpenChange, email }: { open: boolean; onOpenChange: (o: boolean) => void; email: string }) {
  const qc = useQueryClient();
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [bad, setBad] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);
  const [delivery, setDelivery] = useState<"email" | "simulated">("email");
  const send = useMutation({
    mutationFn: () => api<Msg & { delivery?: "email" | "simulated"; resend_in_seconds?: number }>("/auth/email/send-code", { method: "POST" }),
    onSuccess: (r) => {
      setSent(true);
      setCode("");
      setBad(false);
      setCooldown(r.resend_in_seconds ?? 60);
      setDelivery(r.delivery ?? "email");
      qc.invalidateQueries({ queryKey: ["notifications"] });
      notify.success("Code sent", { description: r.detail });
    },
    onError: (e) => {
      const wait = (e as { body?: { retry_after?: number } })?.body?.retry_after;
      if (wait) setCooldown(wait);
      notify.error(e);
    },
  });
  const verify = useMutation({
    mutationFn: (c: string) => api<UserOut>("/auth/email/verify", { body: { code: c } }),
    onSuccess: (u) => {
      qc.setQueryData(["me"], u);
      qc.invalidateQueries({ queryKey: qk.profile });
      qc.invalidateQueries({ queryKey: qk.dashboard });
      notify.success("Email verified");
      onOpenChange(false);
    },
    onError: (e) => {
      setBad(true);
      notify.error(e);
    },
  });
  return (
    <Dialog open={open} onOpenChange={(o) => { onOpenChange(o); if (!o) { setSent(false); setCode(""); setBad(false); } }}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Verify your email</DialogTitle>
          <DialogDescription>We’ll send a 6-digit code to {email}.</DialogDescription>
        </DialogHeader>
        {sent && delivery === "simulated" ? (
          <Notice tone="info" title="Demo mode">No real email is sent. Find your code in your <Link href="/candidate/notifications" className="font-medium underline" onClick={() => onOpenChange(false)}>Notifications</Link>.</Notice>
        ) : (
          <p className="text-xs text-muted-foreground">The code is valid for 15 minutes. You can request a new one after 1 minute.</p>
        )}
        {!sent ? (
          <DialogFooter>
            <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button loading={send.isPending} onClick={() => send.mutate()}>Send code</Button>
          </DialogFooter>
        ) : (
          <>
            <OtpInput value={code} onChange={(v) => { setCode(v); setBad(false); }} invalid={bad} disabled={verify.isPending} />
            {bad && <p role="alert" className="text-center text-xs text-destructive">That code didn’t work. Check it and try again, or request a new one.</p>}
            <DialogFooter className="sm:justify-between">
              <Button variant="ghost" disabled={cooldown > 0} loading={send.isPending} onClick={() => send.mutate()}>{cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}</Button>
              <Button disabled={code.length < 6} loading={verify.isPending} onClick={() => verify.mutate(code)}>Verify</Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

/** Candidate's own contact details with verification state. */
export function ContactCard({ profile }: { profile: ProfileOut }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const checks = profile.contact_checks;
  const email = checks?.email;
  const phone = checks?.phone ?? null;
  const verified = email?.verified ?? false;
  const wa = useMutation({
    mutationFn: (v: boolean) => api<ProfileOut>("/candidates/me/profile", { method: "PATCH", body: { whatsapp_enabled: v } satisfies ProfileIn }),
    onSuccess: (r) => {
      qc.setQueryData(qk.profile, r);
      notify.success(r.whatsapp_enabled ? "WhatsApp marked as available" : "WhatsApp removed");
    },
    onError: (e) => notify.error(e),
  });
  return (
    <Card>
      <CardHeader>
        <CardTitle>Contact details</CardTitle>
        <CardDescription>Recruiters see these checks next to your application.</CardDescription>
      </CardHeader>
      <CardContent className="divide-y">
        <div className="flex flex-wrap items-center gap-3 pb-4">
          <span className="grid size-9 place-items-center rounded-full bg-muted"><Mail className="size-4" /></span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{profile.email}</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {verified ? <Badge variant="success"><BadgeCheck /> Verified</Badge> : <Badge variant="warning">Not verified</Badge>}
            </div>
          </div>
          {!verified && <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Verify</Button>}
        </div>
        <div className="space-y-3 pt-4">
          <div className="flex flex-wrap items-start gap-3">
            <span className="grid size-9 place-items-center rounded-full bg-muted"><Phone className="size-4" /></span>
            <div className="min-w-0 flex-1 space-y-2">
              <p className="text-sm font-medium">{phone?.e164 ?? phone?.raw ?? profile.phone ?? "No phone number yet"}</p>
              {phone ? <div className="flex flex-wrap gap-1.5">{phoneBadges(phone)}</div> : !profile.phone && <p className="text-xs text-muted-foreground">Add a phone number in your profile below.</p>}
              {phone?.issues.map((i) => <p key={i} className="text-xs text-muted-foreground">{i}</p>)}
            </div>
          </div>
          {profile.phone && (
            <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-muted/50 p-3">
              <Switch id="wa-switch" checked={!!profile.whatsapp_enabled} disabled={wa.isPending || (phone ? !phone.valid && !phone.possible : false)} onCheckedChange={(v) => wa.mutate(v)} aria-labelledby="wa-label" />
              <div className="min-w-0 flex-1">
                <label id="wa-label" htmlFor="wa-switch" className="text-sm font-medium">I use WhatsApp on this number</label>
                <p className="text-xs text-muted-foreground">Declared by you, not verified.</p>
              </div>
              {profile.whatsapp_enabled && phone?.whatsapp.link && (
                <Button size="sm" variant="outline" asChild>
                  <a href={phone.whatsapp.link} target="_blank" rel="noreferrer"><MessageCircle /> Chat on WhatsApp</a>
                </Button>
              )}
            </div>
          )}
        </div>
      </CardContent>
      <VerifyEmailDialog open={open} onOpenChange={setOpen} email={profile.email} />
    </Card>
  );
}
