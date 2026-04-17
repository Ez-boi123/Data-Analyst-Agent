import type { Locale } from "./types";

export const dictionaries = {
  zh: {
    nav: {
      tasks: "分析任务",
      dataSources: "数据源 / Schema",
      glossary: "业务词典",
      settings: "设置"
    },
    actions: {
      newTask: "新建分析",
      openWorkspace: "打开工作台",
      share: "分享",
      followUp: "继续追问"
    },
    terms: {
      schema: "表结构 Schema",
      joinPath: "关联路径 Join Path",
      sql: "SQL",
      agent: "Agent"
    }
  },
  en: {
    nav: {
      tasks: "Analysis Tasks",
      dataSources: "Data Sources / Schema",
      glossary: "Business Glossary",
      settings: "Settings"
    },
    actions: {
      newTask: "New Analysis",
      openWorkspace: "Open Workspace",
      share: "Share",
      followUp: "Follow Up"
    },
    terms: {
      schema: "Schema",
      joinPath: "Join Path",
      sql: "SQL",
      agent: "Agent"
    }
  }
} as const;

export function getDictionary(locale: Locale = "zh") {
  return dictionaries[locale] ?? dictionaries.zh;
}
