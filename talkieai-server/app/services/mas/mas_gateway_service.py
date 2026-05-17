"""
MAS服务网关：负责转发请求到各个MAS服务
"""
import httpx
from typing import Dict, Any, Optional, Union
from app.config import Config
from app.core.logging import logging


class MASGatewayService:
    """MAS服务网关，负责转发请求到各个MAS服务"""
    
    @staticmethod
    def _get_services():
        """获取MAS服务地址配置"""
        return {
            "mma": Config.MAS_MMA_URL,
            "soa": Config.MAS_SOA_URL,
            "gra": Config.MAS_GRA_URL,
            "sca": Config.MAS_SCA_URL,
            "ssa": Config.MAS_SSA_URL,
            "oa": Config.MAS_OA_URL
        }
    
    @staticmethod
    async def call_mas_service(
        service_name: str,
        endpoint: str,
        method: str = "POST",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        timeout: Optional[Union[int, float]] = None,
    ) -> Dict[str, Any]:
        """
        调用MAS服务
        
        Args:
            service_name: 服务名称 (mma, soa, gra, sca, ssa, oa)
            endpoint: API端点路径
            method: HTTP方法 (GET, POST)
            data: 请求体数据（POST用）
            params: URL参数（GET用）
            timeout: 读超时（秒）；默认使用 Config.MAS_HTTP_READ_TIMEOUT（SOA/GRA/SCA 等需较长）
            
        Returns:
            响应数据字典
            
        Raises:
            ValueError: 未知的服务名称
            Exception: HTTP请求失败
        """
        services = MASGatewayService._get_services()
        base_url = services.get(service_name.lower())
        if not base_url:
            raise ValueError(f"Unknown MAS service: {service_name}")
        
        url = f"{base_url}{endpoint}"

        read_sec = float(timeout) if timeout is not None else float(Config.MAS_HTTP_READ_TIMEOUT)
        connect_sec = float(Config.MAS_HTTP_CONNECT_TIMEOUT)
        httpx_timeout = httpx.Timeout(
            connect=connect_sec,
            read=read_sec,
            write=60.0,
            pool=10.0,
        )

        try:
            async with httpx.AsyncClient(timeout=httpx_timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, params=params or data)
                else:
                    response = await client.post(url, json=data)
                
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            logging.error(f"MAS service HTTP error: {service_name} {endpoint} - {e.response.status_code} - {e.response.text}")
            raise Exception(f"MAS服务调用失败: HTTP {e.response.status_code}")
        except httpx.TimeoutException as e:
            logging.error(
                f"MAS service timeout: {service_name} {endpoint} read={read_sec}s - {e}"
            )
            raise Exception(
                f"MAS服务超时（>{read_sec:.0f}s），请检查 SOA/GRA/SCA 或大模型 API 是否正常"
            )
        except httpx.RequestError as e:
            logging.error(f"MAS service request error: {service_name} {endpoint} - {e}")
            raise Exception(f"MAS服务连接失败: {str(e)}")
        except Exception as e:
            logging.error(f"MAS service call failed: {service_name} {endpoint} - {e}")
            raise Exception(f"MAS服务调用失败: {str(e)}")
    
    @staticmethod
    async def check_service_health(service_name: str) -> bool:
        """
        检查MAS服务健康状态
        
        Args:
            service_name: 服务名称
            
        Returns:
            True if service is healthy, False otherwise
        """
        try:
            services = MASGatewayService._get_services()
            base_url = services.get(service_name.lower())
            if not base_url:
                return False
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{base_url}/health", timeout=5)
                return response.status_code == 200
        except:
            return False
    
    @staticmethod
    def get_service_url(service_name: str) -> Optional[str]:
        """
        获取服务URL
        
        Args:
            service_name: 服务名称
            
        Returns:
            服务URL，如果不存在返回None
        """
        services = MASGatewayService._get_services()
        return services.get(service_name.lower())
