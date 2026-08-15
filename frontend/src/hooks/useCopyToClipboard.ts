import { useCallback, useState } from "react";
import { useToast } from "../components/feedback";

/**
 * Copies text and confirms it in a toast.
 *
 * Shared by the two places a link is handed over: the full CopyLinkField,
 * which shows the URL, and the plain copy button in a page header. Both
 * need the same failure handling, and clipboard failure is not
 * hypothetical - `navigator.clipboard` requires a secure context and can
 * be refused outright by browser policy.
 *
 * `failed` is surfaced so the caller can tell the user to select the link
 * by hand. It is never a toast: a message that disappears after four
 * seconds is the wrong place for something the user has to act on.
 */
export function useCopyToClipboard(): {
  copy: (text: string, toastMessage: string) => Promise<void>;
  failed: boolean;
} {
  const toast = useToast();
  const [failed, setFailed] = useState(false);

  const copy = useCallback(
    async (text: string, toastMessage: string) => {
      try {
        await navigator.clipboard.writeText(text);
        setFailed(false);
        toast.show(toastMessage);
      } catch {
        setFailed(true);
      }
    },
    [toast],
  );

  return { copy, failed };
}
