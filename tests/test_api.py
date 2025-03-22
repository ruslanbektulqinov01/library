import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from main import app, get_db
from database import Base
from models import User, Book
from auth import get_password_hash, get_current_user, oauth2_scheme

# Test database setup
TEST_SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Override get_db dependency
def override_get_db():
    db = None
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        if db is not None:
            db.close()

# Override authentication for tests
async def override_get_current_user():
    return {"username": "testuser", "permissions": "read_book,create_book"}

# Apply dependency overrides
app.dependency_overrides = {
    get_db: override_get_db,
    oauth2_scheme: lambda: "test_token",
    get_current_user: override_get_current_user
}

# Setup test client
client = TestClient(app)

@pytest.fixture(scope="function")
def setup_database():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    test_user = User(
        username="testuser",
        hashed_password=get_password_hash("password123"),
        permissions="read_book,create_book"
    )
    db.add(test_user)
    test_book1 = Book(title="Test Book 1", author="Test Author 1", isbn="9781234567890")
    test_book2 = Book(title="Test Book 2", author="Test Author 2", isbn="9789876543210")
    db.add(test_book1)
    db.add(test_book2)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def auth_token():
    return {"Authorization": "Bearer test_token"}



def test_register_success(setup_database):
    response = client.post(
        "/register",
        json={"username": "brandnewuser", "password": "password123", "permissions": "read_book"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_register_existing_username(setup_database):
    response = client.post(
        "/register",
        json={"username": "testuser", "password": "password123", "permissions": "read_book"}
    )
    assert response.status_code == 400
    assert "Bu username allaqachon mavjud" in response.json()["detail"]


# TEST LOGIN
def test_login_success(setup_database):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_invalid_credentials(setup_database):
    response = client.post(
        "/login",
        data={"username": "testuser", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "Noto'g'ri username yoki parol" in response.json()["detail"]


# TEST BOOK ENDPOINTS
def test_get_all_books(setup_database):
    response = client.get("/books")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_create_book_success(setup_database, auth_token):
    response = client.post(
        "/books",
        headers=auth_token,
        json={"title": "New Book", "author": "New Author", "isbn": "9780123456789"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "New Book"
    assert response.json()["author"] == "New Author"
    assert response.json()["isbn"] == "9780123456789"


def test_create_book_duplicate_isbn(setup_database, auth_token):
    response = client.post(
        "/books",
        headers=auth_token,
        json={"title": "Duplicate ISBN", "author": "Some Author", "isbn": "9781234567890"}
    )
    assert response.status_code == 400
    assert "Bu ISBN raqamli kitob allaqachon mavjud" in response.json()["detail"]


def test_delete_book_success(setup_database, auth_token):
    # First get all books to find an id
    books = client.get("/books").json()
    book_id = books[0]["id"]

    response = client.delete(f"/books/{book_id}", headers=auth_token)
    assert response.status_code == 200

    # Verify book is deleted
    all_books = client.get("/books").json()
    assert len(all_books) == 1


def test_delete_book_not_found(setup_database, auth_token):
    response = client.delete("/books/999", headers=auth_token)
    assert response.status_code == 404
    assert "Kitob topilmadi" in response.json()["detail"]


def test_get_books_by_name(setup_database):
    response = client.get("/books/name/Test Book 1")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Test Book 1"


def test_get_book_by_isbn(setup_database):
    response = client.get("/books/isbn/9781234567890")
    assert response.status_code == 200
    assert response.json()["isbn"] == "9781234567890"


def test_get_book_by_isbn_not_found(setup_database):
    response = client.get("/books/isbn/9999999999999")
    assert response.status_code == 404
    assert "Kitob topilmadi" in response.json()["detail"]


def test_get_books_by_author(setup_database):
    response = client.get("/books/author/Test Author 1")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["author"] == "Test Author 1"


def test_update_book_success(setup_database, auth_token):
    # First get all books to find an id
    books = client.get("/books").json()
    book_id = books[0]["id"]

    response = client.put(
        f"/books/{book_id}",
        headers=auth_token,
        json={"title": "Updated Book Title"}
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Book Title"


def test_update_book_not_found(setup_database, auth_token):
    response = client.put(
        "/books/999",
        headers=auth_token,
        json={"title": "This Should Fail"}
    )
    assert response.status_code == 404
    assert "Kitob topilmadi" in response.json()["detail"]


def test_update_book_duplicate_isbn(setup_database, auth_token):
    books = client.get("/books").json()
    book_id = books[0]["id"]
    other_book_isbn = books[1]["isbn"]

    response = client.put(
        f"/books/{book_id}",
        headers=auth_token,
        json={"isbn": other_book_isbn}
    )
    assert response.status_code == 400
    assert "Bu ISBN allaqachon mavjud" in response.json()["detail"]
