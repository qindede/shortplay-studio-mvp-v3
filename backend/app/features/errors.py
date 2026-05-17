from __future__ import annotations


class DomainError(Exception):
    """业务异常，由 service 层抛出，由 router 层的 @api_endpoint 装饰器捕获并转换为 HTTP 响应。"""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def not_found(msg: str = "资源不存在") -> DomainError:
    return DomainError(404, msg)


def insufficient_points(needed: int, current: int) -> DomainError:
    return DomainError(402, f"需要 {needed} 积分，当前 {current}")
