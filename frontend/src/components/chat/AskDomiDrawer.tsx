"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useNoMotion } from "@/lib/use-no-motion";
import { ChatCircleDots } from "@phosphor-icons/react";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { useChat } from "@/state/chat";

/**
 * "Ask Domi" for pages without an inline chat panel (detail, compare, affordability, and the
 * Explore grid view): a floating button that opens the same conversation in a slide-over.
 */
export function AskDomiDrawer() {
  const chat = useChat();
  const pathname = usePathname();
  const reduce = useNoMotion();
  const hidden = pathname === "/" || pathname === "/affordability" || chat.inlineChat;

  // Escape closes
  useEffect(() => {
    if (!chat.drawerOpen) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && chat.closeDrawer();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [chat]);

  if (hidden) return null;

  return (
    <>
      {!chat.drawerOpen && (
        <button
          type="button"
          onClick={chat.openDrawer}
          className="fixed bottom-5 right-5 z-[var(--z-fab,35)] inline-flex h-13 items-center gap-2 rounded-full bg-primary px-5 py-3.5 text-[14px] font-medium text-on-primary shadow-lift transition-[background-color,transform] hover:bg-primary-hover active:scale-[0.97]"
        >
          <ChatCircleDots size={20} aria-hidden /> Ask Domi
        </button>
      )}
      <AnimatePresence>
        {chat.drawerOpen && (
          <>
            <motion.div
              key="scrim"
              className="fixed inset-0 z-[var(--z-drawer,50)] bg-ink/30"
              initial={reduce ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={chat.closeDrawer}
              aria-hidden
            />
            <motion.div
              key="panel"
              role="dialog"
              aria-modal="true"
              aria-label="Ask Domi"
              className="fixed inset-x-0 bottom-0 z-[calc(var(--z-drawer,50)+1)] flex h-[85dvh] flex-col overflow-hidden rounded-t-[24px] border border-line bg-surface shadow-lift sm:inset-y-0 sm:left-auto sm:right-0 sm:h-auto sm:w-[440px] sm:rounded-none sm:rounded-l-[24px]"
              initial={reduce ? false : { y: "8%", opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              exit={{ y: "8%", opacity: 0 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <ChatPanel variant="drawer" onClose={chat.closeDrawer} className="h-full" />
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
