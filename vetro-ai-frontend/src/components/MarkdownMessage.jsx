import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * MarkdownMessage -- renders an assistant response as actual Markdown
 * instead of a flat <p> block. Custom component overrides keep every
 * element inside the existing "incident log" color palette (amber
 * accent #D4A24C, body text #C8CCD8, headings brighter #E4E7EC) rather
 * than react-markdown's default browser styles, so this doesn't look
 * like a bolted-on generic markdown viewer.
 *
 * Streaming note: this re-parses the full accumulated text on every
 * chunk while streaming. react-markdown tolerates incomplete/unclosed
 * markdown (e.g. a "**" that hasn't been closed yet mid-stream)
 * without throwing -- worst case it's briefly rendered as literal
 * text until the closing marker arrives a moment later. Not worth
 * engineering around for a chat UI where this resolves within
 * milliseconds of the stream continuing.
 */
export default function MarkdownMessage({ text }) {
  return (
    <div className="text-[#C8CCD8] mt-1 leading-relaxed text-sm space-y-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-[#E4E7EC] text-base font-semibold mt-3 mb-1 first:mt-0">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-[#E4E7EC] text-sm font-semibold mt-3 mb-1 first:mt-0 font-mono uppercase tracking-wide">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-[#E4E7EC] text-sm font-semibold mt-2 mb-1 first:mt-0">
              {children}
            </h3>
          ),
          p: ({ children }) => <p className="text-[#C8CCD8]">{children}</p>,
          strong: ({ children }) => (
            <strong className="text-[#D4A24C] font-semibold">{children}</strong>
          ),
          em: ({ children }) => <em className="text-[#E4E7EC] italic">{children}</em>,
          ul: ({ children }) => (
            <ul className="list-disc list-outside ml-4 space-y-0.5 marker:text-[#3A6B4C]">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal list-outside ml-4 space-y-0.5 marker:text-[#3A6B4C]">
              {children}
            </ol>
          ),
          li: ({ children }) => <li className="text-[#C8CCD8]">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-[#D4A24C] pl-3 my-2 text-[#A8AEC0] italic">
              {children}
            </blockquote>
          ),
          code: ({ inline, children }) =>
            inline ? (
              <code className="bg-[#161D2E] text-[#D4A24C] px-1 py-0.5 rounded text-xs font-mono">
                {children}
              </code>
            ) : (
              <code className="block bg-[#161D2E] text-[#C8CCD8] p-2 rounded text-xs font-mono overflow-x-auto">
                {children}
              </code>
            ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-2">
              <table className="border-collapse text-xs w-full">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-[#2A3348] px-2 py-1 text-left text-[#E4E7EC] font-mono uppercase text-[10px] tracking-wide bg-[#161D2E]">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-[#2A3348] px-2 py-1 text-[#C8CCD8]">{children}</td>
          ),
          a: ({ children, href }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              className="text-[#D4A24C] underline decoration-dotted hover:text-[#E4B968]"
            >
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
