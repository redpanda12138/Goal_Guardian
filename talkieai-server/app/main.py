from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.config import Config
from app.core.exceptions import (
    UserAccessDeniedException,
    AIServiceQuotaExceededException,
)
from app.core.logging import logging
from app.models.response import ApiResponse

from app.api.sys_routes import router as sys_routes
from app.api.account_routes import router as account_routes
from app.api.message_routes import router as message_routes
from app.api.session_routes import router as session_routes
from app.api.topics_route import router as topic_routes
from app.api.mas_routes import router as mas_routes
from app.services.mas.oa_scheduler_service import start_oa_scheduler, stop_oa_scheduler

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    """应用启动时启动 OA 定时调度"""
    start_oa_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    """应用关闭时停止 OA 定时调度"""
    stop_oa_scheduler()

# Enables CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(account_routes, prefix=f"{Config.API_PREFIX}/v1")
app.include_router(topic_routes, prefix=f"{Config.API_PREFIX}/v1")
app.include_router(sys_routes, prefix=f"{Config.API_PREFIX}/v1")
app.include_router(session_routes, prefix=f"{Config.API_PREFIX}/v1")
app.include_router(message_routes, prefix=f"{Config.API_PREFIX}/v1")
app.include_router(mas_routes, prefix=f"{Config.API_PREFIX}/v1")

# ========== 调试：验证MAS路由注册 ==========
# 在启动时打印所有MAS相关路由，用于调试
mas_routes_list = [r for r in app.routes if hasattr(r, 'path') and 'mas' in r.path]
if mas_routes_list:
    logging.info(f"MAS routes registered: {len(mas_routes_list)} routes")
    for route in mas_routes_list:
        methods = getattr(route, 'methods', set())
        logging.info(f"  {list(methods)} {route.path}")
else:
    logging.warning("WARNING: No MAS routes found! Check mas_routes.py import.")


@app.exception_handler(AIServiceQuotaExceededException)
async def ai_quota_exceeded_handler(_, exc: AIServiceQuotaExceededException):
    logging.error(exc)
    return JSONResponse(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
        content=ApiResponse(
            code="429", status="FAILED", message=str(exc)
        ).__dict__,
    )


@app.exception_handler(Exception)
async def conflict_error_handler(_, exc: Exception):
    """全局异常处理"""
    logging.error(exc)
    # 返回状态码仍为200，exc的错误信息放到ApiResponse中以json格式方式返回并且可以跨域访问
    return JSONResponse(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
        content=ApiResponse(code="500", status="FAILED", message=str(exc)).__dict__,
    )


# UserAccessDeniedException异常处理状态码为403
@app.exception_handler(UserAccessDeniedException)
async def user_access_denied_error_handler(_, exc: UserAccessDeniedException):
    """全局异常处理"""
    logging.error(exc)
    # 返回状态码仍为200，exc的错误信息放到ApiResponse中以json格式方式返回并且可以跨域访问
    return JSONResponse(
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "*",
            "Access-Control-Allow-Headers": "*",
        },
        content=ApiResponse(code="403", status="FAILED", message=str(exc)).__dict__,
    )
