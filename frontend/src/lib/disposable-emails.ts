// Common throwaway-mail providers. A client-side convenience check only; the backend remains the source of truth.
const DISPOSABLE_DOMAINS = new Set([
  "mailinator.com", "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "guerrillamail.biz", "sharklasers.com", "grr.la",
  "10minutemail.com", "10minutemail.net", "20minutemail.com", "tempmail.com", "temp-mail.org", "temp-mail.io", "tempmail.net",
  "tempail.com", "tempr.email", "throwawaymail.com", "trashmail.com", "trashmail.net", "yopmail.com", "yopmail.net", "yopmail.fr",
  "getnada.com", "nada.email", "dispostable.com", "maildrop.cc", "mailnesia.com", "mintemail.com", "mohmal.com", "emailondeck.com",
  "fakeinbox.com", "fakemail.net", "spamgourmet.com", "spam4.me", "mytemp.email", "burnermail.io", "discard.email", "moakt.com",
  "mail.tm", "inboxkitten.com", "tmailor.com", "emailfake.com", "fakemailgenerator.com", "anonbox.net", "33mail.com", "jetable.org",
  "harakirimail.com", "mailcatch.com", "mailforspam.com", "tmpmail.org", "tmpmail.net", "email-temp.com", "luxusmail.org",
  "cs.email", "1secmail.com", "1secmail.net", "1secmail.org", "linshiyouxiang.net", "tempinbox.com", "owlymail.com", "mail7.io",
]);

/** True when the address uses a known disposable-mail domain (including subdomains of one). */
export function isDisposableEmail(email: string): boolean {
  const domain = email.trim().toLowerCase().split("@")[1];
  if (!domain) return false;
  const parts = domain.split(".");
  for (let i = 0; i < parts.length - 1; i++) {
    if (DISPOSABLE_DOMAINS.has(parts.slice(i).join("."))) return true;
  }
  return false;
}
