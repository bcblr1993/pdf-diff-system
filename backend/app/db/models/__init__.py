"""所有 ORM 模型在此 import，触发注册到 Base.metadata。"""
from .user import User, UserRole  # noqa: F401
from .file import File  # noqa: F401
from .comparison import Comparison, ComparisonStatus, ReviewStatus  # noqa: F401
from .diff import Diff, DiffCategory, DiffSeverity, ReviewAction  # noqa: F401
from .audit_log import AuditLog  # noqa: F401
