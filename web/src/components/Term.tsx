import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";

export interface TermProps {
  word: string;
  plain: string;
  example: string;
  defaultOpen?: boolean;
}

export function nextTermOpenState(currentOpen: boolean, key: string): boolean {
  if (key === "Escape") return false;
  if (key === "Enter" || key === " ") return !currentOpen;
  return currentOpen;
}

/**
 * Dotted-underline Feynman term button.
 * Opens a plain-words popover ("In plain words … / Like …").
 * Keyboard accessible; Escape or clicking outside closes it.
 */
export function Term({ word, plain, example, defaultOpen = false }: TermProps) {
  const [open, setOpen] = useState(defaultOpen);
  const wrapRef = useRef<HTMLSpanElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const popId = useId();

  useEffect(() => {
    if (!open || typeof document === "undefined") return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        buttonRef.current?.focus();
      }
    };
    const onPointer = (e: PointerEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("pointerdown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("pointerdown", onPointer);
    };
  }, [open]);

  const handleKeyDown = (e: ReactKeyboardEvent<HTMLButtonElement>) => {
    if (e.key === "Escape" && open) {
      e.preventDefault();
      setOpen(false);
    }
  };

  return (
    <span ref={wrapRef} className="relative inline-block">
      <button
        ref={buttonRef}
        type="button"
        aria-expanded={open}
        aria-controls={open ? popId : undefined}
        onClick={(e) => {
          e.stopPropagation();
          setOpen((v) => !v);
        }}
        onKeyDown={handleKeyDown}
        className="cursor-help border-b border-dotted border-muted bg-transparent p-0 font-[inherit] text-inherit leading-[inherit] hover:border-accent"
      >
        {word}
        <span className="sr-only"> (explain in plain words)</span>
      </button>
      {open && (
        <span
          id={popId}
          role="dialog"
          aria-label={`Explanation of ${word}`}
          onClick={(e) => e.stopPropagation()}
          className="absolute left-0 top-full z-50 mt-1.5 block w-72 rounded-xl border border-hairline bg-raised p-3.5 text-left text-xs leading-relaxed font-normal text-text shadow-xl"
        >
          <span className="mb-1 block text-sm font-semibold text-text">{word}</span>
          <span className="block text-text">
            <span className="font-medium text-muted">In plain words: </span>
            {plain}
          </span>
          {example && (
            <span className="mt-2 block rounded-lg bg-surface px-2.5 py-2 text-muted">
              <span className="font-semibold text-text">Like: </span>
              {example}
            </span>
          )}
        </span>
      )}
    </span>
  );
}
