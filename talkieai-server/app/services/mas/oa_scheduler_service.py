"""
OA 定时调度服务：在 talkieai-server 中定时调用 OA 的调度端点

调度任务：
- 每天 00:00：调用 OA /trigger_mma（MMA 提取会话笔记）
- 每半小时：调用 OA /trigger_hourly_check（检查预约并触发 SOA）
- 每天 02:00：调用 OA /trigger_daily_reset（重置所有患者会话）

注意：若 OA 已单独部署且运行其内部 orchestration_loop，可设置 MAS_OA_SCHEDULER_ENABLED=false 避免重复执行。
"""
import threading
import time

import httpx
from apscheduler.schedulers.background import BackgroundScheduler
from app.config import Config
from app.core.logging import logging


def _call_oa(endpoint: str, retries: int = 3, base_backoff_seconds: float = 1.0) -> bool:
    """
    同步调用 OA 端点（带重试）。

    Returns:
        bool: 是否调用成功
    """
    base_url = Config.MAS_OA_URL.rstrip("/")
    url = f"{base_url}{endpoint}"
    connect_timeout = 5.0
    read_timeout = 30.0
    timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=10.0, pool=5.0)

    for attempt in range(1, retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url)
                response.raise_for_status()
                logging.info(f"OA scheduler: {endpoint} -> {response.json()}")
                return True
        except Exception as e:
            is_last_attempt = attempt == retries
            logging.warning(
                f"OA scheduler: {endpoint} attempt {attempt}/{retries} failed: {e}"
            )
            if not is_last_attempt:
                # 退避重试，降低偶发网络抖动导致的漏触发概率
                sleep_seconds = base_backoff_seconds * (2 ** (attempt - 1))
                time.sleep(sleep_seconds)
            else:
                logging.error(f"OA scheduler: {endpoint} failed after {retries} attempts")
                return False
    return False


def _job_trigger_mma():
    """每天 00:00 触发 MMA 提取"""
    logging.info("OA scheduler: running trigger_mma (midnight)")
    _call_oa("/trigger_mma")


def _job_trigger_hourly_check():
    """每半小时检查预约"""
    logging.info("OA scheduler: running trigger_hourly_check (half-hour)")
    _call_oa("/trigger_hourly_check")


def _job_trigger_daily_reset():
    """每天 02:00 重置会话"""
    logging.info("OA scheduler: running trigger_daily_reset")
    _call_oa("/trigger_daily_reset")


_scheduler: BackgroundScheduler | None = None


def _run_startup_catchup_check() -> None:
    """
    启动后补跑一次检查，避免服务重启期间错过半点任务导致预约长时间不触发。
    """
    # 给应用/网络一点启动缓冲，避免与服务冷启动竞争资源
    time.sleep(5)
    logging.info("OA scheduler: startup catch-up trigger_hourly_check")
    _call_oa("/trigger_hourly_check")


def start_oa_scheduler() -> None:
    """启动 OA 定时调度器"""
    if not Config.MAS_OA_SCHEDULER_ENABLED:
        logging.info("OA scheduler: disabled by MAS_OA_SCHEDULER_ENABLED")
        return

    global _scheduler
    if _scheduler is not None:
        logging.warning("OA scheduler: already running")
        return

    _scheduler = BackgroundScheduler(
        job_defaults={
            # 如果错过窗口，尽快补跑，不丢任务
            "misfire_grace_time": 10 * 60,
            # 同类任务合并，避免堆积后连环触发
            "coalesce": True,
            # 单任务只允许一个实例，避免重入导致状态竞争
            "max_instances": 1,
        }
    )
    # 每天 00:00 触发 MMA
    _scheduler.add_job(_job_trigger_mma, "cron", hour=0, minute=0, id="oa_trigger_mma")
    # 每半小时检查预约
    _scheduler.add_job(_job_trigger_hourly_check, "cron", minute="0,30", id="oa_trigger_hourly")
    # 每天 02:00 重置会话
    _scheduler.add_job(_job_trigger_daily_reset, "cron", hour=2, minute=0, id="oa_trigger_reset")

    _scheduler.start()
    logging.info("OA scheduler: started (midnight MMA, half-hour check, 2am reset)")

    # 启动后补跑一次，防止错过最近一次半点检查
    threading.Thread(target=_run_startup_catchup_check, daemon=True).start()


def stop_oa_scheduler() -> None:
    """停止 OA 定时调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logging.info("OA scheduler: stopped")
