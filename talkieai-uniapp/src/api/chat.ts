import request from "@/axios/api";
export default {
  sessionCreate: (data: any) => {
    return request("/sessions", "POST", data, true);
  },
  sessionMasCreate: () => {
    return request("/mas/sessions/create", "POST", {}, false);
  },
  /** 前端已不再使用：首页「Chat with Coach」改为 sessionMasList 仅打开已有会话；新一轮仅预约轮询 / New Session。 */
  sessionMasGetOrCreate: () => {
    return request("/mas/sessions/get-or-create", "GET", {}, false);
  },
  sessionMasList: () => {
    return request("/mas/sessions/list", "GET", {}, false);
  },
  sessionMasDeleteBulk: (data: { session_ids: string[] }) => {
    return request("/mas/sessions/delete-bulk", "POST", data, false);
  },
  sessionMasGetCurrent: () => {
    return request("/mas/sessions/current", "GET", {}, false);
  },
  sessionDefaultGet: (data: any) => {
    return request("/sessions/default", "GET", data, true);
  },
  sessionDetailsGet: (data: any) => {
    return request("/sessions/" + data.sessionId, "GET", data, true);
  },
  sessionInitGreeting: (sessionId: string) => {
    return request("/sessions/" + sessionId + "/greeting", "GET", {}, false);
  },
  sessionChatInvoke: (data: any) => {
    return request(`/sessions/${data.sessionId}/chat`, "POST", data, false);
  },
  transformText: (data: any) => {
    return request(
      `/sessions/${data.sessionId}/voice-translate`,
      "POST",
      data,
      false
    );
  },
  // 新增独立语音转文字接口
  standaloneVoiceTranslate: (data: any) => {
    return request(
      `/voice/translate`,
      "POST",
      data,
      false
    );
  },
  // 别名，保持兼容性
  standaloneTransformText: (data: any) => {
    return request(
      `/voice/translate`,
      "POST",
      data,
      false
    );
  },
  messagesLatestDelete: (sessionId: string) => {
    return request(
      `/sessions/${sessionId}/messages/latest`,
      "DELETE",
      null,
      false
    );
  },
  messagesAllDelete: (sessionId: string) => {
    return request(`/sessions/${sessionId}/messages`, "DELETE", null, false);
  },
  translateInvoke: (data: any) => {
    return request(
      `/messages/${data.message_id}/translate`,
      "POST",
      data,
      false
    );
  },
  messagePractice: (data: any) => {
    return request(
      `/messages/${data.message_id}/practice`,
      "POST",
      data,
      false
    );
  },
  speechContent: (data: any) => {
    return request("/message/speech-content", "POST", data, false);
  },
  speechDemo: (data: any) => {
    return request("/message/speech-demo", "POST", data, false);
  },
  grammarInvoke: (data: any) => {
    return request("/message/grammar", "POST", data, false);
  },
  pronunciationInvoke: (data: any) => {
    return request("/message/pronunciation", "POST", data, false);
  },
  translateSettingLanguage: (data: any) => {
    return request("/message/translate-setting-language", "POST", data, false);
  },
  translateSourceLanguage: (data: any) => {
    return request("/message/translate-source-language", "POST", data, false);
  },
  transferSpeech: (data: any) => {
    return request("/message/speech", "POST", data, false);
  },
  wordDetail: (data: any) => {
    return request("/message/word/detail", "POST", data, false);
  },
  wordPractice: (data: any) => {
    return request("/message/word/practice", "POST", data, false);
  },
  promptInvoke: (data: any) => {
    return request("/message/prompt", "POST", data, false);
  },
  languageExampleGet: (data?: any) => {
    return request("/languages/example", "GET", data, false);
  },
  rolesGet: (data?: any) => {
    return request("/roles", "GET", data, false);
  },
  /** 删除已发送的录音文件（识别发送后调用） */
  voiceFileDelete: (file_name: string) => {
    return request(`/voices/${encodeURIComponent(file_name)}`, "DELETE", null, false);
  },
};
