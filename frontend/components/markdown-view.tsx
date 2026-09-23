/**
 * Karanlık tema Markdown görüntüleyici (Gemini raporları için).
 */

type MarkdownViewProps = {
  content: string;
  className?: string;
};

/**
 * Satır satır basit Markdown'ı React elemanlarına çevirir.
 * Destek: # ## ###, listeler, > alıntı, paragraflar.
 */
export function MarkdownView({ content, className }: MarkdownViewProps) {
  const blocks = content.replace(/\r\n/g, "\n").split(/\n{2,}/);

  return (
    <div className={className}>
      {blocks.map((block, index) => {
        const trimmed = block.trim();
        if (!trimmed) return null;

        if (trimmed.startsWith("### ")) {
          return (
            <h4 key={index} className="mt-4 mb-2 font-mono text-xs font-semibold tracking-wide text-zinc-200">
              {trimmed.slice(4)}
            </h4>
          );
        }
        if (trimmed.startsWith("## ")) {
          return (
            <h3 key={index} className="mt-4 mb-2 text-sm font-semibold text-zinc-100">
              {trimmed.slice(3)}
            </h3>
          );
        }
        if (trimmed.startsWith("# ")) {
          return (
            <h2 key={index} className="mt-3 mb-2 text-base font-semibold text-zinc-50">
              {trimmed.slice(2)}
            </h2>
          );
        }

        if (trimmed.startsWith("> ")) {
          return (
            <blockquote
              key={index}
              className="my-3 border-l-2 border-zinc-700 pl-3 font-mono text-xs text-zinc-400 italic"
            >
              {trimmed
                .split("\n")
                .map((line) => line.replace(/^>\s?/, ""))
                .join(" ")}
            </blockquote>
          );
        }

        const lines = trimmed.split("\n");
        const isList = lines.every((line) => /^[-*]\s+/.test(line.trim()) || line.trim() === "");
        if (isList) {
          return (
            <ul key={index} className="my-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-zinc-300">
              {lines
                .filter((line) => line.trim())
                .map((line, lineIndex) => (
                  <li key={lineIndex}>{line.replace(/^[-*]\s+/, "")}</li>
                ))}
            </ul>
          );
        }

        return (
          <p key={index} className="my-2 text-sm leading-relaxed text-zinc-300">
            {lines.join(" ")}
          </p>
        );
      })}
    </div>
  );
}
