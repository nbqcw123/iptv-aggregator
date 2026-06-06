"""
IPTV 定时任务调度器
负责定期同步 IPTV 源、清理过期数据等。
"""

from apscheduler.schedulers.background import BackgroundScheduler

# 全局调度器实例
_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> None:
    """启动后台定时任务调度器。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
        # TODO: 添加定时同步任务
        # _scheduler.add_job(sync_all_sources, "interval", hours=1)
        _scheduler.start()


def stop_scheduler() -> None:
    """停止后台定时任务调度器。"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
