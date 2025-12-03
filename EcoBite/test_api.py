
import requests
import json

BASE_URL = "http://127.0.0.1:5000"
SESSION = requests.Session()

def login(email, password):
    print(f"Logging in as {email}...")
    resp = SESSION.post(f"{BASE_URL}/login", data={"email": email, "password": password})
    if resp.status_code == 200 and "Welcome back" in resp.text:
        print("Login successful")
        return True
    elif "Account created" in resp.text: # If redirected after signup
        print("Login/Signup successful")
        return True
    else:
        # Try signup if login fails
        print("Login failed, trying signup...")
        resp = SESSION.post(f"{BASE_URL}/signup", data={"email": email, "password": password, "role": "user"})
        if resp.status_code == 200:
            print("Signup successful")
            return True
        print("Login/Signup failed")
        return False

def test_create_post():
    print("\nTesting Create Post...")
    data = {
        "title": "Test Apple",
        "description": "Fresh apples",
        "category": "Fruit",
        "quantity": "5 kg",
        "estimated_weight_kg": 5.0,
        "dietary_tags": ["Vegan"],
        "location_text": "Downtown",
        "pickup_window_start": "2025-12-03T10:00:00",
        "pickup_window_end": "2025-12-03T12:00:00",
        "expires_at": "2025-12-05T10:00:00"
    }
    resp = SESSION.post(f"{BASE_URL}/api/food-posts", json=data)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    if resp.status_code == 201:
        return resp.json()["id"]
    return None

def test_list_posts():
    print("\nTesting List Posts...")
    resp = SESSION.get(f"{BASE_URL}/api/food-posts")
    print(f"Status: {resp.status_code}")
    posts = resp.json()
    print(f"Count: {len(posts)}")
    return posts

def test_claim_post(post_id):
    print(f"\nTesting Claim Post {post_id}...")
    # Need to login as another user to claim
    # But for simplicity, let's just try to claim (it will fail if own post)
    # So we need a second session.
    
    session2 = requests.Session()
    # Login user 2
    email2 = "claimer@test.com"
    pass2 = "password"
    # Signup/Login
    session2.post(f"{BASE_URL}/signup", data={"email": email2, "password": pass2, "role": "user"})
    session2.post(f"{BASE_URL}/login", data={"email": email2, "password": pass2})
    
    data = {"requested_quantity": "1 kg", "message": "I want some"}
    resp = session2.post(f"{BASE_URL}/api/food-posts/{post_id}/claims", json=data)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
    if resp.status_code == 201:
        return resp.json()["id"]
    return None

def run():
    if not login("owner@test.com", "password"):
        return

    post_id = test_create_post()
    if post_id:
        test_list_posts()
        claim_id = test_claim_post(post_id)
        
        if claim_id:
            print("\nTesting Accept Claim...")
            # Owner accepts
            resp = SESSION.patch(f"{BASE_URL}/api/claims/{claim_id}", json={"status": "accepted"})
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.text}")

if __name__ == "__main__":
    run()
