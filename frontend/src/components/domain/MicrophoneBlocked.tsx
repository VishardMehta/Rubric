import { Button } from "../primitives";
import "./domain.css";

/**
 * design-system.md section 17.
 *
 * Microphone permission denial gets its own treatment because it is the
 * single most likely failure in the candidate flow, and because the
 * generic error shape cannot carry recovery steps.
 *
 * The copy never blames the candidate and never mentions a permission API.
 * It says which control to click, in the place they will actually find it.
 */
export function MicrophoneBlocked() {
  return (
    <div className="rb-mic-blocked">
      <h1 className="text-title-2 rb-mic-blocked__title">Rubric needs your microphone</h1>
      <p className="text-body-lg rb-mic-blocked__body">
        The interview is answered by voice, so we need microphone access to
        continue.
      </p>
      <p className="text-body-lg rb-mic-blocked__body">
        Click the microphone icon in your browser's address bar and choose
        Allow, then reload.
      </p>
      <Button level="primary" size="large" onClick={() => window.location.reload()}>
        Reload and try again
      </Button>
    </div>
  );
}
