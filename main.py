from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import SessionLocal, engine
from models import Base, User, Book
from schemas import UserCreate, UserLogin, Token, BookCreate, Book
from auth import get_password_hash, verify_password, create_access_token, get_current_user
import uvicorn

# Ma'lumotlar bazasini yaratish
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Ma'lumotlar bazasi sessiyasini boshqarish
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Foydalanuvchi ro'yxatdan o'tishi
@app.post("/register", response_model=Token)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Bu username allaqachon mavjud")
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, hashed_password=hashed_password, permissions=user.permissions)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    access_token = create_access_token(data={"sub": new_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Foydalanuvchi tizimga kirishi
@app.post("/login", response_model=Token)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if not db_user or not verify_password(user.password, db_user.hashed_password):
        raise HTTPException(status_code=401, detail="Noto‘g‘ri username yoki parol")
    access_token = create_access_token(data={"sub": db_user.username})
    return {"access_token": access_token, "token_type": "bearer"}

# Kitob qo'shish
@app.post("/books", response_model=Book)
def create_book(book: BookCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if "create_book" not in current_user.permissions.split(","):
        raise HTTPException(status_code=403, detail="Kitob qo‘shish uchun ruxsat yo‘q")
    db_book = Book(**book.dict())
    db.add(db_book)
    db.commit()
    db.refresh(db_book)
    return db_book

# Barcha kitoblarni olish
@app.get("/books", response_model=List[Book])
def read_books(db: Session = Depends(get_db)):
    return db.query(Book).all()

# Kitobni o'chirish
@app.delete("/books/{book_id}", response_model=Book)
def delete_book(book_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if "delete_book" not in current_user.permissions.split(","):
        raise HTTPException(status_code=403, detail="Kitob o‘chirish uchun ruxsat yo‘q")
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Kitob topilmadi")
    db.delete(book)
    db.commit()
    return book

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)