"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, ChevronDown, Send } from "lucide-react";
import { sampleTask } from "@/lib/sample-task";
import { createTask } from "@/lib/api";

const analysisModels = [
  { id: "deep-analysis", label: "深度分析模型", description: "复杂归因与多表推理" },
  { id: "fast-sql", label: "快速 SQL 模型", description: "快速生成查询与预览" },
  { id: "schema-reasoning", label: "Schema 推理模型", description: "表关联与字段理解优先" }
] as const;

export function PromptTaskComposer() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [selectedModel, setSelectedModel] = useState<(typeof analysisModels)[number]>(analysisModels[0]);
  const [isModelPickerOpen, setIsModelPickerOpen] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const submittedPrompt = formData.get("q");
    const trimmedPrompt = typeof submittedPrompt === "string" ? submittedPrompt.trim() : "";

    if (!trimmedPrompt) {
      return;
    }

    setIsSubmitting(true);
    try {
      const task = await createTask(trimmedPrompt, selectedModel.id);
      router.push(`/tasks/${task.id}?run=1`);
    } catch (error) {
      console.error(error);
      router.push(`/tasks/${sampleTask.id}?q=${encodeURIComponent(trimmedPrompt)}&model=${selectedModel.id}&offline=1`);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="prompt-launcher">
      <form
        action={`/tasks/${sampleTask.id}`}
        className="prompt-composer"
        id="analysis-prompt-form"
        method="get"
        onSubmit={handleSubmit}
      >
        <input
          aria-label="输入分析提示词"
          name="q"
          placeholder="输入分析问题，Agent 会沉淀口径、Schema 证据、SQL、自修复记录、图表洞察和追问分支。"
          required
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
        />
        <button
          aria-label="发送并创建任务"
          className="prompt-send"
          data-empty={!prompt.trim() || isSubmitting}
          disabled={isSubmitting}
          type="submit"
        >
          <Send size={18} />
        </button>
      </form>
      <input form="analysis-prompt-form" name="model" type="hidden" value={selectedModel.id} />
      <div className="model-picker" onBlur={() => setIsModelPickerOpen(false)}>
        <span className="model-picker-label">模型</span>
        <button
          aria-expanded={isModelPickerOpen}
          aria-haspopup="listbox"
          className="model-picker-trigger"
          onClick={() => setIsModelPickerOpen((current) => !current)}
          type="button"
        >
          {selectedModel.label}
          <ChevronDown className="model-picker-chevron" size={14} />
        </button>
        {isModelPickerOpen ? (
          <div aria-label="选择分析模型" className="model-picker-menu" role="listbox">
            {analysisModels.map((model) => (
              <button
                aria-selected={model.id === selectedModel.id}
                className="model-option"
                key={model.id}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  setSelectedModel(model);
                  setIsModelPickerOpen(false);
                }}
                role="option"
                type="button"
              >
                <span>
                  <strong>{model.label}</strong>
                  <small>{model.description}</small>
                </span>
                {model.id === selectedModel.id ? <Check size={15} /> : null}
              </button>
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}
