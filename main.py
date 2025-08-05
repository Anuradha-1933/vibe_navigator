# main.py

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from typing import List, Optional
from pydantic import BaseModel
import uvicorn
import json

# --- CORRECTED IMPORTS ---
# Updated to use your actual scraper file and function names
from gmaps_scraper import scrape_gmaps, scrape_reddit
from ai_summarizer import summarize_reviews
import asyncio

# Initialize FastAPI app
app = FastAPI(title="Vibe Navigator API", description="API for exploring city places with AI-powered vibe summaries")

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for scraper endpoints
class ScrapeRequest(BaseModel):
    place_id: int
    place_name: str
    google_maps_url: Optional[str] = None
    tripadvisor_url: Optional[str] = None

class ScrapeResponse(BaseModel):
    success: bool
    message: str
    reviews_scraped: int = 0
    summary_generated: bool = False

class CreatePlaceAndScrapeRequest(BaseModel):
    name: str
    city: str
    category: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    google_maps_url: Optional[str] = None
    tripadvisor_url: Optional[str] = None

# --- CORRECTED SCRAPER FUNCTION ---
async def scrape_and_store_reviews(place_id: int, place_name: str, google_maps_url: str = None, tripadvisor_url: str = None):
    """
    Background task to scrape reviews and store them in the database
    """
    conn = get_db_connection()
    all_reviews = []
    
    try:
        # Scrape Google Maps reviews if URL provided
        if google_maps_url:
            try:
                # Await the async scraper function
                google_reviews = await scrape_google_maps_reviews(google_maps_url)
                
                for review_text in google_reviews:
                    conn.execute(
                        'INSERT INTO reviews (place_id, source, content) VALUES (?, ?, ?)',
                        (place_id, 'Google Maps', review_text)
                    )
                    all_reviews.append(review_text)
                
            except Exception as e:
                print(f"Error scraping Google Maps: {e}")
        
        # Scrape TripAdvisor reviews if URL provided
        if tripadvisor_url:
            try:
                # Await the async scraper function
                tripadvisor_reviews = await scrape_tripadvisor_reviews(tripadvisor_url)
                
                for review_text in tripadvisor_reviews:
                    conn.execute(
                        'INSERT INTO reviews (place_id, source, content) VALUES (?, ?, ?)',
                        (place_id, 'TripAdvisor', review_text)
                    )
                    all_reviews.append(review_text)
                
            except Exception as e:
                print(f"Error scraping TripAdvisor: {e}")
        
        conn.commit()
        
        if all_reviews:
            # Generate AI vibe summary
            summary_json = await summarize_reviews(all_reviews)
            summary_data = json.loads(summary_json)
            
            summary_text = summary_data.get("summary", "No summary provided.")
            mood_tags_json = json.dumps(summary_data.get("mood_tags", []))
            key_themes_json = json.dumps(summary_data.get("key_themes", []))

            # Check if vibe summary already exists
            existing = conn.execute('SELECT * FROM vibe_summaries WHERE place_id = ?', (place_id,)).fetchone()
            
            if existing:
                conn.execute(
                    'UPDATE vibe_summaries SET summary = ?, mood_tags = ?, key_themes = ? WHERE place_id = ?',
                    (summary_text, mood_tags_json, key_themes_json, place_id)
                )
            else:
                conn.execute(
                    'INSERT INTO vibe_summaries (place_id, summary, mood_tags, key_themes) VALUES (?, ?, ?, ?)',
                    (place_id, summary_text, mood_tags_json, key_themes_json)
                )
            
            conn.commit()
            print(f"Successfully scraped {len(all_reviews)} reviews and generated summary for place ID {place_id}.")
            return len(all_reviews), True
        
        return 0, False
            
    except Exception as e:
        print(f"Error in scrape_and_store_reviews for place ID {place_id}: {e}")
    finally:
        conn.close()

# The rest of your main.py file is well-structured and does not require changes.
# I am including it below for completeness.

# Scraper endpoints
@app.post("/scrape/reviews", response_model=ScrapeResponse)
async def scrape_reviews(request: ScrapeRequest, background_tasks: BackgroundTasks):
    conn = get_db_connection()
    place = conn.execute('SELECT * FROM places WHERE id = ?', (request.place_id,)).fetchone()
    conn.close()
    
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    
    background_tasks.add_task(
        scrape_and_store_reviews,
        request.place_id,
        request.place_name,
        request.google_maps_url,
        request.tripadvisor_url
    )
    
    return ScrapeResponse(
        success=True,
        message=f"Started scraping reviews for {request.place_name}. This runs in the background."
    )

@app.post("/scrape/place-and-reviews", response_model=ScrapeResponse)
async def create_place_and_scrape_reviews(request: CreatePlaceAndScrapeRequest, background_tasks: BackgroundTasks):
    conn = get_db_connection()
    try:
        cursor = conn.execute(
            'INSERT INTO places (name, city, category, address, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)',
            (request.name, request.city, request.category, request.address, request.latitude, request.longitude)
        )
        place_id = cursor.lastrowid
        conn.commit()
        
        background_tasks.add_task(
            scrape_and_store_reviews,
            place_id,
            request.name,
            request.google_maps_url,
            request.tripadvisor_url
        )
        
        return ScrapeResponse(
            success=True,
            message=f"Created place '{request.name}' with ID {place_id} and started scraping reviews."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating place: {str(e)}")
    finally:
        conn.close()

# Pydantic models
class Place(BaseModel):
    id: Optional[int] = None
    name: str
    city: str
    category: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class Review(BaseModel):
    id: Optional[int] = None
    place_id: int
    source: str
    content: str
    rating: Optional[float] = None
    date: Optional[str] = None

class VibeSummary(BaseModel):
    id: Optional[int] = None
    place_id: int
    summary: str
    mood_tags: List[str]
    key_themes: List[str]

# Database setup
def get_db_connection():
    conn = sqlite3.connect('vibe_navigator.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS places (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, city TEXT NOT NULL,
            category TEXT NOT NULL, address TEXT, latitude REAL, longitude REAL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT, place_id INTEGER NOT NULL, source TEXT NOT NULL,
            content TEXT NOT NULL, rating REAL, date TEXT,
            FOREIGN KEY (place_id) REFERENCES places (id)
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS vibe_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT, place_id INTEGER NOT NULL UNIQUE, summary TEXT NOT NULL,
            mood_tags TEXT NOT NULL, key_themes TEXT NOT NULL,
            FOREIGN KEY (place_id) REFERENCES places (id)
        )
    ''')
    conn.commit()
    conn.close()

@app.on_event("startup")
async def startup_event():
    init_db()

# Endpoints (no changes needed for the ones below)
@app.get("/")
async def root():
    return {"message": "Vibe Navigator API is running!"}

@app.get("/places/", response_model=List[Place])
async def get_places(city: Optional[str] = None, category: Optional[str] = None):
    conn = get_db_connection()
    query = "SELECT * FROM places WHERE 1=1"
    params = []
    if city:
        query += " AND city = ?"
        params.append(city)
    if category:
        query += " AND category = ?"
        params.append(category)
    places = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(place) for place in places]

@app.post("/places/", response_model=Place)
async def create_place(place: Place):
    conn = get_db_connection()
    cursor = conn.execute(
        'INSERT INTO places (name, city, category, address, latitude, longitude) VALUES (?, ?, ?, ?, ?, ?)',
        (place.name, place.city, place.category, place.address, place.latitude, place.longitude)
    )
    place_id = cursor.lastrowid
    conn.commit()
    conn.close()
    place.id = place_id
    return place

@app.get("/places/{place_id}", response_model=Place)
async def get_place(place_id: int):
    conn = get_db_connection()
    place = conn.execute('SELECT * FROM places WHERE id = ?', (place_id,)).fetchone()
    conn.close()
    if place is None:
        raise HTTPException(status_code=404, detail="Place not found")
    return dict(place)

@app.get("/places/{place_id}/reviews", response_model=List[Review])
async def get_reviews(place_id: int):
    conn = get_db_connection()
    reviews = conn.execute('SELECT * FROM reviews WHERE place_id = ?', (place_id,)).fetchall()
    conn.close()
    return [dict(review) for review in reviews]

@app.get("/places/{place_id}/vibe", response_model=VibeSummary)
async def get_vibe_summary(place_id: int):
    conn = get_db_connection()
    vibe_summary = conn.execute('SELECT * FROM vibe_summaries WHERE place_id = ?', (place_id,)).fetchone()
    conn.close()
    
    if vibe_summary is None:
        raise HTTPException(status_code=404, detail="Vibe summary not found. Scrape reviews first.")
    
    return VibeSummary(
        id=vibe_summary['id'],
        place_id=vibe_summary['place_id'],
        summary=vibe_summary['summary'],
        mood_tags=json.loads(vibe_summary['mood_tags']),
        key_themes=json.loads(vibe_summary['key_themes'])
    )

@app.get("/search/")
async def search_places(query: str, city: Optional[str] = None):
    conn = get_db_connection()
    search_query = """
        SELECT p.* 
        FROM places p 
        LEFT JOIN vibe_summaries v ON p.id = v.place_id 
        WHERE 1=1
    """
    params = []

    if city:
        search_query += " AND LOWER(p.city) LIKE ?"
        params.append(f"%{city.lower()}%")

    if query:
        search_query += """
            AND (
                LOWER(p.name) LIKE ? OR 
                LOWER(p.category) LIKE ? OR 
                LOWER(v.summary) LIKE ? OR 
                LOWER(v.mood_tags) LIKE ? OR 
                LOWER(v.key_themes) LIKE ?
            )
        """
        q = f"%{query.lower()}%"
        params.extend([q, q, q, q, q])

    print("DEBUG - SQL Query:", search_query)
    print("DEBUG - Params:", params)

    places = conn.execute(search_query, params).fetchall()
    conn.close()
    return {"query": query, "results": [dict(place) for place in places]}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)