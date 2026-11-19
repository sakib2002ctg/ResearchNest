from typing import Annotated

from fastapi import Response
from pydantic import Field

DocumentID = Annotated[int, Field(gt=0, le=2_147_483_647)]


async def private_response(response: Response):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
