import request from "@/axios/api";
import type { ToolRequest } from "@/models/models";
export default {
  // 患者信息管理
  submitNotes: (data: any) => {
    return request("/mas/patients/notes", "POST", data, false);
  },
  getPatientInfo: () => {
    return request("/mas/patients/info", "GET", null, false);
  },
  getPatientGoals: () => {
    return request("/mas/patients/goals", "GET", null, false);
  },
  getNextReviewTime: () => {
    return request("/mas/patients/next_review_time", "GET", null, false);
  },
  getCoachDashboard: (window?: "5" | "10" | "all") => {
    return request("/mas/coach/dashboard", "GET", window ? { window } : null, false);
  },
  postCoachStateEvent: (data: {
    event_type: string;
    goal_index?: number;
    note?: string;
    message?: string;
  }) => {
    return request("/mas/coach/goals/state-event", "POST", data, false);
  },
  executeWorkflowTool: (data: {
    tool_request: ToolRequest;
    confirmed: true;
    turn_index: number;
  }) => {
    return request("/mas/workflow/tools/execute", "POST", data, false);
  },

  // 会话管理
  triggerSession: (data?: any) => {
    return request("/mas/sessions/trigger", "POST", data || {}, false);
  },
  sendMasMessage: (data: any) => {
    return request("/mas/sessions/message", "POST", data, false);
  },
  getCurrentSession: () => {
    return request("/mas/sessions/current", "GET", null, false);
  },
  getConversationHistory: () => {
    return request("/mas/sessions/history", "GET", null, false);
  },
  getSessionSummaries: () => {
    return request("/mas/sessions/summaries", "GET", null, false);
  },
  
  // 预约管理
  createSchedule: (data: any) => {
    return request("/mas/schedules", "POST", data, false);
  },
  
  // 健康检查
  checkHealth: () => {
    return request("/mas/health", "GET", null, false);
  },
};
