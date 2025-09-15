# 🌱 EcoBite

EcoBite is a **Food-sharing app**.  
The main idea is simple: when someone has leftover food, they can post it in the app with a short description and an expiry time.  
Nearby students (people) get notified and can claim the food — helping reduce food waste and support sustainability.

---

## 📌 What this project does

- A student/cafeteria/Restaurant can **create a post** like: 
  *“🍕 2 pizza slices in Dorm A — expires in 20 min.”*
- The post saves:
  - description (what food it is)
  - location (latitude/longitude)
  - expiry time (after which the food is gone)
  - optional photo
- Other students nearby will **see the post**.
- A student can **request to claim** the food.
- The **poster approves** who gets the food (to prevent multiple people showing up).
- If no one claims within the expiry time → post becomes **expired**.

---

## 🛠 Tech Used

**Programming Languages**
- Python (backend logic)
- HTML + CSS + JavaScript (frontend pages)

**Framework**
- Flask (a Python web framework)

**Database**
- PostgreSQL with PostGIS (for location and radius features)

**Other Tools**
- Docker (for running the database easily)
- GitHub (for version control and collaboration)

---

## 📂 Project Structure

This is how the project folders and files are organized:
```plaintext
ecobite/
├── app.py               # Main Flask app (Hello World for now)
├── requirements.txt     # Python dependencies
├── README.md            # Project documentation
├── .gitignore           # Ignore venv, cache, uploads, etc.
├── .env.example         # Example environment variables
│
├── db/                  # Database files
│   ├── schema.sql       # Database schema (tables, extensions)
│   └── README.md        # Notes about the database
│
├── templates/           # HTML templates for Flask
│   ├── index.html       # Homepage (Hello World page for now)
│   └── create.html      # Page to create a new food post
│
├── static/              # Static assets (CSS, JS, Service Worker)
│   ├── main.css         # Stylesheet
│   ├── app.js           # Frontend logic
│   └── sw.js            # Service worker (for push notifications)
│
└── uploads/             # Uploaded food photos (empty for now)
    └── .gitkeep         # Keeps the folder in Git


