/**
 * 服务端 API 地址
 * - 浏览器/H5 调试：用 localhost
 * - 真机 USB 调试：必须改成你电脑的局域网 IP，否则手机连不上（在电脑上运行 ipconfig 查看 IPv4 地址）
 */
const isH5 = typeof window !== "undefined" && !/android|iphone|ipad/i.test(navigator.userAgent);
const PC_IP = "192.168.1.26"; // 真机调试时改为你电脑的 IP（如 192.168.1.xxx）

export default {
  basePath: isH5
    ? "http://localhost:8098/api/v1"
    : `http://${PC_IP}:8098/api/v1`,
  // basePath: "https://talkie.prejade.com/api/v1"
};
