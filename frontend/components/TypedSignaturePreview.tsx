"use client";

export default function TypedSignaturePreview({ value }: { value: string }) {
  return (
    <p
      className="min-h-[3rem] rounded border bg-white px-3 py-2 text-2xl text-gray-900"
      style={{ fontFamily: '"Segoe Script", "Snell Roundhand", "Apple Chancery", cursive' }}
    >
      {value || "—"}
    </p>
  );
}
