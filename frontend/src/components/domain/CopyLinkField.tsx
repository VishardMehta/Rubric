import { useState } from "react";
import { Button } from "../primitives";
import { useToast } from "../feedback";
import "./domain.css";

interface CopyLinkFieldProps {
  /** The full URL. Shown as-is, so it is what gets pasted. */
  url: string;
  /** Confirmed in a toast after copying. `Application link copied`. */
  toastMessage: string;
  /** Sits under the field. The interview link's caveat goes here. */
  help?: string;
}

/**
 * screens.md sections 2 and 4.
 *
 * A read-only field showing the link with a copy control beside it. The
 * URL is displayed in full rather than shortened: HR pastes this into an
 * email to a candidate, and a truncated link that cannot be verified by
 * eye before sending is worse than a long one.
 *
 * `navigator.clipboard` needs a secure context. localhost counts as one,
 * so it works for the demo, but the fallback still matters because the
 * API also rejects a call made without a user gesture in some browsers.
 */
export function CopyLinkField({ url, toastMessage, help }: CopyLinkFieldProps) {
  const toast = useToast();
  const [failed, setFailed] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(url);
      setFailed(false);
      toast.show(toastMessage);
    } catch {
      // Selecting the text is the recovery: the link is already on screen
      // in full, so the candidate's link is never actually unreachable.
      setFailed(true);
    }
  }

  return (
    <div className="rb-copylink">
      <div className="rb-copylink__row">
        <input
          className="rb-input rb-copylink__input text-mono"
          value={url}
          readOnly
          onFocus={(event) => event.currentTarget.select()}
          aria-label="Link"
        />
        <Button onClick={handleCopy}>Copy</Button>
      </div>
      {(help || failed) && (
        <p className={`rb-copylink__help${failed ? " rb-copylink__help--failed" : ""}`}>
          {failed ? "Your browser blocked the copy. Select the link above and copy it." : help}
        </p>
      )}
    </div>
  );
}
