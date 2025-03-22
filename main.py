from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List

from database import SessionLocal, engine
from models import Base, User, Book
from schemas import UserCreate, Token, BookCreate, BookSchema, BookUpdate
from auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
import uvicorn

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handler for unexpected errors
@app.middleware("http")
async def catch_exceptions_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        error_detail = {"detail": str(e), "type": type(e).__name__}
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=error_detail
        )


# Database session management
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# User registration
@app.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    try:
        db_user = db.query(User).filter(User.username == user.username).first()
        if db_user:
            raise HTTPException(
                status_code=400,
                detail="Bu username allaqachon mavjud"
            )

        hashed_password = get_password_hash(user.password)
        new_user = User(username=user.username, hashed_password=hashed_password)

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        access_token = create_access_token(data={"sub": new_user.username})
        return {"access_token": access_token, "token_type": "bearer"}

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Ma'lumot bazasi xatosi yuz berdi: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Ro'yxatdan o'tishda xatolik: {str(e)}"
        )


# User login
@app.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.username == form_data.username).first()
        if not user or not verify_password(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=401,
                detail="Noto'g'ri username yoki parol"
            )

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username},
            expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Kirishda xatolik: {str(e)}"
        )


# Create new book
@app.post("/books", response_model=BookSchema)
def create_book(book: BookCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        # Check if book with same ISBN exists
        existing_book = db.query(Book).filter(Book.isbn == book.isbn).first()
        if existing_book:
            raise HTTPException(
                status_code=400,
                detail="Bu ISBN raqamli kitob allaqachon mavjud"
            )

        db_book = Book(**book.model_dump())
        db.add(db_book)
        db.commit()
        db.refresh(db_book)
        return db_book

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Ma'lumotlar bazasi xatoligi: {str(e)}"
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Kitob saqlashda xatolik: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Kitob qo'shishda xatolik: {str(e)}"
        )


# Get all books
@app.get("/books", response_model=List[BookSchema])
def read_books(db: Session = Depends(get_db)):
    try:
        return db.query(Book).all()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Kitoblarni olishda xatolik: {str(e)}"
        )


# Delete book
@app.delete("/books/{book_id}", response_model=BookSchema)
def delete_book(book_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        book = db.query(Book).filter(Book.id == book_id).first()
        if not book:
            raise HTTPException(
                status_code=404,
                detail="Kitob topilmadi"
            )

        db.delete(book)
        db.commit()
        return book

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Kitobni o'chirishda xatolik: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Kitobni o'chirishda xatolik: {str(e)}"
        )


# Get books by name
@app.get("/books/name/{name}", response_model=List[BookSchema])
def get_books_by_name(name: str, db: Session = Depends(get_db)):
    try:
        books = db.query(Book).filter(Book.title == name).all()
        return books
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Kitoblarni nom bo'yicha olishda xatolik: {str(e)}"
        )


# Get book by ISBN
@app.get("/books/isbn/{isbn}", response_model=BookSchema)
def get_book_by_isbn(isbn: str, db: Session = Depends(get_db)):
    try:
        book = db.query(Book).filter(Book.isbn == isbn).first()
        if not book:
            raise HTTPException(
                status_code=404,
                detail="Kitob topilmadi"
            )
        return book

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"ISBN bo'yicha kitobni olishda xatolik: {str(e)}"
        )


# Get books by author
@app.get("/books/author/{author}", response_model=List[BookSchema])
def get_books_by_author(author: str, db: Session = Depends(get_db)):
    try:
        books = db.query(Book).filter(Book.author == author).all()
        return books
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Muallif bo'yicha kitoblarni olishda xatolik: {str(e)}"
        )


# Update book
@app.put("/books/{book_id}", response_model=BookSchema)
def update_book(
        book_id: int,
        book_update: BookUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        db_book = db.query(Book).filter(Book.id == book_id).first()
        if not db_book:
            raise HTTPException(
                status_code=404,
                detail="Kitob topilmadi"
            )

        update_data = book_update.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "isbn" and value != db_book.isbn:
                existing_book = db.query(Book).filter(Book.isbn == value).first()
                if existing_book and existing_book.id != book_id:
                    raise HTTPException(
                        status_code=400,
                        detail="Bu ISBN allaqachon mavjud"
                    )
            setattr(db_book, key, value)

        db.commit()
        db.refresh(db_book)
        return db_book

    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Ma'lumotlar bazasi xatoligi: {str(e)}"
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"Kitobni yangilashda xatolik: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)