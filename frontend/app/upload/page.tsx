"use client";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api, ApiError, uploadContract } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import type { ContractListItem } from "@/lib/types";
import { cn } from "@/lib/utils";

type Phase = "idle" | "uploading" | "extracting";

const ERROR_KEYS: Record<string, TKey> = {
  scanned_pdf_not_supported: "upload.err.scanned",
  unsupported_type: "upload.err.type",
  file_too_large: "upload.err.size",
  corrupted_file: "upload.err.corrupted",
  ai_failed: "upload.err.ai",
};

export default function UploadPage() {
  const { t } = useI18n();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [type, setType] = useState<"main" | "subcontract">("main");
  const [parentId, setParentId] = useState<string>("");
  const [mains, setMains] = useState<ContractListItem[]>([]);
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorKey, setErrorKey] = useState<TKey | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    api<ContractListItem[]>("/api/contracts")
      .then((all) => setMains(all.filter((c) => c.type === "main")))
      .catch(() => {});
  }, []);

  const pick = (f: File | undefined | null) => {
    setErrorKey(null);
    if (!f) return;
    if (!/\.(pdf|docx)$/i.test(f.name)) return setErrorKey("upload.err.type");
    if (f.size > 20 * 1024 * 1024) return setErrorKey("upload.err.size");
    setFile(f);
  };

  const submit = async () => {
    if (!file || phase !== "idle") return;
    setErrorKey(null);
    try {
      setPhase("uploading");
      const { id } = await uploadContract(file, type, type === "subcontract" && parentId ? parentId : undefined);
      setPhase("extracting");
      await api(`/api/contracts/${id}/extract`, { method: "POST" });
      router.push(`/contracts/${id}`);
    } catch (e) {
      setPhase("idle");
      const code = e instanceof ApiError ? e.code : "unknown";
      setErrorKey(ERROR_KEYS[code] ?? "common.error");
    }
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-6 text-2xl font-bold">{t("upload.title")}</h1>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          pick(e.dataTransfer.files?.[0]);
        }}
        className={cn(
          "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed bg-white p-10 text-center",
          dragging ? "border-brand-600 bg-brand-50" : "border-gray-300"
        )}
      >
        <p className="text-gray-600">
          {t("upload.drop")}{" "}
          <button className="font-semibold text-brand-700 underline" onClick={() => inputRef.current?.click()}>
            {t("upload.browse")}
          </button>
        </p>
        <p className="text-sm text-gray-400">{t("upload.hint")}</p>
        {file && <p className="mt-2 rounded-md bg-gray-100 px-3 py-1 text-sm font-medium">{file.name}</p>}
        <input ref={inputRef} type="file" accept=".pdf,.docx" hidden onChange={(e) => pick(e.target.files?.[0])} />
      </div>

      <div className="mt-6 grid gap-4 rounded-xl border bg-white p-6">
        <label className="grid gap-1 text-sm font-medium text-gray-700">
          {t("upload.type")}
          <select
            className="rounded-md border px-3 py-2"
            value={type}
            onChange={(e) => setType(e.target.value as any)}
          >
            <option value="main">{t("type.main")}</option>
            <option value="subcontract">{t("type.subcontract")}</option>
          </select>
        </label>
        {type === "subcontract" && (
          <label className="grid gap-1 text-sm font-medium text-gray-700">
            {t("upload.parent")}
            <select className="rounded-md border px-3 py-2" value={parentId} onChange={(e) => setParentId(e.target.value)}>
              <option value="">{t("upload.parentNone")}</option>
              {mains.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          onClick={submit}
          disabled={!file || phase !== "idle"}
          className="rounded-lg bg-brand-600 px-4 py-2.5 font-semibold text-white hover:bg-brand-700 disabled:opacity-50"
        >
          {phase === "idle" ? t("upload.submit") : phase === "uploading" ? t("upload.uploading") : t("upload.extracting")}
        </button>
        {phase === "extracting" && (
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-100">
            <div className="h-full w-1/2 animate-pulse rounded-full bg-brand-600" />
          </div>
        )}
        {errorKey && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{t(errorKey)}</p>}
      </div>
    </div>
  );
}
