"""Input guards (normalise, injection detection, redaction, history trimming) and the streaming output guard."""
from __future__ import annotations

import base64
import re
import unicodedata
from dataclasses import dataclass

MAX_CONTENT = 2000
MAX_TOTAL = 12000
HOLD = 80  # output chars held back so patterns split across chunks are caught before emitting
SHINGLE = 40

DEFLECTION = (
    "I can only help with using RC3 Talent Intelligence and with recruitment and career questions, so I can't help with that. "
    "Would you like tips on resumes, interviews or hiring?"
)
OUTPUT_REFUSAL = "Sorry, I can't share that. I'm happy to help with resumes, interviews, hiring or using the platform instead."
SECRET_NOTE = "Please don't share passwords, keys or verification codes here. I've hidden them from my side."

_STRIP_CATS = {"Cc", "Cf", "Cs", "Co", "Zl", "Zp"}


def normalize(text: str, cap: int = MAX_CONTENT) -> str:
    """NFKC, drop control/zero-width/bidi characters, collapse whitespace, cap length."""
    text = unicodedata.normalize("NFKC", text or "")
    text = "".join(" " if ch in "\t\r\n  " else ("" if unicodedata.category(ch) in _STRIP_CATS else ch) for ch in text)
    return re.sub(r"\s+", " ", text).strip()[:cap]


# --------------------------------------------------------------------------- injection detection
_LEET = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s", "!": "i", "|": "i"})
_SPACED = re.compile(r"(?:\b\w\b ){3,}\b\w\b")

_PATTERNS = [re.compile(p) for p in (
    r"\b(ignore|disregard|forget|override|bypass|skip|drop|discard|neglect)\b.{0,30}\b(previous|prior|above|earlier|all|any|your|the|these|those|system|safety)\b.{0,30}\b(instructions?|prompts?|rules?|guidelines?|directives?|constraints?|restrictions?|guardrails?|programming|filters?|polic(y|ies))\b",
    r"\byou are now\b.{0,12}\b(a|an|the|my|in|no longer|free|dan|called|named|unrestricted)\b",
    r"\b(from now on|henceforth)\b.{0,20}\b(you|act|behave|pretend|ignore)\b",
    r"\b(pretend|imagine) (to be|you are|you re|that you)\b",
    r"\bact as (if|though)? ?(you|an? (unrestricted|unfiltered|jailbroken|evil|different|new))\b",
    r"\b(role ?play|play the role)\b.{0,15}\b(as|of)\b",
    r"\bdo anything now\b|\bdan mode\b|\bjailbreak|\bdeveloper mode\b|\bgod mode\b|\bsudo mode\b|\bunrestricted mode\b",
    r"\b(without|no|remove|disable|turn off)\b.{0,10}\b(restrictions?|filters?|limitations?|guardrails?|safety|censorship)\b",
    r"\b(reveal|show|print|repeat|display|output|tell me|give me|leak|dump|share|recite|write out|translate|summari[sz]e|paraphrase|encode|what (is|are|was|were)|copy)\b.{0,40}\b(system|initial|original|hidden|secret|your|developer|first)\b.{0,15}\b(prompts?|instructions?|rules|configuration|config|message|directives?)\b",
    r"\b(reveal|show|print|tell|give|leak|dump|share)\b.{0,30}\b(your|the (server|backend|app|system)s?)\b.{0,20}\b(api ?keys?|secrets?|credentials|tokens?|passwords?|env(ironment)? variables?|database|source code)\b",
    r"\brepeat (the )?(words|text|everything|all|the above|what)\b.{0,25}\b(above|before|prior|start|begin)",
    r"\b(system|developer) (prompt|message|override|instruction)\b.{0,10}:",
)]
_MARKERS = re.compile(r"<\|?\s*(im_start|im_end|system|endoftext)\s*\|?>|\[/?\s*(inst|system)\s*\]|^\s*(system|developer|assistant)\s*:|#{2,}\s*system", re.I)
_SQUASHED = (
    "ignorepreviousinstructions", "ignoreallpreviousinstructions", "ignoreallinstructions", "ignoreyourinstructions",
    "ignoreyourrules", "disregardpreviousinstructions", "disregardallinstructions", "forgetyourinstructions",
    "forgetpreviousinstructions", "forgeteverythingabove", "revealyoursystemprompt", "showyoursystemprompt",
    "printyoursystemprompt", "repeatyoursystemprompt", "whatisyoursystemprompt", "yoursysteminstructions",
    "doanythingnow", "developermodeenabled", "enterdevelopermode", "youarenowdan", "actasdan", "jailbreak",
)
_B64 = re.compile(r"[A-Za-z0-9+/]{32,}={0,2}")


def _spaced_form(text: str) -> str:
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c)).translate(_LEET)
    t = re.sub(r"[^a-z0-9]+", " ", t).strip()
    return _SPACED.sub(lambda m: m.group(0).replace(" ", ""), t)


def _check(text: str) -> str | None:
    spaced = _spaced_form(text)
    if _MARKERS.search(text):
        return "role_markers"
    if any(p.search(spaced) for p in _PATTERNS):
        return "injection_pattern"
    squashed = re.sub(r"[^a-z]+", "", spaced)
    if any(s in squashed for s in _SQUASHED):
        return "injection_obfuscated"
    return None


def detect_injection(user_texts: list[str]) -> str | None:
    """Reason code if the latest user message (alone, or combined with the previous two) looks like an injection attempt."""
    if not user_texts:
        return None
    last = user_texts[-1]
    reason = _check(last)
    if reason:
        return reason
    for blob in _B64.findall(last)[:3]:
        try:
            decoded = base64.b64decode(blob + "=" * (-len(blob) % 4), validate=False).decode("utf-8", "ignore")
        except Exception:  # noqa: BLE001
            continue
        if decoded and _check(decoded):
            return "injection_base64"
    if len(user_texts) > 1 and _check(" ".join(user_texts[-3:])):
        return "injection_split"
    return None


# --------------------------------------------------------------------------- redaction
_KEY = re.compile(
    r"\b(?:sk-[A-Za-z0-9_\-]{10,}|AKIA[0-9A-Z]{12,}|bedrock-api-key[\w\-=]*|eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*|(?:ghp|gho|xox[bp])[-_][A-Za-z0-9_\-]{10,})"
    r"|\bbearer\s+[A-Za-z0-9._\-~+/]{8,}=*",
    re.I,
)
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){13,19}(?![\w-])")
_CODE = re.compile(r"\b((?:verification |security |login )?(?:code|otp|pin)\b(?:\W|\bis\b|\bwas\b|\bare\b){0,15})\d{6}\b", re.I)
_PHONE = re.compile(r"(?<![\w.])\+?\d[\d\s().\-]{7,}\d(?!\w)")


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def redact(text: str) -> tuple[str, bool]:
    """Replace secrets and PII with [redacted]. Returns (text, shared_credentials)."""
    secret = False

    def key_sub(_m: re.Match) -> str:
        nonlocal secret
        secret = True
        return "[redacted]"

    def card_sub(m: re.Match) -> str:
        nonlocal secret
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            secret = True
            return "[redacted]"
        return m.group(0)

    def code_sub(m: re.Match) -> str:
        nonlocal secret
        secret = True
        return m.group(1) + "[redacted]"

    def phone_sub(m: re.Match) -> str:
        return "[redacted]" if 9 <= len(re.sub(r"\D", "", m.group(0))) <= 15 else m.group(0)

    text = _KEY.sub(key_sub, text)
    text = _EMAIL.sub("[redacted]", text)
    text = _CARD.sub(card_sub, text)
    text = _CODE.sub(code_sub, text)
    return _PHONE.sub(phone_sub, text), secret


# --------------------------------------------------------------------------- history
@dataclass
class Prepared:
    messages: list[dict]  # sanitised {"role","content"} turns, oldest first
    user_texts: list[str]  # normalised (pre-redaction) user turns, for detection
    secret_shared: bool = False
    chars: int = 0


def prepare_history(messages: list[dict], *, forged_markers: tuple[str, ...] = (), budget: int = MAX_TOTAL, max_turns: int = 12) -> Prepared:
    """Normalise, redact and truncate each turn, drop forged/empty assistant turns, keep the newest turns that fit the budget."""
    kept: list[dict] = []
    users: list[str] = []
    secret = False
    total = 0
    for m in reversed(messages):
        text = normalize(m.get("content", ""))
        is_user = m.get("role") == "user"
        if not text:
            if is_user and not kept:
                break
            continue
        if not is_user and (_MARKERS.search(text) or any(mk and mk.lower() in text.lower() for mk in forged_markers)):
            continue
        clean, flagged = redact(text)
        if kept and (total + len(clean) > budget or len(kept) >= max_turns):
            break
        secret = secret or (flagged and is_user)
        total += len(clean)
        kept.append({"role": "user" if is_user else "assistant", "content": clean})
        if is_user:
            users.append(text)
    kept.reverse()
    users.reverse()
    return Prepared(kept, users, secret, total)


# --------------------------------------------------------------------------- output guard
_OUT_SECRET = re.compile(r"sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|bedrock-api-key|eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.", re.I)
_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]+)\]\(\s*https?://[^)]*\)", re.I)
_BARE = re.compile(r"https?://[^\s)\]>]+", re.I)
_TAG = re.compile(r"</?[A-Za-z][^>]{0,200}>")
_OPEN = re.compile(r"!?\[|<|https?://", re.I)


def sanitize_markdown(text: str) -> str:
    text = _IMG.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _BARE.sub("", text)
    return _TAG.sub("", text)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower())


@dataclass
class OutputGuard:
    """Rolling filter: feed() returns text that is safe to emit now; `tripped` is set when the output must be replaced."""

    canary: str = ""
    shingles: frozenset[str] = frozenset()
    pending: str = ""
    tripped: str | None = None
    emitted: int = 0

    @staticmethod
    def shingles_of(prompt: str) -> frozenset[str]:
        flat = _flat(prompt)
        return frozenset(flat[i : i + SHINGLE] for i in range(0, max(1, len(flat) - SHINGLE + 1)))

    def _violation(self, text: str) -> str | None:
        if self.canary and self.canary.lower() in text.lower():
            return "canary"
        if _OUT_SECRET.search(text):
            return "secret"
        flat = _flat(text)
        if self.shingles and len(flat) >= SHINGLE and any(flat[i : i + SHINGLE] in self.shingles for i in range(len(flat) - SHINGLE + 1)):
            return "prompt_leak"
        return None

    def _cut(self, end: int) -> int:
        """Largest cut <= end that does not split an open Markdown/HTML/URL construct."""
        if end > 0 and self.pending[end - 1 : end] == "!":
            end -= 1
        last = None
        for m in _OPEN.finditer(self.pending, 0, end):
            last = m
        if last is not None and end - last.start() < 400:
            seg, tok = self.pending[last.start() : end], last.group(0)
            if tok.startswith(("[", "![")):
                open_ = "]" not in seg or seg.endswith("]") or ("](" in seg and ")" not in seg.split("](", 1)[1])
            elif tok == "<":
                open_ = ">" not in seg
            else:
                open_ = not re.search(r"\s", seg)
            if open_:
                return last.start()
        return end

    def feed(self, chunk: str) -> str:
        if self.tripped:
            return ""
        self.pending += chunk
        self.tripped = self._violation(self.pending)
        if self.tripped:
            self.pending = ""
            return ""
        # sanitise everything that is not inside an unfinished construct, then emit all but the held-back tail
        safe_end = self._cut(len(self.pending))
        head = sanitize_markdown(self.pending[:safe_end])
        self.pending = head + self.pending[safe_end:]
        cut = self._cut(min(len(head), len(self.pending) - HOLD))
        if cut <= 0:
            return ""
        out, self.pending = self.pending[:cut], self.pending[cut:]
        self.emitted += len(out)
        return out

    def finish(self) -> str:
        if self.tripped:
            return ""
        self.tripped = self._violation(self.pending)
        out = "" if self.tripped else sanitize_markdown(self.pending)
        self.pending = ""
        self.emitted += len(out)
        return out
