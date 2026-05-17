# 用户资源访问受限exception
class UserAccessDeniedException(Exception):
    pass


# 用户密码不正确
class UserPasswordIncorrectException(Exception):
    pass


# 参数不正确
class ParameterIncorrectException(Exception):
    pass


# AI 服务商额度/余额不足（如智谱 429 / code 1113）
class AIServiceQuotaExceededException(Exception):
    pass
