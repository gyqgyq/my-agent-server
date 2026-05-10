from fastapi import APIRouter

router = APIRouter()

@router.get("/book")
async def get_book():
    return {"message": "Hello World"}