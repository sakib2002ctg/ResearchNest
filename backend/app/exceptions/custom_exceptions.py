class ResearchNestException(Exception):
    """
    Base exception for all custom application exceptions.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class PaperNotFoundException(ResearchNestException):
    """
    Raised when a research paper cannot be found.
    """

    def __init__(self, paper_id: int):
        super().__init__(
            f"Research paper with id {paper_id} not found."
        )
        self.paper_id = paper_id