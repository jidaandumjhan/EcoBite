# EcoBite

EcoBite is a web application designed to help reduce food waste by connecting individuals and businesses with surplus food to those who need it. It facilitates the sharing of food items, tracking of environmental impact, and community engagement.

## Features

-   **User Authentication**:
    -   Secure sign-up and login for users and businesses.
    -   Role-based access (User, Business, Admin).
-   **Food Sharing**:
    -   Create posts for surplus food with details like quantity, expiration time, and location.
    -   Categorize food items (e.g., Vegetable, Fruit, Bakery).
    -   Manage your own posts.
-   **Claims**:
    -   Browse available food posts (Feed).
    -   Claim food items you need.
-   **Impact Tracking**:
    -   Visual statistics on your contribution to waste reduction.
-   **API Integration**:
    -   Full suite of API endpoints for frontend interaction and potential external integrations.

## Technology Stack

-   **Backend Framework**: [Flask](https://flask.palletsprojects.com/) (Python)
-   **Database**: [MariaDB](https://mariadb.org/)
-   **Frontend**: HTML5, CSS3, JavaScript
-   **Templating Engine**: [Jinja2](https://jinja.palletsprojects.com/)
-   **Environment Management**: [python-dotenv](https://pypi.org/project/python-dotenv/)

## Prerequisites

Before running the application, ensure you have the following installed:

-   **Python** (3.8 or higher)
-   **MariaDB Server**
-   **git** (for cloning the repository)

## Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/jidaandumjhan/EcoBite.git
    cd EcoBite
    ```

2.  **Set up a virtual environment**
    ```bash
    # Create the virtual environment
    python -m venv venv

    # Activate the virtual environment
    # On Windows:
    venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Database Configuration**
    
    1.  Ensure your MariaDB server is running.
    2.  Create a `.env` file in the project root directory. You can use the provided `.env.example` as a template.
    3.  Add your database credentials and secret key to `.env`:
        ```env
        DB_USER=your_db_user
        DB_PASS=your_db_password
        DB_HOST=127.0.0.1
        DB_PORT=3306
        DB_NAME=ecobite
        SECRET_KEY=your_secret_key
        ```

5.  **Initialize the Database**
    The application is designed to attempt to create the database if it doesn't exist upon connection, but ensure your database user has the appropriate permissions. You can also manually inspect the schema using the provided scripts in `db/`.

## Usage

1.  **Run the application**
    ```bash
    python run.py
    ```

2.  **Access the application**
    Open your web browser and navigate to:
    `http://127.0.0.1:5000`

## Project Structure

```
EcoBite/
├── app/                 # Application core
│   ├── blueprints/      # Modular route handlers
│   │   ├── api.py       # REST API endpoints
│   │   ├── auth.py      # Authentication (Login/Signup)
│   │   ├── claims.py    # Claim logic and processing
│   │   ├── main.py      # Core UI routes (Home, Profile)
│   │   └── posts.py     # Food post management
│   ├── __init__.py      # App factory and initialization
│   ├── config.py        # Environment configuration
│   ├── db.py            # Database connection handler
│   └── utils.py         # Shared utility functions
├── db/                  # Database resources
│   └── schema.sql       # Database schema definition
├── scripts/             # Maintenance scripts
│   ├── inspect_db.py    # Database inspection tool
│   └── migrate_db.py    # Database migration utility
├── static/              # Static assets (CSS, JS, Images)
├── templates/           # HTML/Jinja2 templates
├── tests/               # Quality assurance
│   ├── test_api.py      # API integration tests
│   └── verify_app.py    # Startup verification script
├── uploads/             # User-uploaded content directory
├── .env.example         # Template for environment variables
├── .gitignore           # Git ignore rules
├── README.md            # Project documentation
├── requirements.txt     # Python dependencies
└── run.py               # Application entry point
```

## Contributing

1.  Fork the repository.
2.  Create a new branch (`git checkout -b feature/YourFeature`).
3.  Commit your changes (`git commit -m 'Add some feature'`).
4.  Push to the branch (`git push origin feature/YourFeature`).
5.  Open a Pull Request.
