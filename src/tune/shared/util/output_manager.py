"""Manages all output to console or log with a singleton object."""


class OutputManager:
    def __init__(self) -> None:
        pass

    def debug(self, m: str) -> None:
        pass

    def error(self, m: str) -> None:
        pass

    def warning(self, m: str) -> None:
        pass

    def info(self, m: str) -> None:
        pass


output_manager = OutputManager()
