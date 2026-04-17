import { describe, expect, it } from "vitest";
import { dictionaries, getDictionary } from "./i18n";

describe("i18n dictionaries", () => {
  it("defaults to Chinese while keeping technical terms readable", () => {
    const zh = getDictionary("zh");

    expect(zh.nav.tasks).toBe("分析任务");
    expect(zh.terms.schema).toBe("表结构 Schema");
    expect(zh.terms.joinPath).toBe("关联路径 Join Path");
  });

  it("contains matching English keys for top-level navigation", () => {
    expect(Object.keys(dictionaries.zh.nav)).toEqual(Object.keys(dictionaries.en.nav));
  });
});
