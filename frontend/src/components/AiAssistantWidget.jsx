import { useState } from "react";
import AiChat from "./AiChat";
import { Icon } from "./icons";

export default function AiAssistantWidget() {
  const [open, setOpen] = useState(false);

  return (
    <>
      {open && (
        <div className="fixed bottom-24 right-6 z-50 flex h-[34rem] max-h-[calc(100vh-8rem)] w-[26rem] max-w-[calc(100vw-3rem)] flex-col overflow-hidden rounded-2xl border border-ink-200 bg-white shadow-2xl">
          <div className="flex items-center justify-between border-b border-ink-100 bg-ink-50 px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-accent-400 to-accent-600 text-white">
                <Icon.Sparkles width={15} height={15} />
              </div>
              <div>
                <p className="text-sm font-semibold leading-tight text-ink-900">AI Assistant</p>
                <p className="text-[11px] leading-tight text-ink-400">Ask about your CRM data</p>
              </div>
            </div>
            <button className="btn-ghost px-2 py-1" onClick={() => setOpen(false)} title="Close">
              <Icon.X width={18} height={18} />
            </button>
          </div>
          <div className="min-h-0 flex-1">
            <AiChat />
          </div>
        </div>
      )}

      <button
        onClick={() => setOpen((v) => !v)}
        className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-white shadow-lg transition hover:bg-brand-700"
        title={open ? "Close assistant" : "Ask the AI assistant"}
        aria-label="AI Assistant"
      >
        {open ? <Icon.X width={24} height={24} /> : <Icon.Chat width={24} height={24} />}
      </button>
    </>
  );
}
