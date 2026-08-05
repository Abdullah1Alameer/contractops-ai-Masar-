"use client";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

// Canonical business-lifecycle stages only (docs/contract-lifecycle-policy.md
// §3/§9). Each stage belongs to exactly one step — no stage may appear in two
// entries, or the first (wrong) match wins and silently mis-highlights the
// stepper. `approved`/`awaiting_signature` are read-compatibility aliases for
// pre-canonical rows (see backend `LEGACY_STAGE_MAP`), not new stages.
const STEPS = [
  { id: "draft", key: "stepper.draft", stages: ["draft", "ready_for_client"] },
  { id: "review", key: "stepper.review", stages: ["client_review"] },
  { id: "negotiation", key: "stepper.negotiation", stages: ["negotiation"] },
  { id: "approval", key: "stepper.approval", stages: ["internal_review"] },
  { id: "signature", key: "stepper.signature", stages: ["ready_to_sign", "partially_signed", "approved", "awaiting_signature"] },
  { id: "completed", key: "stepper.completed", stages: ["signed", "active", "completed"] },
] as const;

const TERMINAL_STAGES = new Set(["rejected", "cancelled", "terminated"]);

/** -1 means "no step to highlight" — an unset, terminal, or unrecognized
 * stage. Never guess a stage; a stale/absent value must not silently render
 * as if the contract were still early in the pipeline. */
function stepIndex(stage: string | null | undefined): number {
  if (!stage || TERMINAL_STAGES.has(stage)) return -1;
  for (let i = 0; i < STEPS.length; i++) {
    if ((STEPS[i].stages as readonly string[]).includes(stage)) return i;
  }
  return -1;
}

export default function WorkflowStepper({ stage }: { stage?: string | null }) {
  const { t } = useI18n();
  const current = stepIndex(stage);

  if (stage && TERMINAL_STAGES.has(stage)) {
    return (
      <p className="text-sm font-semibold text-danger-700">
        {t(`stage.${stage}` as import("@/lib/i18n").TKey)}
      </p>
    );
  }

  return (
    <ol className="flex flex-wrap items-center gap-2 md:gap-0">
      {STEPS.map((step, i) => {
        const done = current >= 0 && i < current;
        const active = i === current;
        return (
          <li key={step.id} className="flex items-center">
            <div
              className={cn(
                "flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-semibold md:text-sm",
                active && "bg-brand-600 text-white",
                done && !active && "bg-brand-50 text-brand-800",
                !done && !active && "bg-gray-100 text-gray-500"
              )}
            >
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded-full text-xs",
                  active && "bg-white/20",
                  done && !active && "bg-brand-100 text-brand-800",
                  !done && !active && "bg-gray-200 text-gray-600"
                )}
              >
                {i + 1}
              </span>
              {t(step.key)}
            </div>
            {i < STEPS.length - 1 && (
              <span className="mx-1 hidden h-px w-6 bg-gray-200 md:inline-block" aria-hidden />
            )}
          </li>
        );
      })}
    </ol>
  );
}
