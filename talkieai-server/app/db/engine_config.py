from typing import Any, Dict


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg2://" + database_url[len("postgres://") :]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + database_url[len("postgresql://") :]
    return database_url


def build_engine_options(database_url: str, echo: bool) -> Dict[str, Any]:
    if database_url.startswith("sqlite"):
        return {
            "echo": echo,
            "connect_args": {"check_same_thread": False},
        }

    if database_url.startswith("postgresql"):
        return {
            "echo": echo,
            "pool_pre_ping": True,
            "pool_size": 5,
            "max_overflow": 5,
            "pool_recycle": 1800,
        }

    return {
        "echo": echo,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
        "pool_recycle": 360,
    }


def should_install_mysql_checkout_listener(database_url: str) -> bool:
    return database_url.startswith("mysql")
