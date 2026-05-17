from __future__ import annotations


class DomainError(Exception):
    """业务异常基类，由 service 层抛出，由 router 层的 @api_endpoint 装饰器捕获并转换为 HTTP 响应。"""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class BadRequestError(DomainError):
    pass


class UnauthorizedError(DomainError):
    pass


class InsufficientPointsError(DomainError):
    pass


class ForbiddenError(DomainError):
    pass


class NotFoundError(DomainError):
    pass


class ConflictError(DomainError):
    pass


class ServiceUnavailableError(DomainError):
    pass


# 便捷工厂函数
def not_found(msg: str = "资源不存在") -> NotFoundError:
    return NotFoundError(msg)


def insufficient_points(needed: int, current: int) -> InsufficientPointsError:
    return InsufficientPointsError(f"需要 {needed} 积分，当前 {current}")
