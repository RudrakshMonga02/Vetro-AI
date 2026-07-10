import { Plus, Trash2, MessageSquare } from "lucide-react";

/**
 * Sidebar -- lists persisted conversations ("Investigation A/B/C...").
 * Pure presentational + event-emitting; ChatApp.jsx owns the actual
 * conversation list state and API calls, matching the same pattern
 * ChatInterface already uses (parent owns state, child renders + emits).
 */

function formatRelativeTime(isoString) {
  const then = new Date(isoString).getTime();
  const now = Date.now();
  const diffMin = Math.round((now - then) / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.round(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.round(diffHr / 24);
  return `${diffDay}d ago`;
}

export default function Sidebar({
  conversations,
  activeConversationId,
  onSelect,
  onCreate,
  onDelete,
}) {
  return (
    <div className="w-64 shrink-0 bg-[#0E1526] border-r border-[#2A3348] flex flex-col h-screen">
      <div className="px-4 py-4 border-b border-[#2A3348]">
        <button
          onClick={onCreate}
          className="w-full flex items-center justify-center gap-2 bg-[#D4A24C] text-[#0B1120]
                     rounded px-3 py-2 text-xs font-mono uppercase tracking-wider font-semibold
                     hover:bg-[#E0B15F] transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          New Investigation
        </button>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        {conversations.length === 0 && (
          <p className="text-xs text-[#4A5268] text-center mt-8 px-4 font-mono">
            No investigations yet
          </p>
        )}

        {conversations.map((conv) => {
          const isActive = conv.id === activeConversationId;
          return (
            <div
              key={conv.id}
              onClick={() => onSelect(conv.id)}
              className={`group flex items-center gap-2 px-4 py-2.5 cursor-pointer border-l-2 transition-colors
                ${isActive
                  ? "bg-[#151B2E] border-[#D4A24C]"
                  : "border-transparent hover:bg-[#151B2E]/60"}`}
            >
              <MessageSquare
                className={`w-3.5 h-3.5 shrink-0 ${isActive ? "text-[#D4A24C]" : "text-[#4A5268]"}`}
              />
              <div className="flex-1 min-w-0">
                <p
                  className={`text-xs truncate ${isActive ? "text-[#E4E7EC]" : "text-[#8B93A8]"}`}
                  title={conv.title}
                >
                  {conv.title}
                </p>
                <p className="text-[10px] text-[#4A5268] font-mono mt-0.5">
                  {formatRelativeTime(conv.updated_at)}
                </p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation(); // don't also trigger onSelect
                  onDelete(conv.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-[#4A5268] hover:text-[#B0503C]
                           transition-opacity shrink-0"
                title="Delete investigation"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
