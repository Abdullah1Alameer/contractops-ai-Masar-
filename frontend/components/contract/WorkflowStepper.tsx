"use client";
import { useI18n } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const STEPS = [
  { id: "draft", key: "stepper.draft", stages: ["draft", "negotiation"] },
  { id: "review", key: "stepper.review", stages: ["client_review", "awaiting_client"] },
  { id: "negotiation", key: "stepper.negotiation", stages: ["negotiation"] },
  { id: "approval", key: "stepper.approval", stages: ["internal_review"] },
  { id: "signature", key: "stepper.signature", stages: ["ready_to_sign", "awaiting_signature", "partially_signed", "approved"] },
  { id: "completed", key: "stepper.completed", stages: ["active", "signed", "completed"] },
] as const;

function stepIndex(stage: string | null | undefined) {
  const s = stage ?? "negotiation";
  for (let i = 0; i < STEPS.length; i++) {
    if (STEPS[i].stages.includes(s as never)) return i;
  }
  if (s === "draft") return 0;
  return 1;
}

export default function WorkflowStepper({ stage }: { stage?: string | null }) {
  const { t } = useI18n();
  const current = stepIndex(stage);

  return (
    <ol className="flex flex-wrap items-center gap-2 md:gap-0">
      {STEPS.map((step, i) => {
        const done = i < current;
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
