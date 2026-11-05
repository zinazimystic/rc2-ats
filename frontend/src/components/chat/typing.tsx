export function Typing() {
  return (
    <span className="inline-flex items-center gap-1 py-1.5" role="status" aria-label="Assistant is typing">
      {[0, 1, 2].map((i) => (
        <span key={i} className="rc-dot size-1.5 rounded-full bg-muted-foreground/70" style={{ animationDelay: `${i * 160}ms` }} />
      ))}
    </span>
  );
}
