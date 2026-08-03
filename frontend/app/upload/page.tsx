"use client";
import { useRef, useState } from "react";
import { useRouter } from "next/navigation";

import UnsupportedContractWarning from "@/components/UnsupportedContractWarning";
import { useToast } from "@/components/feedback/ToastProvider";
import Button from "@/components/ui/Button";
import { Card, CardBody } from "@/components/ui/Card";
import { api, ApiError, uploadContract, type ExtractResult } from "@/lib/api";
import { useI18n, type TKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Phase = "idle" | "uploading" | "extracting";

const ERROR_KEYS: Record<string, TKey> = {
  scanned_pdf_not_supported: "upload.err.scanned",
  unsupported_type: "upload.err.type",
  file_too_large: "upload.err.size",
  corrupted_file: "upload.err.corrupted",
  ai_failed: "upload.err.ai",
};

type Blocked = { category: string; confidence?: number; message?: string };

export default function UploadPage() {
  const { t } = useI18n();
  const toast = useToast();
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [errorKey, setErrorKey] = useState<TKey | null>(null);
  const [dragging, setDragging] = useState(false);
  const [blocked, setBlocked] = useState<Blocked | null>(null);

  const pick = (f: File | undefined | null) => {
    setErrorKey(null);
    setBlocked(null);
    if (!f) return;
    if (!/\.(pdf|docx)$/i.test(f.name)) {
      setErrorKey("upload.err.type");
      toast.warning(t("upload.err.type"));
      return;
    }
    if (f.size > 20 * 1024 * 1024) {
      setErrorKey("upload.err.size");
      toast.warning(t("upload.err.size"));
      return;
    }
    setFile(f);
  };

  const submit = async () => {
    if (!file || phase !== "idle") return;
    setErrorKey(null);
    setBlocked(null);
    try {
      setPhase("uploading");
      const { id } = await uploadContract(file);
      setPhase("extracting");
      const result = await api<ExtractResult>(`/api/contracts/${id}/extract`, { method: "POST" });
      if (result.supported === false) {
        setPhase("idle");
        setBlocked({
          category: result.contract_category ?? "Unknown",
          confidence: result.confidence,
          message: result.message,
        });
        setFile(null);
        return;
      }
      toast.success(t("toast.uploadSuccess"));
      router.push(`/contracts/${id}`);
    } catch (e) {
      setPhase("idle");
      const code = e instanceof ApiError ? e.code : "unknown";
      const key = ERROR_KEYS[code] ?? "common.error";
      setErrorKey(key);
      toast.error(t(key));
    }
  };

  if (blocked) {
    return (
      <div className="space-y-4">
        <UnsupportedContractWarning
          category={blocked.category}
          message={blocked.message}
          confidence={blocked.confidence}
        />
        <div className="mx-auto max-w-2xl">
          <Button variant="secondary" onClick={() => setBlocked(null)}>
            {t("upload.tryAnother")}
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 motion-safe:animate-fadeIn">
      <h1 className="text-2xl font-bold text-gray-900 md:text-3xl">{t("upload.title")}</h1>

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
          "flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed bg-white p-10 text-center motion-safe:transition-all",
          dragging ? "scale-[1.01] border-brand-600 bg-brand-50 shadow-cardHover" : "border-gray-300"
        )}
      >
        <p className="text-gray-600">
          {t("upload.drop")}{" "}
          <button type="button" className="font-semibold text-brand-700 underline focus-visible:focus-ring" onClick={() => inputRef.current?.click()}>
            {t("upload.browse")}
          </button>
        </p>
        <p className="text-sm text-gray-400">{t("upload.hint")}</p>
        {file && <p className="mt-2 rounded-md bg-muted-100 px-3 py-1 text-sm font-medium">{file.name}</p>}
        <input ref={inputRef} type="file" accept=".pdf,.docx" hidden onChange={(e) => pick(e.target.files?.[0])} />
      </div>

      <Card>
        <CardBody className="grid gap-4">
          <Button onClick={submit} disabled={!file || phase !== "idle"} loading={phase !== "idle"} variant="primary" size="lg">
            {phase === "idle" ? t("upload.submit") : phase === "uploading" ? t("upload.uploading") : t("upload.extracting")}
          </Button>
          {phase === "extracting" && (
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted-100">
              <div className="h-full w-1/2 motion-safe:animate-pulse rounded-full bg-brand-600" />
            </div>
          )}
          {errorKey && <p className="rounded-md bg-danger-50 px-3 py-2 text-sm text-danger-700">{t(errorKey)}</p>}
        </CardBody>
      </Card>
    </div>
  );
}
