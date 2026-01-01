import os
import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import google.generativeai as genai
from github import Github

# --- CONFIGURATION ---
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/pr_reviews")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")              
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- DATABASE SETUP ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    pr_number = Column(Integer)
    repo_name = Column(String)
    branch = Column(String)
    ai_feedback = Column(Text)
    status = Column(String, default="PENDING")  # PENDING, APPROVED, REJECTED

# Create Tables
Base.metadata.create_all(bind=engine)

# --- APP SETUP ---
app = FastAPI()

# Allow Frontend to talk to Backend (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- HELPER FUNCTIONS ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def generate_ai_review(diff: str, branch: str):
    """Sends code diff to Gemini API for review based on branch context."""
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    context = "General code review."
    if branch.startswith("feature/"):
        context = "Focus on scalability, code style, and performance."
    elif branch.startswith("fix/") or branch.startswith("hotfix/"):
        context = "Focus on bug fixes, error handling, and security."

    prompt = f"""
    You are a Senior DevOps Engineer. Perform a code review for this Pull Request.
    Context: {context}
    
    Code Diff:
    {diff[:10000]}  # Limit characters to avoid API limits
    
    Provide a concise feedback summary in Markdown.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logger.error(f"Gemini Error: {e}")
        return "Error generating AI review."

def process_pr_logic(payload: dict):
    """Background task to fetch diff, get AI review, and save to DB."""
    try:
        pr = payload.get("pull_request")
        repo_name = payload.get("repository", {}).get("full_name")
        pr_number = pr.get("number")
        branch = pr.get("head", {}).get("ref")
        
        # 1. Fetch Diff from GitHub
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(repo_name)
        pull = repo.get_pull(pr_number)
        
        diff_str = ""
        for file in pull.get_files():
            diff_str += f"\nFile: {file.filename}\n{file.patch}\n"
            
        # 2. Get AI Review
        review_text = generate_ai_review(diff_str, branch)
        
        # 3. Save to DB
        db = SessionLocal()
        new_review = Review(
            pr_number=pr_number,
            repo_name=repo_name,
            branch=branch,
            ai_feedback=review_text,
            status="PENDING"
        )
        db.add(new_review)
        db.commit()
        db.close()
        logger.info(f"Review generated for PR #{pr_number}")
        
    except Exception as e:
        logger.error(f"Error processing PR: {e}")

# --- ROUTES ---

@app.post("/webhook")
async def github_webhook(payload: dict, background_tasks: BackgroundTasks):
    """Receives Webhook from GitHub."""
    action = payload.get("action")
    if action in ["opened", "synchronize", "reopened"]:
        background_tasks.add_task(process_pr_logic, payload)
    return {"status": "received"}

@app.get("/reviews")
def get_reviews():
    """Fetch all reviews for the frontend."""
    db = SessionLocal()
    reviews = db.query(Review).order_by(Review.id.desc()).all()
    db.close()
    return reviews

@app.post("/reviews/{review_id}/approve")
def approve_review(review_id: int):
    """Post comment to GitHub and mark as Approved."""
    db = SessionLocal()
    review = db.query(Review).filter(Review.id == review_id).first()
    
    if review and review.status == "PENDING":
        # Post to GitHub
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(review.repo_name)
        pr = repo.get_pull(review.pr_number)
        pr.create_issue_comment(f"✅ **AI Review Approved:**\n\n{review.ai_feedback}")
        
        review.status = "APPROVED"
        db.commit()
    
    db.close()
    return {"status": "approved"}

@app.post("/reviews/{review_id}/reject")
def reject_review(review_id: int):
    """Mark as Rejected (internal only)."""
    db = SessionLocal()
    review = db.query(Review).filter(Review.id == review_id).first()
    if review:
        review.status = "REJECTED"
        db.commit()
    db.close()
    return {"status": "rejected"}