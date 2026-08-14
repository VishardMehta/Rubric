import type { ReactNode } from "react";
import "./layout.css";

interface SplitProps {
  /** `5:7` is Candidate Detail: scores left, evidence right. */
  ratio?: "5:7" | "1:1";
  left: ReactNode;
  right: ReactNode;
}

/** Two columns that become a stack under 1180px (design-system.md section 20). */
export function Split({ ratio = "5:7", left, right }: SplitProps) {
  return (
    <div className={`rb-split${ratio === "1:1" ? " rb-split--even" : ""}`}>
      <div>{left}</div>
      <div>{right}</div>
    </div>
  );
}
