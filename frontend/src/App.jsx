import { useState, useEffect } from "react";
import axios from "axios";
import "./App.css";

// Use relative URL so Nginx/Docker handles the routing, or direct IP for testing
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

function App() {
  const [reviews, setReviews] = useState([]);

  useEffect(() => {
    fetchReviews();
  }, []);

  const fetchReviews = async () => {
    try {
      const res = await axios.get(`${API_URL}/reviews`);
      setReviews(res.data);
    } catch (error) {
      console.error("Error fetching reviews", error);
    }
  };

  const handleApprove = async (id) => {
    await axios.post(`${API_URL}/reviews/${id}/approve`);
    fetchReviews(); // Refresh list
  };

  const handleReject = async (id) => {
    await axios.post(`${API_URL}/reviews/${id}/reject`);
    fetchReviews();
  };

  return (
    <div style={{ padding: "20px", fontFamily: "Arial, sans-serif" }}>
      <h1>🚀 DevOps AI Code Reviewer</h1>
      <div style={{ display: "grid", gap: "20px" }}>
        {reviews.map((review) => (
          <div
            key={review.id}
            style={{
              border: "1px solid #ddd",
              padding: "15px",
              borderRadius: "8px",
              background: "#f9f9f9",
            }}
          >
            <h3>
              PR #{review.pr_number}: {review.branch}
            </h3>
            <p>
              <strong>Status:</strong> {review.status}
            </p>
            <div
              style={{
                background: "#eee",
                padding: "10px",
                borderRadius: "5px",
                whiteSpace: "pre-wrap",
                maxHeight: "200px",
                overflowY: "auto",
              }}
            >
              {review.ai_feedback}
            </div>
            {review.status === "PENDING" && (
              <div style={{ marginTop: "10px" }}>
                <button
                  onClick={() => handleApprove(review.id)}
                  style={{
                    marginRight: "10px",
                    background: "green",
                    color: "white",
                    padding: "8px 15px",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  Approve & Post
                </button>
                <button
                  onClick={() => handleReject(review.id)}
                  style={{
                    background: "red",
                    color: "white",
                    padding: "8px 15px",
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
