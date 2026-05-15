from __future__ import annotations


class AIError(RuntimeError):
    public_message = "AI 服务暂时不可用"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.public_message)


class AIConfigurationError(AIError):
    public_message = "AI 服务尚未配置"


class AIProviderAuthError(AIError):
    public_message = "AI 服务鉴权失败"


class AIProviderRateLimitError(AIError):
    public_message = "AI 服务请求过于频繁"


class AIProviderTimeoutError(AIError):
    public_message = "AI 服务响应超时"


class AIProviderValidationError(AIError):
    public_message = "AI 请求参数无效"


class AIProviderTaskFailedError(AIError):
    public_message = "AI 任务生成失败"


class AIOutputSchemaError(AIError):
    public_message = "AI 返回格式不符合要求"
