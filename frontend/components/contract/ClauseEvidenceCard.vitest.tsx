/** @vitest-environment jsdom */
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import ClauseEvidenceCard from "@/components/contract/ClauseEvidenceCard";
import { I18nProvider } from "@/lib/i18n";

afterEach(cleanup);

function renderCard(props: Partial<React.ComponentProps<typeof ClauseEvidenceCard>> = {}) {
  return render(
    <I18nProvider>
      <ClauseEvidenceCard
        quote="يلتزم الطرف الثاني بتقديم إشعار كتابي خلال سبعة أيام من اكتشاف أي عيب."
        clauseRef="9.1"
        page={5}
        confidence={0.82}
        verified
        reasoning="الحدث المُحفِّز: اكتشاف عيب"
        metadata={[{ label: "obligation.party", value: "المقاول" }]}
        onJump={vi.fn()}
        {...props}
      />
    </I18nProvider>
  );
}

describe("ClauseEvidenceCard — traceability block", () => {
  it("is collapsed by default and reveals the original clause, reasoning, and metadata on expand", async () => {
    renderCard();

    expect(screen.queryByText(/يلتزم الطرف الثاني/)).toBeNull();

    fireEvent.click(screen.getByText("عرض التفاصيل والمصدر"));

    expect(await screen.findByText(/يلتزم الطرف الثاني/)).toBeTruthy();
    expect(screen.getByText("الحدث المُحفِّز: اكتشاف عيب")).toBeTruthy();
    expect(screen.getByText("المقاول")).toBeTruthy();
    expect(screen.getByText("5")).toBeTruthy(); // page
    expect(screen.getByText("9.1")).toBeTruthy(); // clause ref
  });

  it("offers a jump-to-clause action only when the source is verified", async () => {
    const onJump = vi.fn();
    renderCard({ onJump, verified: true });
    fireEvent.click(screen.getByText("عرض التفاصيل والمصدر"));

    fireEvent.click(await screen.findByText("الانتقال إلى البند داخل المستند"));
    expect(onJump).toHaveBeenCalled();
  });

  it("shows an honest 'source unverified' badge instead of a jump action when not verified", async () => {
    renderCard({ verified: false });
    fireEvent.click(screen.getByText("عرض التفاصيل والمصدر"));

    expect(await screen.findByText("المصدر غير مؤكد")).toBeTruthy();
    expect(screen.queryByText("الانتقال إلى البند داخل المستند")).toBeNull();
  });

  it("shows a distinct message instead of fabricating a quote when none exists", async () => {
    renderCard({ quote: null });
    fireEvent.click(screen.getByText("عرض التفاصيل والمصدر"));

    expect(await screen.findByText("لا يتوفر نص أصلي مرتبط بهذا العنصر.")).toBeTruthy();
  });

  it("shows a distinct message instead of fabricating reasoning when none exists", async () => {
    renderCard({ reasoning: null });
    fireEvent.click(screen.getByText("عرض التفاصيل والمصدر"));

    expect(await screen.findByText("لم يُسجَّل تفسير آلي لسبب استخراج هذا العنصر.")).toBeTruthy();
  });

  it("honestly reports 'not scored' instead of a fake confidence for rule-based items (e.g. risk findings)", async () => {
    renderCard({ confidence: null });
    fireEvent.click(screen.getByText("عرض التفاصيل والمصدر"));

    expect(await screen.findByText("غير مقيَّم (نتيجة قاعدية وليست استخراجًا بالذكاء الاصطناعي)")).toBeTruthy();
  });
});
